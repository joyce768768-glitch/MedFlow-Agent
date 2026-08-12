"""医疗轻量 OAG 底座 — ABox 内存对象图。

本模块实现：
1. OGraph 内存单例（节点+边+元数据）
2. 从现有 Store 构建内存对象图的 build_from_store() 方法
3. 图的增删改查（节点/边），带 TBox 公理校验
4. 图的同步更新：上层 Store 变更后，通过 sync_from_store() 增量同步

设计原则：
- 只读优先：图谱为查询优化层，不替代 Store 的 CRUD 写入
- 构建式：启动时从 Store 全量构建，后续增量同步
- 公理强制：所有边创建前经过 validate_* 校验
- 时态优先：所有查询必须带时间窗口
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from .ontology import (
    AxiomViolation,
    EntityType,
    REL_METADATA,
    RelType,
    TBoxEdge,
    TBoxNode,
    _is_within_window,
    _now,
    validate_belong_to_uniqueness,
    validate_entity_fields,
    validate_rel_type,
    validate_valid_time,
    validate_visit_cardinality,
)


class OGraph:
    """医疗轻量 OAG ABox 内存对象图单例。

    节点：所有实体实例（Patient/Doctor/Department/Room/VisitRecord/ExamReport/OrderRecord/ExamItem）
    边：实体间关系（work_in/locate_in/has_visit/generate/belong_to/execute_in/order_item）
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.nodes: Dict[str, TBoxNode] = {}
        self.edges: List[TBoxEdge] = []
        self.meta: dict = {
            "version": "1.0",
            "last_sync": None,
            "axiom_checks_enabled": True,
            "node_count": 0,
            "edge_count": 0,
        }

    # ── 节点操作 ──────────────────────────────────────────

    def add_node(self, node: TBoxNode) -> TBoxNode:
        """添加节点，自动校验实体必填字段。"""
        if self.meta["axiom_checks_enabled"]:
            validate_entity_fields(node.entity_type, node.data)
        with self._lock:
            self.nodes[node.node_id] = node
            self.meta["node_count"] = len(self.nodes)
        return node

    def get_node(self, node_id: str) -> Optional[TBoxNode]:
        """按 ID 获取节点。"""
        return self.nodes.get(node_id)

    def get_nodes_by_type(self, entity_type: EntityType) -> List[TBoxNode]:
        """按类型获取所有节点。"""
        return [n for n in self.nodes.values() if n.entity_type == entity_type]

    def get_node_ids_by_type(self, entity_type: EntityType) -> Set[str]:
        """按类型获取所有节点 ID 集合。"""
        return {n.node_id for n in self.nodes.values() if n.entity_type == entity_type}

    # ── 边操作（带公理校验） ────────────────────────────────

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelType,
        valid_time: Optional[Tuple[str, str]] = None,
        permission_tag: str = "all",
        trace_id: Optional[str] = None,
    ) -> TBoxEdge:
        """添加边，自动校验：关系合法性、时态公理、唯一归属公理、基数约束。

        所有校验失败抛 AxiomViolation，禁止写入。
        """
        # 获取源/目标节点类型
        source_node = self.nodes.get(source_id)
        target_node = self.nodes.get(target_id)
        if source_node is None:
            raise AxiomViolation("节点存在性", f"源节点 {source_id} 不存在")
        if target_node is None:
            raise AxiomViolation("节点存在性", f"目标节点 {target_id} 不存在")

        # 关系合法性校验
        if self.meta["axiom_checks_enabled"]:
            validate_rel_type(rel_type, source_node.entity_type, target_node.entity_type)
            validate_valid_time(rel_type, valid_time)

        edge = TBoxEdge(
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            valid_time=valid_time,
            permission_tag=permission_tag,
            trace_id=trace_id,
        )

        with self._lock:
            # 唯一归属公理 / 基数约束
            if self.meta["axiom_checks_enabled"]:
                validate_belong_to_uniqueness(self.edges, edge)
                validate_visit_cardinality(self.edges, edge)
            self.edges.append(edge)
            self.meta["edge_count"] = len(self.edges)
        return edge

    def get_edges(
        self,
        rel_type: Optional[RelType] = None,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        time_window: Optional[Tuple[Optional[str], Optional[str]]] = None,
    ) -> List[TBoxEdge]:
        """查询边，支持按关系类型/源/目标/时间窗口过滤。"""
        with self._lock:
            result = []
            for e in self.edges:
                if rel_type and e.rel_type != rel_type:
                    continue
                if source_id and e.source_id != source_id:
                    continue
                if target_id and e.target_id != target_id:
                    continue
                if time_window:
                    if not _is_within_window(e.valid_time, time_window):
                        continue
                result.append(e)
            return result

    def get_outgoing_edges(
        self,
        node_id: str,
        rel_type: Optional[RelType] = None,
        time_window: Optional[Tuple[Optional[str], Optional[str]]] = None,
    ) -> List[TBoxEdge]:
        """获取某节点的出边。"""
        return self.get_edges(rel_type=rel_type, source_id=node_id, time_window=time_window)

    def get_incoming_edges(
        self,
        node_id: str,
        rel_type: Optional[RelType] = None,
        time_window: Optional[Tuple[Optional[str], Optional[str]]] = None,
    ) -> List[TBoxEdge]:
        """获取某节点的入边。"""
        return self.get_edges(rel_type=rel_type, target_id=node_id, time_window=time_window)

    # ── 图构建与同步 ──────────────────────────────────────

    def clear(self) -> None:
        """清空图（用于重建）。"""
        with self._lock:
            self.nodes.clear()
            self.edges.clear()
            self.meta["node_count"] = 0
            self.meta["edge_count"] = 0

    def build_from_store(self, store) -> None:
        """从现有 Store 全量构建内存对象图。

        构建顺序：
        1. 先添加所有节点（实体实例）
        2. 再添加所有边（关系实例），带 TBox 公理校验

        映射规则（对齐 Store 实际数据结构）：
        - store.users (role=attending/mdt_expert/nurse/readonly) → Doctor/Nurse 节点
        - store.patients → Patient 节点
        - store.departments → Department 节点（name 字段 → dept_name）
        - store.buildings → Room 节点（building->floor->room 层级结构）
        - PatientState.bookings → VisitRecord 节点
        - PatientState.emr_main.reports → ExamReport 节点
        - 医生-科室映射 → work_in 边
        - 科室-房间映射 → locate_in 边
        - 患者-就诊映射 → has_visit 边
        - 就诊-报告映射 → generate 边
        - 报告-患者映射 → belong_to 边
        - 就诊-房间映射 → execute_in 边
        """
        self.clear()

        # ── 1. Department 节点 ──────────────────────────
        # 同时维护 name → dept_id 映射（用于 work_in 边查找）
        dept_name_to_id: Dict[str, str] = {}
        for dept in store.departments.values():
            dept_id = dept.get("dept_id", "")
            dept_name = dept.get("name", "") or dept.get("dept_name", "")
            self.add_node(TBoxNode(
                node_id=dept_id,
                entity_type=EntityType.DEPARTMENT,
                data={
                    "dept_id": dept_id,
                    "dept_name": dept_name,
                    "category": dept.get("category", "outpatient"),
                },
            ))
            if dept_name:
                dept_name_to_id[dept_name] = dept_id

        # ── 2. Room 节点（从 buildings 派生） ──────────
        # room_full_key → room_id 映射，同时建立 locate_in 边
        room_key_to_id: Dict[str, str] = {}
        if hasattr(store, "buildings"):
            for bld in store.buildings.values():
                building_name = bld.get("name", "")
                for floor in bld.get("floors", []):
                    floor_name = floor.get("name", "")
                    for room in floor.get("rooms", []):
                        room_id = room.get("room_id", "") or f"{bld.get('building_id', '')}-{floor.get('floor_id', '')}-{room.get('name', '')}"
                        r_name = room.get("name", "")
                        r_dept = room.get("dept_name", "")
                        self.add_node(TBoxNode(
                            node_id=room_id,
                            entity_type=EntityType.ROOM,
                            data={
                                "room_id": room_id,
                                "room_name": r_name,
                                "building": building_name,
                                "floor": floor_name,
                                "department": r_dept,
                            },
                        ))
                        # 组合键：楼栋/楼层/房间名 → room_id
                        room_key_to_id[f"{building_name}/{floor_name}/{r_name}"] = room_id
                        # 同时支持仅房间名查找
                        if r_name:
                            room_key_to_id[r_name] = room_id
                        # Department → Room (locate_in)
                        if r_dept and r_dept in dept_name_to_id:
                            self._safe_add_edge(dept_name_to_id[r_dept], room_id, RelType.LOCATE_IN)

        # ── 3. Doctor 节点 + work_in 边 ────────────────
        for user in store.users.values():
            role = user.get("role", "")
            if role in ("attending", "mdt_expert", "readonly"):
                self.add_node(TBoxNode(
                    node_id=user["user_id"],
                    entity_type=EntityType.DOCTOR,
                    data={
                        "doctor_id": user["user_id"],
                        "doctor_name": user.get("name", ""),
                        "title": user.get("title", ""),
                        "avatar": user.get("avatar", ""),
                        "role": role,
                    },
                ))
                # work_in 边：通过 department 名称查找 dept_id
                dept_name = user.get("department", "")
                if dept_name and dept_name in dept_name_to_id:
                    self._safe_add_edge(user["user_id"], dept_name_to_id[dept_name], RelType.WORK_IN)
            elif role == "nurse":
                self.add_node(TBoxNode(
                    node_id=user["user_id"],
                    entity_type=EntityType.NURSE,
                    data={
                        "nurse_id": user["user_id"],
                        "nurse_name": user.get("name", ""),
                        "role": role,
                    },
                ))

        # ── 4. Patient 节点 ──────────────────────────
        for pat in store.patients.values():
            self.add_node(TBoxNode(
                node_id=pat["patient_id"],
                entity_type=EntityType.PATIENT,
                data={
                    "patient_id": pat["patient_id"],
                    "patient_name": pat.get("patient_name", ""),
                    "gender": pat.get("gender", ""),
                    "age": pat.get("age", 0),
                    "patient_no": pat.get("patient_no", ""),
                    "id_card": pat.get("id_card", ""),
                },
            ))

        # ── 5. ExamItem 节点 ──────────────────────────
        for item in store.exam_items.values():
            item_code = item.get("code", "") or item.get("item_code", "")
            item_name = item.get("name", "") or item.get("item_name", "")
            item_id = item.get("item_id", item_code)
            self.add_node(TBoxNode(
                node_id=item_id,
                entity_type=EntityType.EXAM_ITEM,
                data={
                    "item_code": item_code,
                    "item_name": item_name,
                    "category": item.get("category", ""),
                    "spec": item.get("spec", ""),
                },
            ))

        # ── 6. VisitRecord 节点（从 bookings 派生） ────
        for pat_id, pat in store.patients.items():
            for booking in pat.get("bookings", []):
                booking_id = booking.get("booking_id", "")
                if not booking_id:
                    continue
                start_time = booking.get("start_time", "") or booking.get("slot_date", "")
                end_time = booking.get("end_time") or None
                self.add_node(TBoxNode(
                    node_id=booking_id,
                    entity_type=EntityType.VISIT_RECORD,
                    data={
                        "visit_id": booking_id,
                        "patient_id": pat_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "status": booking.get("status", "upcoming"),
                        "doctor_id": booking.get("doctor_id", ""),
                        "doctor_name": booking.get("doctor_name", ""),
                        "dept_id": booking.get("department", ""),
                        "room_id": booking.get("room_name", ""),
                        "channel": booking.get("channel", ""),
                    },
                ))
                visit_window = (start_time, end_time) if start_time else None
                # Patient → VisitRecord (has_visit)
                self._safe_add_edge(pat_id, booking_id, RelType.HAS_VISIT, valid_time=visit_window)

                # VisitRecord → Room (execute_in)
                bk = booking.get('building_name', '')
                fl = booking.get('floor_name', '')
                rm = booking.get('room_name', '')
                if bk and fl and rm:
                    full_key = f"{bk}/{fl}/{rm}"
                    if full_key in room_key_to_id:
                        self._safe_add_edge(booking_id, room_key_to_id[full_key], RelType.EXECUTE_IN, valid_time=visit_window)
                    elif rm in room_key_to_id:
                        self._safe_add_edge(booking_id, room_key_to_id[rm], RelType.EXECUTE_IN, valid_time=visit_window)

                # OrderRecord 节点（从 check_tasks + orders 派生）
                for task in pat.get("check_tasks", []):
                    task_id = task.get("task_id", "")
                    self.add_node(TBoxNode(
                        node_id=task_id,
                        entity_type=EntityType.ORDER_RECORD,
                        data={
                            "order_id": task_id,
                            "patient_id": pat_id,
                            "visit_id": booking_id,
                            "order_type": task.get("task_type", ""),
                            "order_time": task.get("created_at", start_time),
                        },
                    ))
                    # 医嘱开立项目
                    item_code = task.get("item_code", "") or task.get("task_type", "")
                    if item_code in self.nodes and self.nodes[item_code].entity_type == EntityType.EXAM_ITEM:
                        self._safe_add_edge(task_id, item_code, RelType.ORDER_ITEM)

        # ── 7. ExamReport 节点 ─────────────────────────
        for pat_id, pat in store.patients.items():
            emr = pat.get("emr_main", {})
            reports = emr.get("reports", []) if isinstance(emr, dict) else []
            for report in reports:
                report_id = report.get("report_id", "")
                visit_id = report.get("visit_id", "")
                report_time = report.get("report_time", "")
                self.add_node(TBoxNode(
                    node_id=report_id,
                    entity_type=EntityType.EXAM_REPORT,
                    data={
                        "report_id": report_id,
                        "patient_id": pat_id,
                        "visit_id": visit_id,
                        "report_type": report.get("report_type", ""),
                        "content": report.get("content", ""),
                        "report_time": report_time,
                        "status": report.get("status", "finalized"),
                    },
                ))
                report_window = (report_time, None) if report_time else None
                # VisitRecord → ExamReport (generate)
                if visit_id and visit_id in self.nodes:
                    self._safe_add_edge(visit_id, report_id, RelType.GENERATE, valid_time=report_window)
                # ExamReport → Patient (belong_to, 长期有效)
                self._safe_add_edge(report_id, pat_id, RelType.BELONG_TO, valid_time=None)

        self.meta["last_sync"] = _now()

    def _safe_add_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelType,
        valid_time: Optional[Tuple[str, str]] = None,
    ) -> None:
        """安全添加边：跳过节点不存在的情况（静默失败，不抛异常）。

        主要用于 build_from_store 阶段，部分节点可能尚未构建或不存在。
        """
        if source_id not in self.nodes or target_id not in self.nodes:
            return
        try:
            self.add_edge(source_id, target_id, rel_type, valid_time=valid_time)
        except AxiomViolation:
            # 构建阶段允许跳过冲突（如同一 ExamReport 已有归属）
            pass

    def sync_from_store(self, store) -> List[str]:
        """增量同步：检查 Store 中新增的实体和关系，添加到图中。

        返回本次同步新增的节点 ID 列表。
        """
        new_nodes = []
        existing_node_ids = set(self.nodes.keys())

        # 检查新增 Patient
        for pat_id, pat in store.patients.items():
            if pat_id not in existing_node_ids:
                self.add_node(TBoxNode(
                    node_id=pat_id,
                    entity_type=EntityType.PATIENT,
                    data={
                        "patient_id": pat_id,
                        "patient_name": pat.get("patient_name", ""),
                        "gender": pat.get("gender", ""),
                        "age": pat.get("age", 0),
                    },
                ))
                new_nodes.append(pat_id)

        # 检查新增 Doctor
        for doc_id, doc in store.doctors.items():
            if doc_id not in existing_node_ids:
                self.add_node(TBoxNode(
                    node_id=doc_id,
                    entity_type=EntityType.DOCTOR,
                    data={
                        "doctor_id": doc_id,
                        "doctor_name": doc.get("doctor_name", ""),
                        "title": doc.get("title", ""),
                    },
                ))
                new_nodes.append(doc_id)

        self.meta["last_sync"] = _now()
        return new_nodes

    # ── 统计信息 ──────────────────────────────────────

    def get_stats(self) -> dict:
        """获取图谱统计信息。"""
        node_type_counts: Dict[str, int] = {}
        for n in self.nodes.values():
            t = n.entity_type.value
            node_type_counts[t] = node_type_counts.get(t, 0) + 1

        rel_type_counts: Dict[str, int] = {}
        for e in self.edges:
            r = e.rel_type.value
            rel_type_counts[r] = rel_type_counts.get(r, 0) + 1

        return {
            "version": self.meta["version"],
            "last_sync": self.meta["last_sync"],
            "node_count": self.meta["node_count"],
            "edge_count": self.meta["edge_count"],
            "node_type_distribution": node_type_counts,
            "rel_type_distribution": rel_type_counts,
        }


# ── 全局单例 ──────────────────────────────────────────

_ograph_instance: Optional[OGraph] = None


def get_ograph() -> OGraph:
    """获取 OGraph 全局单例。"""
    global _ograph_instance
    if _ograph_instance is None:
        _ograph_instance = OGraph()
    return _ograph_instance


def reset_ograph() -> OGraph:
    """重置 OGraph（用于测试或重建）。"""
    global _ograph_instance
    _ograph_instance = OGraph()
    return _ograph_instance
