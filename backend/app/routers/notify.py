"""通知 & 审计路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import assert_patient_access, get_current_user, require_action
from app.schemas import NotifyOut
from app.storage import store

router = APIRouter(tags=["notify"])


@router.get("/notifications", response_model=list[NotifyOut])
def list_notifications(user: dict = Depends(get_current_user)):
    """当前用户的 Mock 站内通知。"""
    return store.list_notifications(user["user_id"])


@router.get("/patients/{patient_id}/audit-log")
def list_audit(patient_id: str, user: dict = Depends(require_action("can_view_history"))):
    """患者审计日志（只读；护士不可见）。"""
    assert_patient_access(user, patient_id, need_write=False)
    state = store.get_patient(patient_id)
    return state.get("audit_log", [])
