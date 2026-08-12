"""医疗轻量 OAG 底座 — TBox 本体规范（Schema 层）。

本模块定义：
1. TBox 实体类枚举、关系类型枚举
2. TBox 固定关系元数据（源类→目标类、时态属性）
3. TBox 核心公理校验函数（代码层强制实现，不依赖 OWL 推理机）
4. ABox 节点/边数据结构定义

设计原则：
- 轻量化：不引入 Neo4j/OWL 推理机，纯内存数据结构 + Python 校验
- 业务语义固化：关系类型和约束不可运行时动态修改
- 时态优先：所有关系带 valid_time，查询强制时间窗口
- 不做医学知识图谱：仅建模业务对象，二期再扩展疾病/症状/药理
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ============================================================
# 1. TBox 实体类枚举
# ============================================================

class EntityType(str, Enum):
    """TBox 固定实体类（Schema 层）。"""

    # Person 系列
    PATIENT = "Patient"
    DOCTOR = "Doctor"
    NURSE = "Nurse"

    # Space 系列
    DEPARTMENT = "Department"
    ROOM = "Room"

    # MedicalFlow 系列
    VISIT_RECORD = "VisitRecord"
    EXAM_REPORT = "ExamReport"
    EXAM_ITEM = "ExamItem"
    ORDER_RECORD = "OrderRecord"


# 实体类命名空间分组
ENTITY_NAMESPACE = {
    EntityType.PATIENT: "Person",
    EntityType.DOCTOR: "Person",
    EntityType.NURSE: "Person",
    EntityType.DEPARTMENT: "Space",
    EntityType.ROOM: "Space",
    EntityType.VISIT_RECORD: "MedicalFlow",
    EntityType.EXAM_REPORT: "MedicalFlow",
    EntityType.EXAM_ITEM: "MedicalFlow",
    EntityType.ORDER_RECORD: "MedicalFlow",
}


# 实体类核心属性（最小集，不含扩展属性）
ENTITY_REQUIRED_FIELDS: Dict[EntityType, List[str]] = {
    EntityType.PATIENT: ["patient_id", "patient_name"],
    EntityType.DOCTOR: ["doctor_id", "doctor_name"],
    EntityType.NURSE: ["nurse_id", "nurse_name"],
    EntityType.DEPARTMENT: ["dept_id", "dept_name"],
    EntityType.ROOM: ["room_id", "room_name"],
    EntityType.VISIT_RECORD: ["visit_id", "patient_id", "start_time"],
    EntityType.EXAM_REPORT: ["report_id", "patient_id", "visit_id", "report_type"],
    EntityType.EXAM_ITEM: ["item_code", "item_name"],
    EntityType.ORDER_RECORD: ["order_id", "patient_id", "visit_id"],
}


# ============================================================
# 2. TBox 关系类型枚举 + 元数据
# ============================================================

class RelType(str, Enum):
    """TBox 固定关系类型（对象关系，强业务语义）。"""

    WORK_IN = "work_in"           # Doctor → Department（任职科室）
    LOCATE_IN = "locate_in"       # Department → Room（科室对应诊室）
    HAS_VISIT = "has_visit"       # Patient → VisitRecord（患者拥有就诊记录）
    GENERATE = "generate"         # VisitRecord → ExamReport（就诊产生报告）
    BELONG_TO = "belong_to"       # ExamReport → Patient（报告唯一归属患者）
    EXECUTE_IN = "execute_in"     # VisitRecord → Room（就诊发生诊室）
    ORDER_ITEM = "order_item"     # OrderRecord → ExamItem（医嘱开立项目）


# 关系元数据：源类→目标类、时态属性、业务说明
REL_METADATA: Dict[RelType, dict] = {
    RelType.WORK_IN: {
        "source_type": EntityType.DOCTOR,
        "target_type": EntityType.DEPARTMENT,
        "time_sensitive": True,       # 每日排班动态生效
        "description": "医生任职科室，含时效性",
    },
    RelType.LOCATE_IN: {
        "source_type": EntityType.DEPARTMENT,
        "target_type": EntityType.ROOM,
        "time_sensitive": False,      # 长期有效
        "description": "科室对应诊室",
    },
    RelType.HAS_VISIT: {
        "source_type": EntityType.PATIENT,
        "target_type": EntityType.VISIT_RECORD,
        "time_sensitive": True,       # 就诊时段
        "description": "患者拥有就诊记录",
    },
    RelType.GENERATE: {
        "source_type": EntityType.VISIT_RECORD,
        "target_type": EntityType.EXAM_REPORT,
        "time_sensitive": True,       # 报告生成时间
        "description": "就诊产生报告",
    },
    RelType.BELONG_TO: {
        "source_type": EntityType.EXAM_REPORT,
        "target_type": EntityType.PATIENT,
        "time_sensitive": False,      # 长期有效
        "description": "报告唯一归属患者",
    },
    RelType.EXECUTE_IN: {
        "source_type": EntityType.VISIT_RECORD,
        "target_type": EntityType.ROOM,
        "time_sensitive": True,       # 就诊时段
        "description": "就诊发生诊室",
    },
    RelType.ORDER_ITEM: {
        "source_type": EntityType.ORDER_RECORD,
        "target_type": EntityType.EXAM_ITEM,
        "time_sensitive": True,       # 开立时间
        "description": "医嘱开立项目",
    },
}


# ============================================================
# 3. ABox 数据结构定义
# ============================================================

class TBoxNode:
    """ABox 节点（实体实例）。"""

    def __init__(
        self,
        node_id: str,
        entity_type: EntityType,
        data: dict,
        create_time: Optional[str] = None,
    ):
        self.node_id = node_id
        self.entity_type = entity_type
        self.data = data
        self.create_time = create_time or _now()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "type": self.entity_type.value,
            "data": self.data,
            "create_time": self.create_time,
        }


class TBoxEdge:
    """ABox 边（关系实例）。"""

    def __init__(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelType,
        valid_time: Optional[Tuple[str, str]] = None,
        create_time: Optional[str] = None,
        permission_tag: str = "all",
        trace_id: Optional[str] = None,
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type
        self.valid_time = valid_time          # (start_iso, end_iso) 或 None=长期有效
        self.create_time = create_time or _now()
        self.permission_tag = permission_tag
        self.trace_id = trace_id

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rel_type": self.rel_type.value,
            "valid_time": self.valid_time,
            "create_time": self.create_time,
            "permission_tag": self.permission_tag,
            "trace_id": self.trace_id,
        }


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ============================================================
# 4. TBox 公理校验函数（代码层强制实现）
# ============================================================

class AxiomViolation(Exception):
    """公理违反异常。"""

    def __init__(self, axiom_name: str, message: str):
        self.axiom_name = axiom_name
        super().__init__(f"[TBox公理违反] {axiom_name}: {message}")


def validate_entity_fields(entity_type: EntityType, data: dict) -> None:
    """校验实体核心属性（TBox Schema 约束）。

    缺少必填字段抛出 AxiomViolation。
    """
    required = ENTITY_REQUIRED_FIELDS.get(entity_type, [])
    missing = [f for f in required if f not in data or not data[f]]
    if missing:
        raise AxiomViolation(
            "实体属性完备性",
            f"{entity_type.value} 缺少必填字段: {missing}",
        )


def validate_rel_type(rel_type: RelType, source_type: EntityType, target_type: EntityType) -> None:
    """校验关系类型的源类→目标类是否符合 TBox 定义。"""
    meta = REL_METADATA.get(rel_type)
    if meta is None:
        raise AxiomViolation("关系类型合法性", f"未知关系类型: {rel_type.value}")
    if meta["source_type"] != source_type:
        raise AxiomViolation(
            "关系源类约束",
            f"关系 {rel_type.value} 要求源类为 {meta['source_type'].value}，实际为 {source_type.value}",
        )
    if meta["target_type"] != target_type:
        raise AxiomViolation(
            "关系目标类约束",
            f"关系 {rel_type.value} 要求目标类为 {meta['target_type'].value}，实际为 {target_type.value}",
        )


def validate_valid_time(rel_type: RelType, valid_time: Optional[Tuple[str, str]]) -> None:
    """校验关系的时态属性。

    时态敏感关系必须带 valid_time；非时态关系可为 None（长期有效）。
    """
    meta = REL_METADATA.get(rel_type, {})
    if meta.get("time_sensitive") and valid_time is None:
        raise AxiomViolation(
            "时态核心公理",
            f"关系 {rel_type.value} 是时态敏感关系，必须提供 valid_time=[start, end]",
        )


def validate_belong_to_uniqueness(existing_edges: List[TBoxEdge], new_edge: TBoxEdge) -> None:
    """唯一归属公理：一份 ExamReport 恰好 1 个 Patient。

    如果某 ExamReport 已有 belong_to 边，不允许再创建新的 belong_to 边。
    """
    if new_edge.rel_type != RelType.BELONG_TO:
        return
    for e in existing_edges:
        if (
            e.rel_type == RelType.BELONG_TO
            and e.source_id == new_edge.source_id
        ):
            raise AxiomViolation(
                "唯一归属公理",
                f"ExamReport {new_edge.source_id} 已归属 Patient {e.target_id}，禁止重复归属",
            )


def validate_visit_cardinality(existing_edges: List[TBoxEdge], new_edge: TBoxEdge) -> None:
    """基数约束：一条 VisitRecord 仅归属一个 Patient（通过 has_visit 边）。

    检查逻辑：如果已有边的 target_id（VisitRecord）与新边相同，说明同一就诊记录被多个患者归属。
    """
    if new_edge.rel_type != RelType.HAS_VISIT:
        return
    for e in existing_edges:
        if (
            e.rel_type == RelType.HAS_VISIT
            and e.target_id == new_edge.target_id  # 同一 VisitRecord 作为 target
        ):
            raise AxiomViolation(
                "基数约束",
                f"VisitRecord {new_edge.target_id} 已归属 Patient {e.source_id}，禁止重复归属",
            )


def validate_identity_mutex(doctor_user_id: str, patient_user_id: str) -> None:
    """身份互斥公理：同一 user_id 不可同时为 Doctor 和 Patient。

    此校验在用户注册/角色变更时调用。
    """
    if doctor_user_id == patient_user_id:
        raise AxiomViolation(
            "身份互斥公理",
            f"用户 {doctor_user_id} 不可同时为医生和患者",
        )


# ============================================================
# 5. 时间窗口工具
# ============================================================

def make_time_window(
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """构造时间窗口。None 表示无边界（慎用）。"""
    return (start, end)


def make_visit_window(visit_start: str, visit_end: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """构造就诊时段时间窗口。"""
    return (visit_start, visit_end)


def _is_within_window(valid_time: Optional[Tuple[str, str]], window: Tuple[Optional[str], Optional[str]]) -> bool:
    """判断边的 valid_time 是否与查询时间窗口有交集。

    - valid_time 为 None（长期有效）→ 始终返回 True
    - window[0] 为 None → 不限制开始
    - window[1] 为 None → 不限制结束
    """
    if valid_time is None:
        return True  # 长期有效关系，对所有时间窗口可见

    v_start, v_end = valid_time
    w_start, w_end = window

    # 边的有效期开始于窗口结束之后 → 无交集
    if w_end and v_start > w_end:
        return False
    # 边的有效期结束于窗口开始之前 → 无交集
    if w_start and v_end and v_end < w_start:
        return False
    # 边的有效期结束于窗口开始之前（边已过期）→ 无交集
    if v_end and w_start and v_end < w_start:
        return False

    return True
