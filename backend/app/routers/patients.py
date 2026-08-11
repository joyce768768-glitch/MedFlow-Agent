"""患者路由：列表 / 详情 / 接诊（LangGraph 主流程）/ 归档。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import assert_patient_access, get_current_user
from app.graph.workflow import admission_graph
from app.schemas import PatientSummary
from app.storage import store

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientSummary])
def list_patients(user: dict = Depends(get_current_user)):
    """患者列表（按角色数据范围过滤）。"""
    out = []
    for state in store.list_patients():
        # 数据范围过滤
        try:
            assert_patient_access(user, state["patient_id"], need_write=False)
        except Exception:
            continue
        out.append({
            "patient_id": state["patient_id"],
            "patient_name": state.get("patient_name", ""),
            "status": state.get("status", ""),
            "attending_doctor_ids": state.get("attending_doctor_ids", []),
            "check_task_count": len(state.get("check_tasks", [])),
            "mdt_comment_count": len(state.get("mdt_comments", [])),
        })
    return out


@router.get("/{patient_id}")
def get_patient(patient_id: str, user: dict = Depends(get_current_user)):
    """患者 State（按数据范围二次鉴权；按角色脱敏返回）。

    护士仅返回基础信息 + 检查任务状态，不返回 emr / mdt / 历史 / audit。
    其他角色返回完整 State（写动作仍受后端二次鉴权约束）。
    """
    assert_patient_access(user, patient_id, need_write=False)
    state = store.get_patient(patient_id)
    if user["role"] == "nurse":
        return {
            "patient_id": state.get("patient_id"),
            "patient_name": state.get("patient_name"),
            "status": state.get("status"),
            "attending_doctor_ids": state.get("attending_doctor_ids", []),
            "check_tasks": state.get("check_tasks", []),
        }
    return state


@router.post("/{patient_id}/admit")
def admit_patient(patient_id: str, user: dict = Depends(get_current_user)):
    """接诊：调用 LangGraph 主接诊流程图。

    流程：准入校验 -> 接诊(节点内 if enable_emr_subagent 分支) -> HITL 卡点。
    返回更新后的 ai_draft / hitl_pending。
    """
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    # 复制一份喂给图，避免图内 replace 语义丢失字段
    result = admission_graph.invoke(dict(state))
    # 合并图输出
    store.patch_patient(patient_id, result)
    store.append_audit(patient_id, "admit", user, "执行接诊流程（LangGraph 主流程）")
    return store.get_patient(patient_id)


@router.post("/{patient_id}/archive")
def archive_patient(patient_id: str, user: dict = Depends(get_current_user)):
    """归档 & 审计落盘（纯规则节点）。"""
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    from app.graph.nodes import node_archive_audit
    patch = node_archive_audit(state, actor=user)
    store.patch_patient(patient_id, patch)
    store.append_audit(patient_id, "archive", user, "归档 & 审计落盘")
    return store.get_patient(patient_id)
