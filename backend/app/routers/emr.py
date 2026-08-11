"""病历路由：主病历读取 / 编辑 / 定稿锁定 / AI 草稿生成。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import assert_patient_access, get_current_user, require_action
from app.graph.nodes import emr_draft_subagent_wrapper
from app.schemas import AiDraftResponse, EmrLockRequest, EmrUpdateRequest
from app.storage import store

router = APIRouter(prefix="/patients/{patient_id}/emr", tags=["emr"])


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
