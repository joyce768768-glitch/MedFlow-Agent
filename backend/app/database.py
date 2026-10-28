"""SQLite 持久化底座（M1 · 数据底座层落地）。

业务库：backend/data/medflow_app.db（WAL 模式），与 KG 库
chinese-medical-kg-main/ontology/data/medical_kg.db 物理分离、互不干扰。

架构定位（见 docs/m1-schema-design.md）：
- Store（storage.py）仍是唯一接口层：内存 dict = 读写缓存，170 个方法签名不变；
- 本模块只负责三件事：建表（幂等）、行序列化/反序列化、批量落盘/加载；
- 持久化时机：FastAPI 请求边界统一 flush（main.py 中间件）+ 种子灌完落盘——
  内存仍是运行时真相源，SQLite 是重启恢复的真相源；
- exam_reports / exam_items / mdt_comments / audit_log / notifications /
  treatment_versions / memory_cards 七个集合在 state_json 中剥离，以关系表
  为磁盘唯一真相源（契约 tat_hours 公式可直接对表执行）。

表命名说明：exam_item_dict（检验项目字典）刻意区别于契约 detail 表
exam_items（报告项目明细）——前者是主数据，不进语义契约。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import (
    Column, Integer, Text, create_engine, event,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

# ------------------------------------------------------------------
# 引擎与连接
# ------------------------------------------------------------------
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "medflow_app.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
    poolclass=NullPool,  # 每次 checkout 新建连接，规避线程池共享 SQLite 连接的并发问题
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


Base = declarative_base()


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def loads(raw: Optional[str], default: Any = None) -> Any:
    if raw is None or raw == "":
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# ------------------------------------------------------------------
# A 档 · 医疗流程域（契约对齐，M2 指标直接消费）
# ------------------------------------------------------------------
class PatientRow(Base):
    """患者主表 + PatientState 文档（state_json 不含已剥离的 6 个集合）。"""
    __tablename__ = "patients"

    patient_id = Column(Text, primary_key=True)
    patient_name = Column(Text)
    gender = Column(Text)
    age = Column(Text)
    department = Column(Text)
    status = Column(Text)                    # waiting / in_progress / archived
    hitl_pending = Column(Integer, default=0)
    attending_doctor_ids = Column(Text)      # JSON 数组
    state_json = Column(Text, nullable=False)
    created_at = Column(Text)
    updated_at = Column(Text)


class ExamReportRow(Base):
    """契约 primary 表 exam_reports（源：PatientState.check_tasks）。"""
    __tablename__ = "exam_reports"

    task_id = Column(Text, primary_key=True)
    patient_id = Column(Text, nullable=False, index=True)
    task_type = Column(Text)                 # blood / ct / ultrasound
    task_label = Column(Text)
    status = Column(Text)                    # ordered / pending / done
    ordered_at = Column(Text)                # = CheckTask.created_at（契约 tat_hours 公式列名）
    created_by = Column(Text)
    created_by_name = Column(Text)
    completed_at = Column(Text)
    flag = Column(Text)                      # normal / abnormal / critical
    result_json = Column(Text)
    source = Column(Text, default="flow")    # seed / flow
    created_at = Column(Text)
    updated_at = Column(Text)


class ExamItemRow(Base):
    """契约 detail 表 exam_items（源：result.items 拆行）。"""
    __tablename__ = "exam_items"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Text, nullable=False, index=True)  # → exam_reports.task_id
    code = Column(Text)
    name = Column(Text)
    value_text = Column(Text)
    unit = Column(Text)
    ref_range = Column(Text)
    flag = Column(Text)                      # normal / abnormal / critical
    sort_no = Column(Integer, default=0)


class ExamItemDictRow(Base):
    """检验项目字典（主数据；命名避开契约 detail 表 exam_items）。"""
    __tablename__ = "exam_item_dict"

    item_id = Column(Text, primary_key=True)
    code = Column(Text)
    name = Column(Text)
    category = Column(Text)
    spec = Column(Text)
    ref_range = Column(Text)
    created_at = Column(Text)


# ------------------------------------------------------------------
# B 档 · 主数据与资源（签名列 + extra_json 兜底）
# ------------------------------------------------------------------
class UserRow(Base):
    __tablename__ = "users"

    user_id = Column(Text, primary_key=True)
    username = Column(Text, index=True)
    password = Column(Text)
    name = Column(Text)
    role = Column(Text)
    department = Column(Text)
    title = Column(Text)
    dept_lead = Column(Integer, default=0)
    active = Column(Integer, default=1)
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class PatientUserRow(Base):
    __tablename__ = "patient_users"

    patient_id = Column(Text, primary_key=True)
    patient_name = Column(Text)
    medical_card_number = Column(Text)
    phone = Column(Text)
    gender = Column(Text)
    age = Column(Text)
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class DepartmentRow(Base):
    __tablename__ = "departments"

    dept_id = Column(Text, primary_key=True)
    name = Column(Text)
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class BuildingRow(Base):
    """楼宇主数据：楼层/房间层级整体存 floors_json（低频聚合，不拆表）。"""
    __tablename__ = "buildings"

    building_id = Column(Text, primary_key=True)
    name = Column(Text)
    floors_json = Column(Text)
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class KbEntryRow(Base):
    __tablename__ = "kb_entries"

    kb_id = Column(Text, primary_key=True)
    category = Column(Text)
    title = Column(Text)
    content = Column(Text)
    tags_json = Column(Text)
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class RagDocRow(Base):
    __tablename__ = "rag_docs"

    doc_id = Column(Text, primary_key=True)
    title = Column(Text)
    category = Column(Text)
    content = Column(Text)
    status = Column(Text)
    chunks_json = Column(Text)               # chunks + Mock 向量整体
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class PromptResourceRow(Base):
    __tablename__ = "prompt_resources"

    prompt_id = Column(Text, primary_key=True)
    name = Column(Text)
    content = Column(Text)
    status = Column(Text)
    department = Column(Text)
    bound_agents_json = Column(Text)
    extra_json = Column(Text)                # 含 _history 版本快照 / version / created_by 等
    created_at = Column(Text)
    updated_at = Column(Text)


class SchemaResourceRow(Base):
    __tablename__ = "schema_resources"

    schema_id = Column(Text, primary_key=True)
    name = Column(Text)
    json_schema_text = Column(Text)
    status = Column(Text)
    department = Column(Text)
    bound_agents_json = Column(Text)
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class ModelResourceRow(Base):
    """模型资源池。注意：演示库含明文 api_key，.gitignore 掉 db 文件，不进 Git。"""
    __tablename__ = "model_resources"

    model_id = Column(Text, primary_key=True)
    provider = Column(Text)
    model = Column(Text)
    api_key = Column(Text)
    base_url = Column(Text)
    timeout = Column(Integer, default=30)
    status = Column(Text)
    bound_agents_json = Column(Text)
    extra_json = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)


class KgDeptAliasRow(Base):
    """KG 科室 → 业务科室 别名映射。kg_dept_name 为主键（同名校验级联）。"""
    __tablename__ = "kg_dept_aliases"

    kg_dept_name = Column(Text, primary_key=True)
    business_dept_name = Column(Text)
    note = Column(Text)
    updated_at = Column(Text)


# ------------------------------------------------------------------
# C 档 · 事件 / 会话 / 审计（追加型）
# ------------------------------------------------------------------
class MdtCommentRow(Base):
    __tablename__ = "mdt_comments"

    comment_id = Column(Text, primary_key=True)
    patient_id = Column(Text, nullable=False, index=True)
    author_id = Column(Text)
    author_name = Column(Text)
    author_role = Column(Text)
    content = Column(Text)
    is_adopted = Column(Integer, default=0)
    adopted_by = Column(Text)
    adopted_by_name = Column(Text)
    adopted_at = Column(Text)
    created_at = Column(Text)


class TreatmentVersionRow(Base):
    __tablename__ = "treatment_versions"

    version_id = Column(Text, primary_key=True)
    patient_id = Column(Text, nullable=False, index=True)
    version_no = Column(Integer, default=0)
    content = Column(Text)
    created_by = Column(Text)
    created_by_name = Column(Text)
    created_at = Column(Text)


class AuditLogRow(Base):
    """患者级审计（从 PatientState.audit_log 剥离）。"""
    __tablename__ = "audit_log"

    log_id = Column(Text, primary_key=True)
    patient_id = Column(Text, nullable=False, index=True)
    action = Column(Text)
    actor_id = Column(Text)
    actor_name = Column(Text)
    detail = Column(Text)
    created_at = Column(Text)


class NotificationRow(Base):
    __tablename__ = "notifications"

    notify_id = Column(Text, primary_key=True)
    patient_id = Column(Text, index=True)
    target_user_id = Column(Text, index=True)
    type = Column(Text)
    message = Column(Text)
    read = Column(Integer, default=0)
    created_at = Column(Text)


class SystemAuditRow(Base):
    """跨患者系统审计（后台管理操作）。"""
    __tablename__ = "system_audit_log"

    log_id = Column(Text, primary_key=True)
    operator_id = Column(Text)
    operator_name = Column(Text)
    action = Column(Text)
    entity = Column(Text)
    entity_id = Column(Text)
    before_json = Column(Text)
    after_json = Column(Text)
    created_at = Column(Text)


class PatientEventRow(Base):
    """患者端行为埋点（保留量上限逻辑在 Store 层，落库为追加行）。"""
    __tablename__ = "patient_events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Text, index=True)
    event_type = Column(Text)
    payload_json = Column(Text)
    created_at = Column(Text)


class ChatMessageRow(Base):
    """四类会话统一表：channel ∈ emr / prediction / unified / research。"""
    __tablename__ = "chat_messages"

    msg_id = Column(Text, primary_key=True)
    channel = Column(Text, nullable=False, index=True)
    owner_id = Column(Text, nullable=False, index=True)   # patient_id 或 user_id
    role = Column(Text)
    content = Column(Text)
    extra_json = Column(Text)
    created_at = Column(Text)


class AdoptionRow(Base):
    __tablename__ = "adoption_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    adoption_id = Column(Text, index=True)
    patient_id = Column(Text, index=True)
    agent_type = Column(Text)
    msg_id = Column(Text)
    summary = Column(Text)
    target = Column(Text)
    detail_json = Column(Text)
    created_at = Column(Text)


class MemoryCardRow(Base):
    """L2 医生/患者记忆 + L3 沉淀知识同表：owner_type ∈ doctor / patient / system。"""
    __tablename__ = "memory_cards"

    card_id = Column(Text, primary_key=True)
    owner_type = Column(Text, index=True)
    owner_id = Column(Text, index=True)
    card_type = Column(Text)
    frozen = Column(Integer, default=0)
    card_json = Column(Text, nullable=False)
    created_at = Column(Text)


# ------------------------------------------------------------------
# KV 档
# ------------------------------------------------------------------
class AppKvRow(Base):
    """单例配置统一收口：subagent_config / permission_matrix / agent_config
    / chat_status:{pid} / meta 等。"""
    __tablename__ = "app_kv"

    key = Column(Text, primary_key=True)
    value_json = Column(Text, nullable=False)
    updated_at = Column(Text)


# ------------------------------------------------------------------
# 建表与通用行读写
# ------------------------------------------------------------------
def ensure_schema() -> None:
    """幂等建表（只增不删），模块导入即执行。"""
    Base.metadata.create_all(engine)


ensure_schema()


def upsert(session, row) -> None:
    session.merge(row)


def delete_by_pk(session, model, pk_value) -> None:
    obj = session.get(model, pk_value)
    if obj is not None:
        session.delete(obj)


def delete_all(session, model, patient_id: Optional[str] = None,
              pid_column: str = "patient_id") -> None:
    q = session.query(model)
    if patient_id is not None:
        q = q.filter(getattr(model, pid_column) == patient_id)
    q.delete(synchronize_session=False)


# ------------------------------------------------------------------
# 行 ↔ dict 通用转换（B 档实体域）
# 规则：列名以 _json 结尾（extra_json/state_json/value_json/payload_json 除外）
# 反序列化为同名去后缀 key；json_schema_text → json_schema；extra_json 整体合并。
# ------------------------------------------------------------------
_JSON_SKIP_BASES = {"state", "value", "payload"}


def row_pk(row) -> Any:
    return getattr(row, list(row.__table__.primary_key.columns)[0].name)


def row_to_dict(row) -> dict:
    data: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    for c in row.__table__.columns:
        v = getattr(row, c.key)
        k = c.key
        if k == "extra_json":
            extra = loads(v, {}) or {}
        elif k == "json_schema_text":
            data["json_schema"] = loads(v)
        elif k.endswith("_json"):
            base = k[:-5]
            if base in _JSON_SKIP_BASES:
                continue  # 特殊表（patients/app_kv/patient_events）由调用方处理
            data[base] = loads(v)
        else:
            data[k] = v
    data.update(extra)
    return data
