"""检查任务路由：列表 / 开立 / 状态流转 / 检验汇总 SubAgent。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import assert_patient_access, get_current_user
from app.graph.nodes import node_open_check_task, node_transition_check_task
from app.schemas import CheckTaskCreate, CheckTaskOut, CheckTaskStatusUpdate
from app.storage import store
from app.subagents import lab_summary_subagent

router = APIRouter(prefix="/patients/{patient_id}/check-tasks", tags=["check-tasks"])

_VALID_TYPES = {"blood": "血常规", "ct": "CT", "ultrasound": "B超"}


@router.get("", response_model=list[CheckTaskOut])
def list_tasks(patient_id: str, user: dict = Depends(get_current_user)):
    """检查任务列表（护士只读可见）。"""
    assert_patient_access(user, patient_id, need_write=False)
    state = store.get_patient(patient_id)
    return state.get("check_tasks", [])


@router.post("", response_model=CheckTaskOut)
def create_task(patient_id: str, body: CheckTaskCreate, user: dict = Depends(get_current_user)):
    """开立检查任务（仅主治）。状态：ordered 已开立。"""
    assert_patient_access(user, patient_id, need_write=True)
    if body.task_type not in _VALID_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "task_type 非法")
    label = body.task_label or _VALID_TYPES[body.task_type]
    state = store.get_patient(patient_id)
    patch = node_open_check_task(state, task_type=body.task_type, task_label=label, actor=user)
    store.patch_patient(patient_id, patch)
    store.append_audit(patient_id, "check_task_open", user, f"开立检查 {label}")
    return patch["check_tasks"][-1]


@router.patch("/{task_id}", response_model=CheckTaskOut)
def transition_task(
    patient_id: str, task_id: str, body: CheckTaskStatusUpdate, user: dict = Depends(get_current_user)
):
    """检查任务状态流转：ordered -> pending -> done（仅主治）。done 时回填 Mock 结果。"""
    assert_patient_access(user, patient_id, need_write=True)
    if body.status not in {"ordered", "pending", "done"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "status 非法")
    state = store.get_patient(patient_id)
    patch = node_transition_check_task(state, task_id=task_id, new_status=body.status, actor=user)
    if not patch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    store.patch_patient(patient_id, patch)
    store.append_audit(patient_id, "check_task_transition", user, f"任务 {task_id} -> {body.status}")
    for t in patch["check_tasks"]:
        if t["task_id"] == task_id:
            return t
    raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")


@router.post("/lab-summary")
def lab_summary(patient_id: str, user: dict = Depends(get_current_user)):
    """检验汇总 SubAgent（节点内 if enable_lab_subagent 开关分支）。

    - 开启：调用 lab_summary_subagent 生成汇总建议（隔离输出，不写正式病历）
    - 关闭：返回提示，走人工解读
    """
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    enabled = bool(state.get("enable_lab_subagent"))
    if not enabled:
        return {"enabled": False, "summary": "检验汇总 SubAgent 已关闭，请人工解读检查结果。"}
    summary = lab_summary_subagent(state.get("check_tasks", []))
    store.append_audit(patient_id, "lab_summary_subagent", user, "调用检验汇总 SubAgent")
    return {"enabled": True, "summary": summary}
