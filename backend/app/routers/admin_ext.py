"""后台管理扩展路由：主数据 / RAG文档 / Agent配置 / 归档病案 / 系统审计。

与 admin.py 共用 /admin 前缀，仅 admin 角色可访问。
所有写操作自动记录系统审计日志（store.append_system_audit）。
Demo 全 Mock 存储，重启数据重置。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.auth import require_admin
from app.schemas import (
    AgentConfigOut,
    AgentToggleRequest,
    ArchivedCaseSummary,
    BuildingCreate,
    BuildingOut,
    ExamItemCreate,
    ExamItemOut,
    ExamItemUpdate,
    FloorCreate,
    RagDocCreate,
    RagDocOut,
    RagDocStatusUpdate,
    RagDocUpdate,
    RagRecallHit,
    RagRecallRequest,
    RoomBind,
    SystemAuditOut,
)
from app.storage import Store, store

router = APIRouter(prefix="/admin", tags=["admin-ext"], dependencies=[Depends(require_admin)])

_VALID_EXAM_CATS = {"blood", "ct", "ultrasound", "pathology", "other"}
_VALID_RAG_CATS = {"clinical_guide", "soap_template", "sop", "mdt_template"}
_VALID_RAG_STATUS = {"pending", "active", "inactive"}
_VALID_AGENT_KEYS = {"emr_agent", "imaging_agent"}


def _audit(user: dict, action: str, entity: str, entity_id: str = "",
           before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    """记录系统审计日志（快捷方法）。"""
    store.append_system_audit(
        operator_id=user.get("user_id", ""), operator_name=user.get("name", ""),
        action=action, entity=entity, entity_id=entity_id,
        before=before, after=after,
    )


# ==================== 楼宇/楼层/房间 ====================
@router.get("/buildings", response_model=list[BuildingOut])
def list_buildings():
    return store.list_buildings()


@router.post("/buildings", response_model=BuildingOut)
def create_building(body: BuildingCreate, user: dict = Depends(require_admin)):
    b = store.add_building(body.name)
    _audit(user, "create", "building", b["building_id"], after=b)
    return b


@router.put("/buildings/{building_id}", response_model=BuildingOut)
def update_building(building_id: str, body: BuildingCreate, user: dict = Depends(require_admin)):
    before = store.buildings.get(building_id)
    b = store.update_building(building_id, body.name)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "楼宇不存在")
    _audit(user, "update", "building", building_id, before=before, after=b)
    return b


@router.delete("/buildings/{building_id}")
def delete_building(building_id: str, user: dict = Depends(require_admin)):
    ok = store.delete_building(building_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "楼宇不存在")
    _audit(user, "delete", "building", building_id)
    return {"deleted": True}


@router.post("/buildings/{building_id}/floors", response_model=BuildingOut)
def add_floor(building_id: str, body: FloorCreate, user: dict = Depends(require_admin)):
    f = store.add_floor(building_id, body.name)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "楼宇不存在")
    b = next(b for b in store.list_buildings() if b["building_id"] == building_id)
    _audit(user, "create", "floor", f["floor_id"], after={"building": building_id, "name": body.name})
    return b


@router.delete("/buildings/{building_id}/floors/{floor_id}")
def delete_floor(building_id: str, floor_id: str, user: dict = Depends(require_admin)):
    ok = store.delete_floor(building_id, floor_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "楼层不存在")
    _audit(user, "delete", "floor", floor_id)
    return {"deleted": True}


@router.post("/buildings/{building_id}/floors/{floor_id}/rooms", response_model=BuildingOut)
def bind_room(building_id: str, floor_id: str, body: RoomBind, user: dict = Depends(require_admin)):
    r = store.bind_room(building_id, floor_id, body.room_name, body.dept_name)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "楼宇或楼层不存在")
    b = next(b for b in store.list_buildings() if b["building_id"] == building_id)
    _audit(user, "create", "room", r["room_id"], after=r)
    return b


@router.delete("/buildings/{building_id}/floors/{floor_id}/rooms/{room_id}")
def delete_room(building_id: str, floor_id: str, room_id: str, user: dict = Depends(require_admin)):
    ok = store.delete_room(building_id, floor_id, room_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "房间不存在")
    _audit(user, "delete", "room", room_id)
    return {"deleted": True}


# ==================== 检验/检查项目字典 ====================
@router.get("/exam-items", response_model=list[ExamItemOut])
def list_exam_items(category: Optional[str] = None):
    return store.list_exam_items(category)


@router.post("/exam-items", response_model=ExamItemOut)
def create_exam_item(body: ExamItemCreate, user: dict = Depends(require_admin)):
    if body.category not in _VALID_EXAM_CATS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"分类非法，可选：{sorted(_VALID_EXAM_CATS)}")
    item = store.add_exam_item(code=body.code, name=body.name, category=body.category,
                               spec=body.spec, ref_range=body.ref_range)
    _audit(user, "create", "exam_item", item["item_id"], after=item)
    return item


@router.put("/exam-items/{item_id}", response_model=ExamItemOut)
def update_exam_item(item_id: str, body: ExamItemUpdate, user: dict = Depends(require_admin)):
    before = store.exam_items.get(item_id)
    item = store.update_exam_item(item_id, body.model_dump(exclude_none=True))
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    _audit(user, "update", "exam_item", item_id, before=before, after=item)
    return item


@router.delete("/exam-items/{item_id}")
def delete_exam_item(item_id: str, user: dict = Depends(require_admin)):
    ok = store.delete_exam_item(item_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    _audit(user, "delete", "exam_item", item_id)
    return {"deleted": True}


# ==================== RAG 文档库 ====================
@router.get("/rag/docs", response_model=list[RagDocOut])
def list_rag_docs(category: Optional[str] = None):
    return store.list_rag_docs(category)


@router.post("/rag/docs", response_model=RagDocOut)
def create_rag_doc(body: RagDocCreate, user: dict = Depends(require_admin)):
    if body.category not in _VALID_RAG_CATS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"分类非法，可选：{sorted(_VALID_RAG_CATS)}")
    doc = store.add_rag_doc(title=body.title, category=body.category, content=body.content,
                            uploaded_by=user.get("user_id", ""), uploaded_by_name=user.get("name", ""))
    _audit(user, "create", "rag_doc", doc["doc_id"], after={"title": doc["title"], "chunks": len(doc["chunks"])})
    return doc


@router.get("/rag/docs/{doc_id}", response_model=RagDocOut)
def get_rag_doc(doc_id: str):
    doc = store.get_rag_doc(doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    return doc


@router.put("/rag/docs/{doc_id}", response_model=RagDocOut)
def update_rag_doc(doc_id: str, body: RagDocUpdate, user: dict = Depends(require_admin)):
    before = store.get_rag_doc(doc_id)
    doc = store.update_rag_doc(doc_id, title=body.title, content=body.content)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    _audit(user, "update", "rag_doc", doc_id,
           before={"title": before["title"], "version": before["version"]},
           after={"title": doc["title"], "version": doc["version"], "chunks": len(doc["chunks"])})
    return doc


@router.put("/rag/docs/{doc_id}/status", response_model=RagDocOut)
def set_rag_doc_status(doc_id: str, body: RagDocStatusUpdate, user: dict = Depends(require_admin)):
    if body.status not in _VALID_RAG_STATUS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"状态非法，可选：{sorted(_VALID_RAG_STATUS)}")
    before = store.get_rag_doc(doc_id)
    doc = store.set_rag_doc_status(doc_id, body.status)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    _audit(user, "activate" if body.status == "active" else "deactivate",
           "rag_doc", doc_id, before={"status": before["status"]}, after={"status": body.status})
    return doc


@router.delete("/rag/docs/{doc_id}")
def delete_rag_doc(doc_id: str, user: dict = Depends(require_admin)):
    ok = store.delete_rag_doc(doc_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    _audit(user, "delete", "rag_doc", doc_id)
    return {"deleted": True}


@router.post("/rag/recall", response_model=list[RagRecallHit])
def rag_recall(body: RagRecallRequest):
    """Mock 召回测试：输入指令，返回匹配的 active 文档片段。生产需替换为真实向量检索。"""
    return store.rag_recall(body.query, body.top_k)


# ==================== Agent 能力灰度配置 ====================
@router.get("/agents/config", response_model=AgentConfigOut)
def get_agent_config():
    return store.get_agent_config()


@router.put("/agents/toggle", response_model=AgentConfigOut)
def toggle_agent(body: AgentToggleRequest, user: dict = Depends(require_admin)):
    if body.agent_key not in _VALID_AGENT_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Agent 非法，可选：{sorted(_VALID_AGENT_KEYS)}")
    before = store.get_agent_config()
    store.set_agent_config(body.agent_key, global_on=body.global_on,
                           hospital_id=body.hospital_id, hospital_on=body.hospital_on)
    after = store.get_agent_config()
    _audit(user, "agent_toggle", "agent_config", body.agent_key,
           before=before.get(body.agent_key), after=after.get(body.agent_key))
    return after


# ==================== 归档病案查阅（只读） ====================
@router.get("/cases", response_model=list[ArchivedCaseSummary])
def list_archived_cases(patient_id: Optional[str] = None, doctor_id: Optional[str] = None):
    """归档病案列表（只读，不修改原始 State）。"""
    return store.list_archived_cases(patient_id=patient_id, doctor_id=doctor_id)


@router.get("/cases/{patient_id}")
def get_archived_case(patient_id: str):
    """归档病案详情（只读快照：病历多版本 + MDT讨论 + 审计日志 + 检查任务）。"""
    detail = store.get_archived_case_detail(patient_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "病案不存在")
    return detail


# ==================== 系统审计日志 ====================
@router.get("/audit", response_model=list[SystemAuditOut])
def list_system_audit(action: Optional[str] = None, entity: Optional[str] = None):
    """系统审计日志列表（后台数据修改 / Agent开关变更 / 归档操作留痕）。"""
    return store.list_system_audit(action=action, entity=entity)
