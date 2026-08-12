"""病历路由：主病历读取 / 编辑 / 定稿锁定 / AI 草稿生成 / 对话辅助。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.auth import assert_patient_access, get_current_user, require_action
from app.graph.nodes import emr_draft_subagent_wrapper
from app.schemas import AiDraftResponse, EmrLockRequest, EmrUpdateRequest
from app.storage import store
from app.subagents import emr_chat_subagent

router = APIRouter(prefix="/patients/{patient_id}/emr", tags=["emr"])


class EmrChatRequest(BaseModel):
    """病历对话请求。"""
    message: str


class EmrChatMessageOut(BaseModel):
    """病历对话消息。"""
    msg_id: str
    role: str
    content: str
    timestamp: str
    provider_used: Optional[str] = None
    trace_id: Optional[str] = None
    structured_output: Optional[dict] = None


def _build_patient_context(state: dict) -> str:
    """从患者 State 抽取关键信息作为对话上下文（注入 system message）。"""
    lines = []
    emr = state.get("emr_main", {}) or {}
    if emr.get("content"):
        lines.append(f"当前病历正文：\n{emr['content']}")
    if emr.get("locked"):
        lines.append("（病历已定稿锁定，建议仅做参考性讨论，正式修改需先解锁）")

    cc = state.get("chief_complaint") or ""
    if cc:
        lines.append(f"主诉：{cc}")

    # 已完成的检查结果摘要
    tasks = state.get("check_tasks", []) or []
    done = [t for t in tasks if t.get("status") == "done"]
    if done:
        lines.append("已完成检查：")
        for t in done[:5]:
            r = t.get("result") or {}
            lines.append(f"  - {t.get('task_label', '')}：{r.get('summary', '结果已回填')}")

    return "\n".join(lines)


def _build_kb_context(state: dict) -> str:
    """从知识库召回 SOAP 模板/指南/药品字典（简化版：直接返回全部 active 条目）。"""
    try:
        entries = store.kb_for_emr_draft()
    except Exception:
        return ""
    if not entries:
        return ""
    lines = []
    for e in entries[:5]:
        lines.append(f"[{e.get('category')}] {e.get('title')}：{e.get('content', '')[:200]}")
    return "\n".join(lines)


@router.get("")
def get_emr(patient_id: str, user: dict = Depends(require_action("can_view_emr"))):
    """读取主病历（含锁定状态）。"""
    assert_patient_access(user, patient_id, need_write=False)
    state = store.get_patient(patient_id)
    return {
        "emr_main": state.get("emr_main", {}),
        "ai_draft": state.get("ai_draft"),
        "enable_emr_subagent": bool(state.get("enable_emr_subagent")),
    }


@router.put("")
def update_emr(patient_id: str, body: EmrUpdateRequest, user: dict = Depends(get_current_user)):
    """编辑主病历正文（仅主治；已定稿锁定时禁止编辑）。"""
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    emr = dict(state.get("emr_main", {}))
    if emr.get("locked"):
        raise HTTPException(status.HTTP_409_CONFLICT, "病历已定稿锁定，不可编辑；如需修改请新建诊疗版本")
    emr["content"] = body.content
    emr["locked"] = False
    store.patch_patient(patient_id, {"emr_main": emr})
    store.append_audit(patient_id, "emr_update", user, "编辑主病历正文（未定稿）")
    return store.get_patient(patient_id).get("emr_main")


@router.post("/lock")
def lock_emr(patient_id: str, body: EmrLockRequest, user: dict = Depends(get_current_user)):
    """定稿锁定 / 解锁（仅主治；HITL 终审确认）。"""
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    from app.storage import now
    emr = dict(state.get("emr_main", {}))
    emr["locked"] = body.locked
    if body.locked:
        emr["locked_at"] = now()
        emr["locked_by"] = user["user_id"]
        emr["locked_by_name"] = user["name"]
    else:
        emr["locked_at"] = None
        emr["locked_by"] = None
        emr["locked_by_name"] = None
    store.patch_patient(patient_id, {"emr_main": emr})
    store.append_audit(patient_id, "emr_lock" if body.locked else "emr_unlock", user,
                       "定稿锁定" if body.locked else "解除锁定")
    return store.get_patient(patient_id).get("emr_main")


@router.post("/ai-draft", response_model=AiDraftResponse)
def generate_ai_draft(patient_id: str, user: dict = Depends(get_current_user)):
    """生成 AI 病历草稿（节点内 if enable_emr_subagent 开关分支）。

    - 开启：调用 emr_draft_subagent，输出写入 ai_draft（隔离区，不进 emr_main）
    - 关闭：返回提示，走人工编辑
    两条分支最终都需主治 HITL 确认后才可手动采纳到正式病历。
    """
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    enabled = bool(state.get("enable_emr_subagent"))
    if not enabled:
        store.append_audit(patient_id, "emr_subagent_skip", user, "病历 SubAgent 关闭，走人工编辑")
        return {"ai_draft": "病历 SubAgent 已关闭，请直接人工编辑主病历。", "enabled": False}
    draft = emr_draft_subagent_wrapper(state)
    store.patch_patient(patient_id, {"ai_draft": draft, "hitl_pending": True})
    store.append_audit(patient_id, "emr_subagent_generate", user, "调用病历 SubAgent 生成草稿（隔离）")
    return {"ai_draft": draft, "enabled": True}


# ==================== 病历 Agent 对话辅助 ====================

@router.get("/chat/history", response_model=list[EmrChatMessageOut])
def get_emr_chat_history(patient_id: str, user: dict = Depends(require_action("can_view_emr"))):
    """获取病历 Agent 对话历史。"""
    assert_patient_access(user, patient_id, need_write=False)
    return store.get_emr_chat_history(patient_id)


@router.post("/chat", response_model=EmrChatMessageOut)
def emr_chat(patient_id: str, body: EmrChatRequest, user: dict = Depends(get_current_user)):
    """病历 Agent 对话：医生发消息，AI 返回 SOAP 草稿建议。

    - 需主治医生权限（can_edit_emr 隐含写权限）
    - 多轮对话，历史从 store.emr_chat_sessions 读取
    - SubAgent 关闭时不阻断对话，但会在回复中提示（向后兼容）
    - 真模型失败自动降级 Mock，保证服务不中断
    """
    assert_patient_access(user, patient_id, need_write=True)
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "消息不能为空")
    if len(msg) > 2000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "消息过长（>2000 字符）")

    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者不存在")

    # 写入用户消息
    store.append_emr_chat_message(patient_id, "user", msg)

    # 调用 SubAgent
    history = store.get_emr_chat_history(patient_id)
    patient_ctx = _build_patient_context(state)
    kb_ctx = _build_kb_context(state)

    result = emr_chat_subagent(
        patient_id=patient_id,
        message=msg,
        history=history[:-1],  # 排除刚写入的 user 消息，避免重复
        patient_context=patient_ctx,
        kb_context=kb_ctx,
    )

    # 写入 AI 消息
    ai_msg = store.append_emr_chat_message(
        patient_id, "assistant", result.get("reply", ""),
        extra={
            "provider_used": result.get("provider_used"),
            "trace_id": result.get("trace_id"),
            "structured_output": result.get("structured_output"),
        },
    )

    store.append_audit(
        patient_id, "emr_chat", user,
        f"病历对话：医生发送 {len(msg)} 字，AI 回复 {len(result.get('reply', ''))} 字（{result.get('provider_used')}）",
    )
    return ai_msg


@router.delete("/chat/session")
def reset_emr_chat(patient_id: str, user: dict = Depends(get_current_user)):
    """清空病历 Agent 对话历史。"""
    assert_patient_access(user, patient_id, need_write=True)
    n = store.clear_emr_chat_history(patient_id)
    store.append_audit(patient_id, "emr_chat_reset", user, f"清空病历对话历史（{n} 条）")
    return {"cleared": n}
