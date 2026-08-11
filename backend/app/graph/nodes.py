"""LangGraph 节点定义（方案A：同一节点内 if 开关分支，不维护两套 Graph）。

7 个节点：
1. node_admission_guard   —— 准入 & 权限校验（纯 Workflow，无 LLM）
2. node_admit_emr         —— 接诊节点：if enable_emr_subagent 调用 emr_draft_subagent；否则跳过 AI
3. node_open_check_task   —— 开立检查任务（纯 Workflow，Mock 状态流转）
4. node_mdt_invite        —— MDT 邀请子图：临时授权 + 时效 + 白名单写入
5. node_new_treatment     —— 诊疗方案版本新建（新建版本，不覆盖旧版）
6. node_adopt_mdt_comment —— MDT 意见采纳（仅主治，写入标记 + 推送通知）
7. node_archive_audit     —— 归档 & 审计落盘（纯规则）

每个节点：接收 PatientState（dict），返回 partial 更新（默认 replace 语义）。
节点均为纯函数，可被 LangGraph 编排，也可被路由直接调用复用。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.storage import now, uid
from app.subagents import emr_draft_subagent


def _expires_at(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).astimezone().isoformat(timespec="seconds")


# ============================================================
# 节点 1：准入 & 权限校验（纯 Workflow，无 LLM）
# ============================================================
def node_admission_guard(state: dict) -> dict:
    """校验患者是否可进入诊疗流程：存在性 + 状态准入。

    说明：细粒度 RBAC（角色 + 数据范围）由 API 层 auth 二次鉴权完成；
    本节点负责 Workflow 层的"患者状态准入"规则，不调用 LLM。
    """
    patient_id = state.get("patient_id", "")
    if not patient_id:
        return {"status": "waiting", "hitl_pending": False}
    # 准入规则：已归档不可重新接诊
    if state.get("status") == "archived":
        return {"hitl_pending": False}
    return {"status": "in_progress"}


# ============================================================
# 节点 2：接诊节点（方案A：同节点 if 开关分支）
# ============================================================
def node_admit_emr(state: dict) -> dict:
    """接诊 + 病历草稿分支。

    - enable_emr_subagent=True  -> 调用 emr_draft_subagent 生成 AI 草稿（隔离区）
    - enable_emr_subagent=False -> 跳过 AI，走人工编辑
    两条分支收敛至同一 HITL 终审卡点（hitl_pending=True）。
    AI 草稿写入 state.ai_draft，绝不自动写入 emr_main。
    """
    if state.get("enable_emr_subagent"):
        draft = emr_draft_subagent_wrapper(state)
        return {"ai_draft": draft, "hitl_pending": True, "status": "in_progress"}
    # 关闭 SubAgent：人工编辑路径
    return {"ai_draft": None, "hitl_pending": True, "status": "in_progress"}


def emr_draft_subagent_wrapper(state: dict) -> str:
    """包装 SubAgent 调用：从知识库检索相关条目，透传给病历 SubAgent。

    真实场景替换为 RAG + LLM；此处 Mock 用关键词检索知识库。
    """
    from app.storage import store
    patient_name = state.get("patient_name", "患者")
    # 按主诉关键词检索知识库（Mock：取全部指南/SOAP/药品条目）
    kb = store.kb_for_emr_draft(patient_name)
    return emr_draft_subagent(patient_name, chief_complaint="", kb_entries=kb)


# ============================================================
# 节点 3：开立检查任务（纯 Workflow，Mock 状态流转）
# ============================================================
def node_open_check_task(
    state: dict,
    *,
    task_type: str,
    task_label: str,
    actor: dict,
) -> dict:
    """新建检查任务，初始状态 ordered（已开立）。

    状态机：ordered(已开立) -> pending(待执行) -> done(已完成)。
    仅模拟流转，不联真实检验科。
    """
    task = {
        "task_id": uid("task"),
        "task_type": task_type,
        "task_label": task_label,
        "status": "ordered",
        "created_at": now(),
        "created_by": actor.get("user_id", "system"),
        "created_by_name": actor.get("name", "系统"),
        "completed_at": None,
        "result": None,
    }
    tasks = list(state.get("check_tasks", []))
    tasks.append(task)
    return {"check_tasks": tasks}


def node_transition_check_task(state: dict, *, task_id: str, new_status: str, actor: dict) -> dict:
    """检查任务状态流转（ordered -> pending -> done）。

    done 时回填 Mock 结构化结果。
    """
    tasks = list(state.get("check_tasks", []))
    mock_results = {
        "blood": {"summary": "WBC 7.5，Hb 135，基本正常。", "wbc": 7.5, "hb": 135},
        "ct": {"summary": "胸部 CT 未见明显异常。", "finding": "无"},
        "ultrasound": {"summary": "腹部 B 超：肝胆胰脾未见明显异常。", "finding": "无"},
    }
    updated = False
    for t in tasks:
        if t.get("task_id") == task_id:
            t["status"] = new_status
            if new_status == "done":
                t["completed_at"] = now()
                t["result"] = mock_results.get(t.get("task_type"), {"summary": "结果已回填"})
            updated = True
            break
    if not updated:
        return {}
    return {"check_tasks": tasks}


# ============================================================
# 节点 4：MDT 邀请子图（临时授权 + 时效 + 白名单写入）
# ============================================================
def node_mdt_invite(
    state: dict,
    *,
    expert_id: str,
    expert_name: str,
    expires_hours: int,
    actor: dict,
) -> dict:
    """邀请 MDT 专家：写入临时授权白名单（带时效）。

    独立子 Workflow：临时授权 -> 时效控制 -> 权限写入白名单。
    """
    invitation = {
        "invitation_id": uid("inv"),
        "expert_id": expert_id,
        "expert_name": expert_name,
        "invited_at": now(),
        "expires_at": _expires_at(expires_hours),
        "active": True,
    }
    invites = list(state.get("mdt_invitations", []))
    # 同一专家不重复邀请（覆盖时效）
    invites = [i for i in invites if i.get("expert_id") != expert_id]
    invites.append(invitation)
    return {"mdt_invitations": invites}


# ============================================================
# 节点 5：诊疗方案版本新建（新建版本，不覆盖旧版）
# ============================================================
def node_new_treatment(state: dict, *, content: str, actor: dict) -> dict:
    """新建诊疗方案版本：version_no +1，时间戳，原文保留。

    不做版本 Diff 对比；历史版本只读，不覆盖。
    """
    versions = list(state.get("treatment_versions", []))
    next_no = max([v.get("version_no", 0) for v in versions], default=0) + 1
    version = {
        "version_id": uid("ver"),
        "version_no": next_no,
        "content": content,
        "created_at": now(),
        "created_by": actor.get("user_id", "system"),
        "created_by_name": actor.get("name", "系统"),
    }
    # 倒序：新版本放最前
    versions.insert(0, version)
    return {"treatment_versions": versions}


# ============================================================
# 节点 6：MDT 意见采纳（仅主治，写入标记 + 推送通知）
# ============================================================
def node_adopt_mdt_comment(state: dict, *, comment_id: str, actor: dict) -> dict:
    """采纳 MDT 意见：写入 is_adopted + adopted_by + adopted_at，推送站内通知。

    - 仅主治可执行（API 层 RBAC 强制）；
    - 采纳标记独立留痕，不依靠病历文本反推；
    - 后续新建诊疗版本不修改/抹除历史采纳标记。
    """
    comments = list(state.get("mdt_comments", []))
    target: Optional[dict] = None
    for c in comments:
        if c.get("comment_id") == comment_id:
            c["is_adopted"] = True
            c["adopted_by"] = actor.get("user_id")
            c["adopted_by_name"] = actor.get("name")
            c["adopted_at"] = now()
            target = c
            break
    if not target:
        return {}
    # 推送通知给专家（Mock 站内通知）
    notify = {
        "notify_id": uid("ntf"),
        "type": "mdt_adopted",
        "target_user_id": target.get("author_id", ""),
        "message": f"您的 MDT 意见已被 {actor.get('name', '主治医生')} 采纳。",
        "created_at": now(),
        "read": False,
    }
    queue = list(state.get("notify_queue", []))
    queue.append(notify)
    return {"mdt_comments": comments, "notify_queue": queue}


# ============================================================
# 节点 7：归档 & 审计落盘（纯规则）
# ============================================================
def node_archive_audit(state: dict, *, actor: dict) -> dict:
    """归档：状态置 archived，HITL 关闭。审计落盘由 storage.append_audit 统一记录。"""
    return {"status": "archived", "hitl_pending": False}
