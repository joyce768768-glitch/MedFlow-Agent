"""诊疗方案版本路由：列表 / 新建版本（不覆盖旧版）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import assert_patient_access, get_current_user, require_action
from app.graph.nodes import node_new_treatment
from app.schemas import NewTreatmentRequest, TreatmentVersionOut
from app.storage import store

router = APIRouter(prefix="/patients/{patient_id}/treatment-versions", tags=["treatment"])


@router.get("", response_model=list[TreatmentVersionOut])
def list_versions(patient_id: str, user: dict = Depends(require_action("can_view_history"))):
    """历史诊疗方案列表（倒序，最新在前）。"""
    assert_patient_access(user, patient_id, need_write=False)
    state = store.get_patient(patient_id)
    return state.get("treatment_versions", [])


@router.post("", response_model=TreatmentVersionOut)
def new_version(patient_id: str, body: NewTreatmentRequest, user: dict = Depends(get_current_user)):
    """新建诊疗方案版本：version_no +1，时间戳，不覆盖旧版。

    仅主治可执行（后端二次鉴权 need_write=True）。
    """
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    patch = node_new_treatment(state, content=body.content, actor=user)
    store.patch_patient(patient_id, patch)
    store.append_audit(patient_id, "new_treatment_version", user, f"新建诊疗方案 v{patch['treatment_versions'][0]['version_no']}")
    return patch["treatment_versions"][0]
