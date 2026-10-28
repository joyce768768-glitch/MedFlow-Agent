"""Store：进程级单例 + SQLite 持久化（M1 数据底座层落地）。

架构定位（M1 重构后，见 docs/m1-schema-design.md）：
- 内存 dict = 读写缓存（运行时真相源），SQLite（backend/data/medflow_app.db）
  = 重启恢复真相源——「内存 Store 改缓存层」；
- 170 个方法签名与 dict 属性全部保留，routers / graph / subagents 零改动；
- 持久化时机：main.py 请求边界中间件统一 persist_all() + 种子灌完落盘；
- patients.state_json 剥离 6 个集合（check_tasks / mdt_comments / notify_queue /
  audit_log / treatment_versions / memory_cards），磁盘上以关系表为唯一真相源，
  加载时回填——契约 tat_hours 公式可直接对 exam_reports 表执行。

提供进程级单例 Store：
- users: 用户表（含角色、密码哈希占位）
- patients: patient_id -> PatientState
- subagent_config: 全局 SubAgent 开关（配置页可在线切换）
- notifications: user_id -> [NotifyEvent]（站内通知索引）

设计原则：动作权限与数据范围解耦；所有写操作落 audit_log。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app import database as db
from app.config import settings
from app.graph.state import (
    AuditLogEntry,
    CheckTask,
    MdtComment,
    MdtInvitation,
    NotifyEvent,
    PatientState,
    TreatmentVersion,
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# 权限矩阵：角色 × 动作开关，按域分组（临床 / 后台管理 / 患者端）
PERMISSION_ROLES = ["attending", "mdt_expert", "nurse", "readonly", "lab_tech", "imaging_tech"]
# —— 动作分组（权限管理页按域显示） ——
CLINICAL_ACTIONS = [
    "can_view_emr", "can_edit_emr", "can_lock_emr", "can_generate_ai",
    "can_open_check", "can_invite_mdt", "can_adopt_comment", "can_submit_comment",
    "can_view_history", "can_view_mdt", "can_view_check",
]
ADMIN_ACTIONS = [
    "manage_users", "manage_departments", "manage_kb",
    "manage_agents", "manage_permissions", "view_audit",
]
PATIENT_ACTIONS = [
    "can_self_triage", "can_book_appointment", "can_view_own_report",
    "can_view_own_emr", "can_consult", "can_pay",
]
# 向后兼容：现有鉴权代码依赖 PERMISSION_ACTIONS（临床动作集合）
PERMISSION_ACTIONS = CLINICAL_ACTIONS
# 所有角色（权限矩阵行，含后台 / 患者角色）
ADMIN_ROLES = ["admin", "platform_admin"]
ALL_PERMISSION_ROLES = PERMISSION_ROLES + ADMIN_ROLES + ["patient"]
ALL_PERMISSION_ACTIONS = CLINICAL_ACTIONS + ADMIN_ACTIONS + PATIENT_ACTIONS
# 角色分组（供前端权限页分域 Tab 渲染）
ROLE_GROUPS = {
    "clinical": PERMISSION_ROLES,
    "admin": ADMIN_ROLES,
    "patient": ["patient"],
}
ACTION_GROUPS = {
    "clinical": CLINICAL_ACTIONS,
    "admin": ADMIN_ACTIONS,
    "patient": PATIENT_ACTIONS,
}
# 角色 → 适用动作域（不适用域的格子前端灰禁、后端忽略）
ROLE_ACTION_DOMAINS = {
    "attending": ["clinical"], "mdt_expert": ["clinical"],
    "nurse": ["clinical"], "readonly": ["clinical"], "lab_tech": ["clinical"],
    "imaging_tech": ["clinical"],
    "admin": ["admin"], "platform_admin": ["admin"],
    "patient": ["patient"],
}

# 知识库分类
KB_CATEGORIES = {
    "guide": "临床指南/诊疗常规",
    "soap_template": "SOAP 病历模板",
    "drug_dict": "药品/检查项字典",
    "mdt_template": "MDT 会诊模板",
}


def default_permission_matrix() -> Dict[str, Dict[str, bool]]:
    """默认权限矩阵：角色 × 动作（按临床 / 后台 / 患者三域）。

    - 临床角色（attending/mdt_expert/nurse/readonly）：仅配置临床动作；
    - 后台角色（admin/platform_admin）：拥有全部后台管理动作，无临床/患者权限；
    - 患者角色（patient）：拥有全部患者端动作，无临床/后台权限。
    """

    def _row(clinical: Dict[str, bool], admin: Dict[str, bool], patient: Dict[str, bool]) -> Dict[str, bool]:
        row: Dict[str, bool] = {}
        row.update({a: bool(clinical.get(a, False)) for a in CLINICAL_ACTIONS})
        row.update({a: bool(admin.get(a, False)) for a in ADMIN_ACTIONS})
        row.update({a: bool(patient.get(a, False)) for a in PATIENT_ACTIONS})
        return row

    _no_admin = {a: False for a in ADMIN_ACTIONS}
    _no_patient = {a: False for a in PATIENT_ACTIONS}
    _no_clinical = {a: False for a in CLINICAL_ACTIONS}
    _all_admin = {a: True for a in ADMIN_ACTIONS}
    _all_patient = {a: True for a in PATIENT_ACTIONS}
    _all_clinical = {a: True for a in CLINICAL_ACTIONS}

    return {
        "attending": _row({
            "can_view_emr": True, "can_edit_emr": True, "can_lock_emr": True,
            "can_generate_ai": True, "can_open_check": True, "can_invite_mdt": True,
            "can_adopt_comment": True, "can_submit_comment": False,
            "can_view_history": True, "can_view_mdt": True, "can_view_check": True,
        }, _no_admin, _no_patient),
        "mdt_expert": _row({
            "can_view_emr": True, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": True,
            "can_view_history": True, "can_view_mdt": True, "can_view_check": True,
        }, _no_admin, _no_patient),
        "nurse": _row({
            "can_view_emr": False, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": False,
            "can_view_history": False, "can_view_mdt": False, "can_view_check": True,
        }, _no_admin, _no_patient),
        "readonly": _row({
            "can_view_emr": True, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": False,
            "can_view_history": True, "can_view_mdt": True, "can_view_check": True,
        }, _no_admin, _no_patient),
        "lab_tech": _row({
            "can_view_emr": False, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": False,
            "can_view_history": False, "can_view_mdt": False, "can_view_check": True,
        }, _no_admin, _no_patient),
        "imaging_tech": _row({
            "can_view_emr": False, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": False,
            "can_view_history": False, "can_view_mdt": False, "can_view_check": True,
        }, _no_admin, _no_patient),
        # 后台管理角色：拥有全部后台动作 + 全部临床权限（产品阶段方便用 admin 单号测所有功能，后续再回收临床权限）
        "admin": _row(_all_clinical, _all_admin, _no_patient),
        "platform_admin": _row(_all_clinical, _all_admin, _no_patient),
        # 患者角色：拥有全部患者端动作，无临床/后台权限
        "patient": _row(_no_clinical, _no_admin, _all_patient),
    }


class Store:
    """进程内单例存储（线程安全）。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.users: Dict[str, dict] = {}
        self.patients: Dict[str, PatientState] = {}
        self.subagent_config: dict = {
            "enable_emr_subagent": bool(settings.default_enable_emr_subagent),
            "enable_lab_subagent": bool(settings.default_enable_lab_subagent),
        }
        # 后台管理：科室 / 知识库 / 权限矩阵
        self.departments: Dict[str, dict] = {}
        self._kg_dept_aliases: Dict[str, dict] = {}   # KG 科室 → 业务科室别名映射
        self.kb_entries: Dict[str, dict] = {}
        self.permission_matrix: Dict[str, Dict[str, bool]] = default_permission_matrix()
        # 后台扩展：主数据 / RAG文档 / 系统审计 / Agent灰度配置
        self.buildings: Dict[str, dict] = {}           # 楼宇(含楼层/房间)
        self.exam_items: Dict[str, dict] = {}           # 检验/检查项目字典
        self.rag_docs: Dict[str, dict] = {}             # RAG文档(含chunks+Mock向量)
        self.system_audit_log: List[dict] = []          # 系统审计日志(跨患者)
        self.agent_config: dict = {                     # Agent能力灰度配置 + 模型配置 + PromptResource + SchemaResource
            "patient_triage_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                # —— v2 版本化资源引用（优先使用） ——
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                # —— @deprecated 旧版内联字段，兼容降级用 ——
                "prompt": "",
                "output_schema": "",
            },
            "emr_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                "prompt": "",
                "output_schema": "",
            },
            "imaging_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                "prompt": "",
                "output_schema": "",
            },
            # —— 检验报告 Agent：解读化验/检验结果，标注异常值与临床意义 ——
            "lab_report_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                "prompt": "",
                "output_schema": "",
            },
            # —— 诊断 Agent：整合检查/影像/预测，给出鉴别诊断与初步结论 ——
            "diagnosis_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                "prompt": "",
                "output_schema": "",
            },
            # —— 疾病预测 Agent：基于症状实体做 KG 检索 + 概率排序 ——
            "prediction_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                "prompt": "",
                "output_schema": "",
            },
            # —— 治疗方案 Agent：基于确诊结果生成用药/随访/教育方案草稿 ——
            "treatment_plan_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                "prompt": "",
                "output_schema": "",
            },
            # —— 用户问诊 Agent：医患对话中的问诊引导与结构化提取 ——
            "consultation_agent": {
                "global": True, "hospitals": {},
                "model_config": {
                    "provider": "mock", "enable_real": 0,
                    "model": "", "base_url": "", "api_key": "",
                    "timeout": 30,
                },
                "prompt_resource_id": "",
                "schema_resource_id": "",
                "model_resource_id": "",
                "prompt": "",
                "output_schema": "",
            },
        }
        self.patient_users: Dict[str, dict] = {}  # 患者端登录用户（patient_id -> info）
        self.patient_events: List[dict] = []       # 患者端行为埋点事件
        self.emr_chat_sessions: Dict[str, List[dict]] = {}  # 病历对话历史（patient_id -> [msg]）
        self.prediction_chat_sessions: Dict[str, List[dict]] = {}  # 疾病预测对话历史（patient_id -> [msg]）

        # —— 统一对话（豆包式：多 Agent 共享一个会话）——
        self.unified_chat_sessions: Dict[str, List[dict]] = {}  # patient_id -> [msg]
        self.unified_adoptions: Dict[str, List[dict]] = {}     # patient_id -> [adoption_record]
        self.chat_status: Dict[str, dict] = {}  # patient_id -> {steps:[{key,label,status,detail}], updated_at}

        # —— 记忆模块（L2 主体记忆 + L3 沉淀知识 + 研究对话）——
        self.doctor_memory: Dict[str, List[dict]] = {}        # 医生 L2 记忆（user_id -> [MemoryCard]）
        self.crystallized_knowledge: List[dict] = []           # L3 沉淀知识（去标识化，全院共享）
        self.research_chat_sessions: Dict[str, List[dict]] = {}  # 研究模式对话历史（user_id -> [msg]）

        # —— Prompt/OutputSchema 资源管理（版本化，解耦 SubAgent） ——
        self.prompt_resources: Dict[str, dict] = {}
        self.schema_resources: Dict[str, dict] = {}

        # —— 模型资源管理（独立模型池，Agent 可引用） ——
        self.model_resources: Dict[str, dict] = {}

        # —— 从 .env 自动配置 LLM（避免重启后手动注册模型丢失） ——
        if settings.llm_api_key:
            _deepseek_cfg = {
                "provider": "openai_compatible",
                "enable_real": 1,
                "model": settings.llm_model or "deepseek-chat",
                "base_url": settings.llm_base_url or "https://api.deepseek.com/v1",
                "api_key": settings.llm_api_key,
                "timeout": 30,
            }
            for _ak in ("patient_triage_agent", "emr_agent", "imaging_agent",
                        "lab_report_agent", "diagnosis_agent",
                        "prediction_agent",
                        "treatment_plan_agent", "consultation_agent"):
                if _ak in self.agent_config:
                    self.agent_config[_ak]["model_config"] = dict(_deepseek_cfg)

        # —— M1：启动时从 SQLite 全量加载进内存缓存（DB 有数据则跳过种子） ——
        self._db_loaded: bool = False
        self._db_loaded = self._load_from_db()

    # ==================== 持久化（M1 · 数据底座层） ====================
    # state_json 剥离集合：磁盘上以关系表为唯一真相源，_load_from_db 时回填
    _STRIP_KEYS = ("check_tasks", "mdt_comments", "notify_queue",
                   "audit_log", "treatment_versions", "memory_cards")

    @staticmethod
    def _exam_report_flag(result) -> Optional[str]:
        """报告级 flag：任一 item critical → critical；有异常 → abnormal；否则 normal。"""
        if not isinstance(result, dict):
            return None
        items = result.get("items") or []
        flags = [str(i.get("abnormal", "normal")).lower() for i in items if isinstance(i, dict)]
        if any(f == "critical" for f in flags):
            return "critical"
        if result.get("abnormal_count") or any(f not in ("normal", "") for f in flags):
            return "abnormal"
        return "normal"

    @staticmethod
    def _item_flag(abnormal) -> str:
        f = str(abnormal or "normal").lower()
        return "critical" if f == "critical" else ("abnormal" if f not in ("normal", "") else "normal")

    def _load_from_db(self) -> bool:
        """启动时从 SQLite 全量加载进内存缓存。返回 True=已有数据（跳过种子）。"""
        with Session(db.engine) as s:
            kv = {r.key: db.loads(r.value_json) for r in s.query(db.AppKvRow).all()}
            if not kv.get("meta.seeded"):
                return False
            self.subagent_config.update(kv.get("subagent_config") or {})
            if kv.get("permission_matrix"):
                self.permission_matrix = kv["permission_matrix"]
            if kv.get("agent_config"):
                self.agent_config = kv["agent_config"]
            self.chat_status = kv.get("chat_status") or {}

            def rows(model):
                return {db.row_pk(r): db.row_to_dict(r) for r in s.query(model).all()}

            self.users = rows(db.UserRow)
            self.patient_users = rows(db.PatientUserRow)
            self.departments = rows(db.DepartmentRow)
            self.buildings = rows(db.BuildingRow)
            self.kb_entries = rows(db.KbEntryRow)
            self.exam_items = rows(db.ExamItemDictRow)
            self.rag_docs = rows(db.RagDocRow)
            self.prompt_resources = rows(db.PromptResourceRow)
            self.schema_resources = rows(db.SchemaResourceRow)
            self.model_resources = rows(db.ModelResourceRow)
            self._kg_dept_aliases = rows(db.KgDeptAliasRow)

            # 会话（channel, owner_key）→ [msg]
            chats: Dict[tuple, List[dict]] = {}
            for r in s.query(db.ChatMessageRow).all():
                msg = {"msg_id": r.msg_id, "role": r.role, "content": r.content,
                       "timestamp": r.created_at}
                msg.update(db.loads(r.extra_json, {}))
                chats.setdefault((r.channel, r.owner_id), []).append(msg)
            self.emr_chat_sessions = {k[1]: v for k, v in chats.items() if k[0] == "emr"}
            self.prediction_chat_sessions = {k[1]: v for k, v in chats.items() if k[0] == "prediction"}
            self.unified_chat_sessions = {k[1]: v for k, v in chats.items() if k[0] == "unified"}
            self.research_chat_sessions = {k[1]: v for k, v in chats.items() if k[0] == "research"}

            self.unified_adoptions = {}
            for r in s.query(db.AdoptionRow).all():
                rec = {"adoption_id": r.adoption_id, "patient_id": r.patient_id,
                       "agent_type": r.agent_type, "msg_id": r.msg_id,
                       "summary": r.summary, "target": r.target,
                       "detail": db.loads(r.detail_json, {}),
                       "adopted_at": r.created_at}
                self.unified_adoptions.setdefault(r.patient_id, []).append(rec)

            self.patient_events = [
                {**(db.loads(r.payload_json, {}) or {}), "timestamp": r.created_at}
                for r in s.query(db.PatientEventRow).all()
            ]
            self.system_audit_log = [
                {"log_id": r.log_id, "operator_id": r.operator_id,
                 "operator_name": r.operator_name, "action": r.action,
                 "entity": r.entity, "entity_id": r.entity_id,
                 "before": db.loads(r.before_json), "after": db.loads(r.after_json),
                 "timestamp": r.created_at}
                for r in s.query(db.SystemAuditRow).all()
            ]
            self.crystallized_knowledge = [
                db.loads(r.card_json, {})
                for r in s.query(db.MemoryCardRow).filter_by(owner_type="system").all()
            ]
            self.doctor_memory = {}
            for r in s.query(db.MemoryCardRow).filter_by(owner_type="doctor").all():
                card = db.loads(r.card_json, {})
                self.doctor_memory.setdefault(r.owner_id, []).append(card)

            # patients + 回填 6 个剥离集合
            mdt_by_pid: Dict[str, List[dict]] = {}
            for r in s.query(db.MdtCommentRow).all():
                mdt_by_pid.setdefault(r.patient_id, []).append({
                    "comment_id": r.comment_id, "author_id": r.author_id,
                    "author_name": r.author_name, "author_role": r.author_role,
                    "content": r.content, "created_at": r.created_at,
                    "is_adopted": bool(r.is_adopted), "adopted_by": r.adopted_by,
                    "adopted_by_name": r.adopted_by_name, "adopted_at": r.adopted_at})
            tv_by_pid: Dict[str, List[dict]] = {}
            for r in s.query(db.TreatmentVersionRow).all():
                tv_by_pid.setdefault(r.patient_id, []).append({
                    "version_id": r.version_id, "version_no": r.version_no,
                    "content": r.content, "created_at": r.created_at,
                    "created_by": r.created_by, "created_by_name": r.created_by_name})
            audit_by_pid: Dict[str, List[dict]] = {}
            for r in s.query(db.AuditLogRow).all():
                audit_by_pid.setdefault(r.patient_id, []).append({
                    "log_id": r.log_id, "action": r.action, "actor_id": r.actor_id,
                    "actor_name": r.actor_name, "detail": r.detail,
                    "timestamp": r.created_at})
            notify_by_pid: Dict[str, List[dict]] = {}
            for r in s.query(db.NotificationRow).all():
                notify_by_pid.setdefault(r.patient_id, []).append({
                    "notify_id": r.notify_id, "type": r.type,
                    "target_user_id": r.target_user_id, "message": r.message,
                    "created_at": r.created_at, "read": bool(r.read)})
            tasks_by_pid: Dict[str, List[dict]] = {}
            for r in s.query(db.ExamReportRow).all():
                tasks_by_pid.setdefault(r.patient_id, []).append({
                    "task_id": r.task_id, "task_type": r.task_type,
                    "task_label": r.task_label, "status": r.status,
                    "created_at": r.ordered_at, "created_by": r.created_by,
                    "created_by_name": r.created_by_name,
                    "completed_at": r.completed_at,
                    "result": db.loads(r.result_json)})
            memcards_by_pid: Dict[str, List[dict]] = {}
            for r in s.query(db.MemoryCardRow).filter_by(owner_type="patient").all():
                memcards_by_pid.setdefault(r.owner_id, []).append(db.loads(r.card_json, {}))

            for r in s.query(db.PatientRow).all():
                state = dict(db.loads(r.state_json, {}) or {})
                state.update({
                    "patient_id": r.patient_id,
                    "patient_name": r.patient_name or state.get("patient_name", ""),
                    "gender": r.gender if r.gender is not None else state.get("gender"),
                    "age": r.age if r.age is not None else state.get("age"),
                    "department": r.department if r.department is not None else state.get("department"),
                    "status": r.status or state.get("status", "waiting"),
                    "hitl_pending": bool(r.hitl_pending),
                    "attending_doctor_ids": db.loads(r.attending_doctor_ids, []),
                    "check_tasks": tasks_by_pid.get(r.patient_id, []),
                    "mdt_comments": mdt_by_pid.get(r.patient_id, []),
                    "notify_queue": notify_by_pid.get(r.patient_id, []),
                    "audit_log": audit_by_pid.get(r.patient_id, []),
                    "treatment_versions": tv_by_pid.get(r.patient_id, []),
                    "memory_cards": memcards_by_pid.get(r.patient_id, []),
                })
                self.patients[r.patient_id] = state
        return True

    def mark_seeded(self) -> None:
        """种子灌完打标（幂等种子护栏）。"""
        with Session(db.engine) as s, s.begin():
            s.merge(db.AppKvRow(key="meta.seeded", value_json=db.dumps(True), updated_at=_now()))

    def persist_all(self) -> None:
        """把内存缓存整体落盘（幂等；请求边界中间件 + 种子灌完后调用）。

        策略：全部业务表按域整体重建（DELETE + INSERT，单事务）。演示级数据量
        （<10MB）下单次 flush 为毫秒级；换来的是零逐方法埋点、种子/后台路径全覆盖。
        """
        ts = _now()
        with Session(db.engine) as s, s.begin():
            for model in (db.UserRow, db.PatientUserRow, db.DepartmentRow, db.BuildingRow,
                          db.KbEntryRow, db.RagDocRow, db.PromptResourceRow, db.SchemaResourceRow,
                          db.ModelResourceRow, db.KgDeptAliasRow, db.ExamItemDictRow,
                          db.PatientRow, db.ExamReportRow, db.ExamItemRow,
                          db.MdtCommentRow, db.TreatmentVersionRow, db.AuditLogRow,
                          db.NotificationRow, db.SystemAuditRow, db.PatientEventRow,
                          db.ChatMessageRow, db.AdoptionRow, db.MemoryCardRow):
                s.query(model).delete(synchronize_session=False)

            B_KV_EXCLUDE = {
                "user_id", "username", "password", "name", "role", "department",
                "title", "dept_lead", "active", "patient_id", "patient_name",
                "medical_card_number", "phone", "gender", "age", "dept_id", "name",
                "building_id", "floors", "kb_id", "category", "title", "content",
                "tags", "item_id", "code", "exam_code", "spec", "ref_range",
                "doc_id", "chunks", "status", "prompt_id", "bound_agents",
                "schema_id", "json_schema", "model_id", "provider", "model",
                "api_key", "base_url", "timeout", "kg_dept_name",
                "business_dept_name", "note", "created_at", "updated_at",
            }

            def extra_of(data: dict, *also_exclude: str) -> str:
                excl = B_KV_EXCLUDE | set(also_exclude)
                return db.dumps({k: v for k, v in data.items() if k not in excl})

            for u in self.users.values():
                s.merge(db.UserRow(
                    user_id=u.get("user_id"), username=u.get("username"),
                    password=u.get("password"), name=u.get("name"), role=u.get("role"),
                    department=u.get("department"), title=u.get("title"),
                    dept_lead=int(bool(u.get("dept_lead"))),
                    active=int(bool(u.get("active", True))),
                    extra_json=extra_of(u), created_at=u.get("created_at"), updated_at=ts))
            for p in self.patient_users.values():
                s.merge(db.PatientUserRow(
                    patient_id=p.get("patient_id"), patient_name=p.get("patient_name"),
                    medical_card_number=p.get("medical_card_number"), phone=p.get("phone"),
                    gender=p.get("gender"), age=p.get("age"),
                    extra_json=extra_of(p), created_at=p.get("created_at"), updated_at=ts))
            for d in self.departments.values():
                s.merge(db.DepartmentRow(
                    dept_id=d.get("dept_id"), name=d.get("name"),
                    extra_json=extra_of(d), created_at=d.get("created_at"), updated_at=ts))
            for b in self.buildings.values():
                s.merge(db.BuildingRow(
                    building_id=b.get("building_id"), name=b.get("name"),
                    floors_json=db.dumps(b.get("floors", [])),
                    extra_json=extra_of(b, "name"), created_at=b.get("created_at"), updated_at=ts))
            for k in self.kb_entries.values():
                s.merge(db.KbEntryRow(
                    kb_id=k.get("kb_id"), category=k.get("category"), title=k.get("title"),
                    content=k.get("content"), tags_json=db.dumps(k.get("tags", [])),
                    extra_json=extra_of(k), created_at=k.get("created_at"),
                    updated_at=k.get("updated_at")))
            for it in self.exam_items.values():
                s.merge(db.ExamItemDictRow(
                    item_id=it.get("item_id"), code=it.get("code"), name=it.get("name"),
                    category=it.get("category"), spec=it.get("spec"),
                    ref_range=it.get("ref_range"), created_at=it.get("created_at")))
            for doc in self.rag_docs.values():
                s.merge(db.RagDocRow(
                    doc_id=doc.get("doc_id"), title=doc.get("title"),
                    category=doc.get("category"), content=doc.get("content"),
                    status=doc.get("status"), chunks_json=db.dumps(doc.get("chunks", [])),
                    extra_json=extra_of(doc), created_at=doc.get("created_at"),
                    updated_at=doc.get("updated_at")))
            for pr in self.prompt_resources.values():
                s.merge(db.PromptResourceRow(
                    prompt_id=pr.get("prompt_id"), name=pr.get("name"),
                    content=pr.get("content"), status=pr.get("status"),
                    department=pr.get("department"),
                    bound_agents_json=db.dumps(pr.get("bound_agents", [])),
                    extra_json=extra_of(pr), created_at=pr.get("created_at"),
                    updated_at=ts))
            for sr in self.schema_resources.values():
                s.merge(db.SchemaResourceRow(
                    schema_id=sr.get("schema_id"), name=sr.get("name"),
                    json_schema_text=db.dumps(sr.get("json_schema")),
                    status=sr.get("status"), department=sr.get("department"),
                    bound_agents_json=db.dumps(sr.get("bound_agents", [])),
                    extra_json=extra_of(sr), created_at=sr.get("created_at"),
                    updated_at=ts))
            for mr in self.model_resources.values():
                s.merge(db.ModelResourceRow(
                    model_id=mr.get("model_id"), provider=mr.get("provider"),
                    model=mr.get("model"), api_key=mr.get("api_key"),
                    base_url=mr.get("base_url"), timeout=int(mr.get("timeout", 30)),
                    status=mr.get("status"),
                    bound_agents_json=db.dumps(mr.get("bound_agents", [])),
                    extra_json=extra_of(mr), created_at=mr.get("created_at"), updated_at=ts))
            for name, alias in self._kg_dept_aliases.items():
                s.merge(db.KgDeptAliasRow(
                    kg_dept_name=alias.get("kg_dept_name", name),
                    business_dept_name=alias.get("business_dept_name"),
                    note=alias.get("note"), updated_at=alias.get("updated_at")))

            # —— 会话 / 采纳 / 埋点 / 系统审计 ——
            for channel, sessions in (("emr", self.emr_chat_sessions),
                                      ("prediction", self.prediction_chat_sessions),
                                      ("unified", self.unified_chat_sessions),
                                      ("research", self.research_chat_sessions)):
                for owner_key, msgs in sessions.items():
                    for m in msgs:
                        s.merge(db.ChatMessageRow(
                            msg_id=m.get("msg_id"), channel=channel, owner_id=owner_key,
                            role=m.get("role"), content=m.get("content"),
                            extra_json=db.dumps({k: v for k, v in m.items()
                                                 if k not in ("msg_id", "role", "content", "timestamp")}),
                            created_at=m.get("timestamp")))
            for pid, records in self.unified_adoptions.items():
                for rec in records:
                    s.add(db.AdoptionRow(
                        adoption_id=rec.get("adoption_id"), patient_id=pid,
                        agent_type=rec.get("agent_type"), msg_id=rec.get("msg_id"),
                        summary=rec.get("summary"), target=rec.get("target"),
                        detail_json=db.dumps(rec.get("detail") or {}),
                        created_at=rec.get("adopted_at")))
            for ev in self.patient_events:
                s.add(db.PatientEventRow(
                    patient_id=ev.get("patient_id"), event_type=ev.get("event_type"),
                    payload_json=db.dumps({k: v for k, v in ev.items() if k != "timestamp"}),
                    created_at=ev.get("timestamp")))
            for entry in self.system_audit_log:
                s.add(db.SystemAuditRow(
                    log_id=entry.get("log_id"), operator_id=entry.get("operator_id"),
                    operator_name=entry.get("operator_name"), action=entry.get("action"),
                    entity=entry.get("entity"), entity_id=entry.get("entity_id"),
                    before_json=db.dumps(entry.get("before")),
                    after_json=db.dumps(entry.get("after")),
                    created_at=entry.get("timestamp")))
            doctor_cards = [(uid_, c) for uid_, cards in self.doctor_memory.items() for c in cards]
            for uid_, card in doctor_cards:
                s.add(db.MemoryCardRow(
                    card_id=card.get("card_id"), owner_type="doctor", owner_id=uid_,
                    card_type=card.get("card_type"), frozen=int(bool(card.get("frozen"))),
                    card_json=db.dumps(card), created_at=card.get("create_time")))
            for card in self.crystallized_knowledge:
                s.add(db.MemoryCardRow(
                    card_id=card.get("card_id"), owner_type="system",
                    owner_id=card.get("owner_id", "system"), card_type=card.get("card_type"),
                    frozen=int(bool(card.get("frozen"))), card_json=db.dumps(card),
                    created_at=card.get("create_time")))

            # —— patients 文档 + 六个剥离集合的关系表 ——
            for pid, state in self.patients.items():
                doc = {k: v for k, v in state.items() if k not in self._STRIP_KEYS}
                s.merge(db.PatientRow(
                    patient_id=pid, patient_name=state.get("patient_name"),
                    gender=str(state.get("gender")) if state.get("gender") is not None else None,
                    age=str(state.get("age")) if state.get("age") is not None else None,
                    department=state.get("department"), status=state.get("status"),
                    hitl_pending=int(bool(state.get("hitl_pending"))),
                    attending_doctor_ids=db.dumps(state.get("attending_doctor_ids", [])),
                    state_json=db.dumps(doc), created_at=state.get("created_at"), updated_at=ts))

                for c in state.get("mdt_comments", []):
                    s.merge(db.MdtCommentRow(
                        comment_id=c.get("comment_id"), patient_id=pid,
                        author_id=c.get("author_id"), author_name=c.get("author_name"),
                        author_role=c.get("author_role"), content=c.get("content"),
                        is_adopted=int(bool(c.get("is_adopted"))),
                        adopted_by=c.get("adopted_by"),
                        adopted_by_name=c.get("adopted_by_name"),
                        adopted_at=c.get("adopted_at"), created_at=c.get("created_at")))
                for v in state.get("treatment_versions", []):
                    s.merge(db.TreatmentVersionRow(
                        version_id=v.get("version_id"), patient_id=pid,
                        version_no=int(v.get("version_no", 0)), content=v.get("content"),
                        created_by=v.get("created_by"),
                        created_by_name=v.get("created_by_name"),
                        created_at=v.get("created_at")))
                for a in state.get("audit_log", []):
                    s.add(db.AuditLogRow(
                        log_id=a.get("log_id"), patient_id=pid, action=a.get("action"),
                        actor_id=a.get("actor_id"), actor_name=a.get("actor_name"),
                        detail=a.get("detail"), created_at=a.get("timestamp")))
                for n in state.get("notify_queue", []):
                    s.add(db.NotificationRow(
                        notify_id=n.get("notify_id"), patient_id=pid,
                        target_user_id=n.get("target_user_id"), type=n.get("type"),
                        message=n.get("message"), read=int(bool(n.get("read"))),
                        created_at=n.get("created_at")))
                for card in state.get("memory_cards", []):
                    s.merge(db.MemoryCardRow(
                        card_id=card.get("card_id"), owner_type="patient", owner_id=pid,
                        card_type=card.get("card_type"), frozen=int(bool(card.get("frozen"))),
                        card_json=db.dumps(card), created_at=card.get("create_time")))
                for t in state.get("check_tasks", []):
                    result = t.get("result") if isinstance(t.get("result"), dict) else None
                    s.merge(db.ExamReportRow(
                        task_id=t.get("task_id"), patient_id=pid,
                        task_type=t.get("task_type"), task_label=t.get("task_label"),
                        status=t.get("status"), ordered_at=t.get("created_at"),
                        created_by=t.get("created_by"),
                        created_by_name=t.get("created_by_name"),
                        completed_at=t.get("completed_at"),
                        flag=self._exam_report_flag(result),
                        result_json=db.dumps(result) if result is not None else None,
                        source="flow", created_at=t.get("created_at"), updated_at=ts))
                    if result:
                        for idx, item in enumerate(result.get("items") or []):
                            if not isinstance(item, dict):
                                continue
                            s.add(db.ExamItemRow(
                                report_id=t.get("task_id"), code=item.get("code"),
                                name=item.get("name"),
                                value_text=str(item.get("value", "")) if item.get("value") is not None else None,
                                unit=item.get("unit"),
                                ref_range=item.get("reference_range") or item.get("ref_range"),
                                flag=self._item_flag(item.get("abnormal")), sort_no=idx))

            # —— KV ——
            s.merge(db.AppKvRow(key="subagent_config", value_json=db.dumps(self.subagent_config), updated_at=ts))
            s.merge(db.AppKvRow(key="permission_matrix", value_json=db.dumps(self.permission_matrix), updated_at=ts))
            s.merge(db.AppKvRow(key="agent_config", value_json=db.dumps(self.agent_config), updated_at=ts))
            s.merge(db.AppKvRow(key="chat_status", value_json=db.dumps(self.chat_status), updated_at=ts))
            s.merge(db.AppKvRow(key="meta.seeded", value_json=db.dumps(True), updated_at=ts))

    # ---------- 用户 ----------
    def add_user(self, user: dict) -> None:
        with self._lock:
            self.users[user["user_id"]] = user

    def get_user(self, user_id: str) -> Optional[dict]:
        with self._lock:
            return self.users.get(user_id)

    def find_user_by_username(self, username: str) -> Optional[dict]:
        with self._lock:
            for u in self.users.values():
                if u["username"] == username and u.get("active", True):
                    return u
        return None

    def list_users(self) -> List[dict]:
        with self._lock:
            return list(self.users.values())

    def create_user(self, *, username, password, name, role, department, title,
                    dept_lead: bool = False) -> dict:
        with self._lock:
            user = {
                "user_id": _uid("u"),
                "username": username,
                "password": password,
                "name": name,
                "role": role,
                "department": department,
                "title": title,
                "dept_lead": dept_lead,   # 科室负责人标志（可管理本科室 prompt/schema）
                "active": True,
            }
            self.users[user["user_id"]] = user
            return user

    def update_user(self, user_id: str, patch: dict) -> Optional[dict]:
        with self._lock:
            user = self.users.get(user_id)
            if user is None:
                return None
            for k in ("name", "role", "department", "title", "password", "active", "dept_lead"):
                if k in patch:
                    user[k] = patch[k]
            return user

    def can_manage_dept_prompt(self, user: dict, department: Optional[str]) -> bool:
        """判断用户能否编辑某科室的 prompt/schema 配对。

        - admin / platform_admin：全权（所有科室）
        - attending 且 dept_lead=True 且 department 匹配：可编辑本科室
        - 其他：不可
        """
        role = user.get("role")
        if role in ("admin", "platform_admin"):
            return True
        if role == "attending" and user.get("dept_lead"):
            return (user.get("department") or "") == (department or "")
        return False

    def delete_user(self, user_id: str) -> bool:
        with self._lock:
            return self.users.pop(user_id, None) is not None

    # ---------- 患者端用户 ----------
    def add_patient_user(self, user: dict) -> None:
        with self._lock:
            self.patient_users[user["patient_id"]] = user

    def get_patient_user(self, patient_id: str) -> Optional[dict]:
        with self._lock:
            return self.patient_users.get(patient_id)

    def find_patient_user(self, patient_id: str, medical_card_number: str) -> Optional[dict]:
        with self._lock:
            u = self.patient_users.get(patient_id)
            if u and u.get("medical_card_number") == medical_card_number:
                return u
        return None

    def list_patient_users(self) -> List[dict]:
        with self._lock:
            return list(self.patient_users.values())

    def create_patient_user(self, *, patient_id, patient_name, medical_card_number, phone, gender, age) -> dict:
        with self._lock:
            user = {
                "patient_id": patient_id or _uid("p"),
                "patient_name": patient_name,
                "medical_card_number": medical_card_number,
                "phone": phone,
                "gender": gender,
                "age": age,
            }
            self.patient_users[user["patient_id"]] = user
            return user

    def update_patient_user(self, patient_id: str, patch: dict) -> Optional[dict]:
        with self._lock:
            u = self.patient_users.get(patient_id)
            if u is None:
                return None
            for k in ("patient_name", "medical_card_number", "phone", "gender", "age"):
                if k in patch:
                    u[k] = patch[k]
            return u

    def delete_patient_user(self, patient_id: str) -> bool:
        with self._lock:
            return self.patient_users.pop(patient_id, None) is not None

    # ---------- 患者端行为埋点 ----------
    def track_patient_event(self, event: dict) -> None:
        with self._lock:
            event.setdefault("timestamp", _now())
            self.patient_events.append(event)
            if len(self.patient_events) > 5000:
                self.patient_events = self.patient_events[-2500:]

    def list_patient_events(self, patient_id: Optional[str] = None,
                            event_type: Optional[str] = None) -> List[dict]:
        with self._lock:
            out = list(self.patient_events)
        if patient_id:
            out = [e for e in out if e.get("patient_id") == patient_id]
        if event_type:
            out = [e for e in out if e.get("event_type") == event_type]
        out.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        return out

    # ---------- 病历 Agent 对话历史 ----------
    def get_emr_chat_history(self, patient_id: str) -> List[dict]:
        """获取某患者的病历 Agent 对话历史（按时间正序）。"""
        with self._lock:
            return list(self.emr_chat_sessions.get(patient_id, []))

    def append_emr_chat_message(self, patient_id: str, role: str, content: str,
                                extra: Optional[dict] = None) -> dict:
        """追加一条对话消息。role: 'user' / 'assistant'。返回新增消息。"""
        with self._lock:
            msg = {
                "msg_id": _uid("emrmsg"),
                "role": role,
                "content": content,
                "timestamp": _now(),
            }
            if extra:
                msg.update(extra)
            self.emr_chat_sessions.setdefault(patient_id, []).append(msg)
            # 限制单 patient 历史长度，避免内存膨胀
            if len(self.emr_chat_sessions[patient_id]) > 100:
                self.emr_chat_sessions[patient_id] = self.emr_chat_sessions[patient_id][-50:]
            return dict(msg)

    def clear_emr_chat_history(self, patient_id: str) -> int:
        """清空某患者的对话历史，返回清除条数。"""
        with self._lock:
            n = len(self.emr_chat_sessions.get(patient_id, []))
            self.emr_chat_sessions.pop(patient_id, None)
            return n

    # ---------- 疾病预测 Agent 对话历史 ----------
    def get_prediction_chat_history(self, patient_id: str) -> List[dict]:
        """获取某患者的疾病预测 Agent 对话历史（按时间正序）。"""
        with self._lock:
            return list(self.prediction_chat_sessions.get(patient_id, []))

    def append_prediction_chat_message(self, patient_id: str, role: str, content: str,
                                       extra: Optional[dict] = None) -> dict:
        """追加一条预测对话消息。role: 'user' / 'assistant'。返回新增消息。"""
        with self._lock:
            msg = {
                "msg_id": _uid("predmsg"),
                "role": role,
                "content": content,
                "timestamp": _now(),
            }
            if extra:
                msg.update(extra)
            self.prediction_chat_sessions.setdefault(patient_id, []).append(msg)
            if len(self.prediction_chat_sessions[patient_id]) > 100:
                self.prediction_chat_sessions[patient_id] = self.prediction_chat_sessions[patient_id][-50:]
            return dict(msg)

    def clear_prediction_chat_history(self, patient_id: str) -> int:
        """清空某患者的预测对话历史，返回清除条数。"""
        with self._lock:
            n = len(self.prediction_chat_sessions.get(patient_id, []))
            self.prediction_chat_sessions.pop(patient_id, None)
            return n

    # ---------- 统一对话（豆包式：多 Agent 共享一个会话） ----------
    def get_unified_chat_history(self, patient_id: str, namespace: str = "") -> List[dict]:
        key = f"{namespace}:{patient_id}" if namespace else patient_id
        with self._lock:
            return list(self.unified_chat_sessions.get(key, []))

    def append_unified_chat_message(self, patient_id: str, role: str, content: str,
                                    extra: Optional[dict] = None,
                                    namespace: str = "") -> dict:
        key = f"{namespace}:{patient_id}" if namespace else patient_id
        with self._lock:
            msg = {
                "msg_id": _uid("unichat"),
                "role": role,
                "content": content,
                "timestamp": _now(),
            }
            if extra:
                msg.update(extra)
            self.unified_chat_sessions.setdefault(key, []).append(msg)
            if len(self.unified_chat_sessions[key]) > 200:
                self.unified_chat_sessions[key] = self.unified_chat_sessions[key][-100:]
            return dict(msg)

    def clear_unified_chat_history(self, patient_id: str, namespace: str = "") -> int:
        key = f"{namespace}:{patient_id}" if namespace else patient_id
        with self._lock:
            n = len(self.unified_chat_sessions.get(key, []))
            self.unified_chat_sessions.pop(key, None)
            return n

    # ---------- 对话处理状态（Agent 思考过程可视化） ----------
    def set_chat_status(self, patient_id: str, steps: List[dict]) -> None:
        """覆盖写入当前对话处理状态（steps: [{key,label,status,detail}]）。"""
        with self._lock:
            self.chat_status[patient_id] = {"steps": steps, "updated_at": _now()}

    def get_chat_status(self, patient_id: str) -> Optional[dict]:
        with self._lock:
            st = self.chat_status.get(patient_id)
            return dict(st) if st else None

    def clear_chat_status(self, patient_id: str) -> None:
        with self._lock:
            self.chat_status.pop(patient_id, None)

    # ---------- 采纳记录（AI 结果 → PatientState） ----------
    def get_adoptions(self, patient_id: str) -> List[dict]:
        with self._lock:
            return list(self.unified_adoptions.get(patient_id, []))

    def add_adoption(self, patient_id: str, agent_type: str, msg_id: str,
                     summary: str, target: str, detail: Optional[dict] = None) -> dict:
        with self._lock:
            record = {
                "adoption_id": _uid("adopt"),
                "patient_id": patient_id,
                "agent_type": agent_type,
                "msg_id": msg_id,
                "summary": summary,
                "target": target,   # 'emr' | 'diagnosis' | 'treatment'
                "detail": detail or {},
                "adopted_at": _now(),
            }
            self.unified_adoptions.setdefault(patient_id, []).append(record)
            return dict(record)

    def clear_adoptions(self, patient_id: str) -> int:
        with self._lock:
            n = len(self.unified_adoptions.get(patient_id, []))
            self.unified_adoptions.pop(patient_id, None)
            return n

    # ==================== 记忆模块（L2 主体记忆 / L3 沉淀知识） ====================

    def _make_memory_card(self, *, owner_type: str, owner_id: str, card_type: str,
                          title: str, content: str, tags: Optional[List[str]] = None,
                          confidence: float = 0.7, source: str = "user_manual",
                          permission_tags: Optional[List[str]] = None,
                          expert_dept: Optional[str] = None, adopted: Optional[bool] = None,
                          frozen: bool = False, valid_start: Optional[str] = None,
                          valid_end: Optional[str] = None,
                          sample_count: Optional[int] = None) -> dict:
        """统一构造一张记忆卡片（自动生成 card_id/trace_id/时间戳/valid_time）。"""
        return {
            "card_id": _uid("mem"),
            "owner_type": owner_type,
            "owner_id": owner_id,
            "card_type": card_type,
            "title": title,
            "content": content,
            "tags": list(tags or []),
            "confidence": float(confidence),
            "source": source,
            "valid_time": {"start": valid_start or _now(), "end": valid_end},
            "create_time": _now(),
            "trace_id": _uid("mtrc"),
            "permission_tags": list(permission_tags or []),
            "adopted": adopted,
            "expert_dept": expert_dept,
            "frozen": frozen,
            "superseded_by": None,
            "sample_count": sample_count,
            "deidentified": owner_type == "system",
        }

    # —— 医生 L2 记忆（doctor_memory）——
    def add_doctor_memory_card(self, user_id: str, card: dict) -> dict:
        with self._lock:
            self.doctor_memory.setdefault(user_id, []).append(card)
            return dict(card)

    def list_doctor_memory_cards(self, user_id: str, card_type: Optional[str] = None) -> List[dict]:
        with self._lock:
            cards = list(self.doctor_memory.get(user_id, []))
        if card_type:
            cards = [c for c in cards if c.get("card_type") == card_type]
        return [c for c in cards if not c.get("superseded_by")]

    def delete_doctor_memory_card(self, user_id: str, card_id: str) -> bool:
        with self._lock:
            cards = self.doctor_memory.get(user_id, [])
            for i, c in enumerate(cards):
                if c.get("card_id") == card_id:
                    if c.get("frozen"):
                        return False  # 冻结卡片不可删（MDT 沉淀继承此语义）
                    cards.pop(i)
                    return True
            return False

    def supersede_doctor_memory_card(self, user_id: str, old_card_id: str, new_card: dict) -> dict:
        """去重合并：标记旧卡被覆盖，追加新卡。"""
        with self._lock:
            cards = self.doctor_memory.setdefault(user_id, [])
            for c in cards:
                if c.get("card_id") == old_card_id:
                    c["superseded_by"] = new_card["card_id"]
            cards.append(new_card)
            return dict(new_card)

    # —— 患者 L2 记忆（PatientState.memory_cards，随患者走）——
    def add_patient_memory_card(self, patient_id: str, card: dict) -> dict:
        with self._lock:
            state = self.patients.get(patient_id)
            if state is None:
                return {}
            state.setdefault("memory_cards", []).append(card)
            return dict(card)

    def list_patient_memory_cards(self, patient_id: str, card_type: Optional[str] = None) -> List[dict]:
        with self._lock:
            state = self.patients.get(patient_id)
            if state is None:
                return []
            cards = list(state.get("memory_cards", []))
        if card_type:
            cards = [c for c in cards if c.get("card_type") == card_type]
        return [c for c in cards if not c.get("superseded_by")]

    def mark_patient_memory_card_adopted(self, patient_id: str, title_keyword: str) -> int:
        """标记匹配的 MDT 沉淀卡片为已采纳（用于 MDT 采纳同步，仅改 adopted/confidence，不改内容）。

        匹配规则：source=mdt_comment 且 title 含 keyword。
        """
        with self._lock:
            state = self.patients.get(patient_id)
            if state is None:
                return 0
            cards = state.get("memory_cards", [])
            n = 0
            for c in cards:
                if c.get("source") == "mdt_comment" and title_keyword in (c.get("title") or ""):
                    c["adopted"] = True
                    c["confidence"] = min(float(c.get("confidence", 0.6)) + 0.2, 1.0)
                    n += 1
            return n

    # —— L3 沉淀知识（crystallized_knowledge，去标识化全院共享）——
    def add_crystallized(self, card: dict) -> dict:
        with self._lock:
            self.crystallized_knowledge.append(card)
            return dict(card)

    def list_crystallized(self, tags: Optional[List[str]] = None, limit: int = 50) -> List[dict]:
        with self._lock:
            cards = list(self.crystallized_knowledge)
        if tags:
            tag_set = set(tags)
            cards = [c for c in cards if tag_set & set(c.get("tags", []))]
        return cards[-limit:] if limit else cards

    # —— 记忆检索（注入用，Demo 用标签+关键词，不上向量）——
    def search_memory_for_research(self, user_id: str, query_tags: Optional[List[str]] = None,
                                    limit: int = 10) -> dict:
        """研究模式注入：医生自己的 L2 + L3。不注入任何患者数据。"""
        with self._lock:
            doc_cards = [c for c in self.doctor_memory.get(user_id, [])
                         if not c.get("superseded_by")]
            cry_cards = list(self.crystallized_knowledge)
        if query_tags:
            tag_set = set(query_tags)
            doc_cards = [c for c in doc_cards if tag_set & set(c.get("tags", []))]
            cry_cards = [c for c in cry_cards if tag_set & set(c.get("tags", []))]
        return {"doctor_cards": doc_cards[-limit:], "crystallized": cry_cards[-limit:]}

    def search_memory_for_patient(self, patient_id: str, query_tags: Optional[List[str]] = None,
                                   limit: int = 10) -> dict:
        """患者模式注入：患者自己的 L2 + L3。不注入医生私有 insight。"""
        with self._lock:
            state = self.patients.get(patient_id)
            pat_cards = list(state.get("memory_cards", [])) if state else []
            pat_cards = [c for c in pat_cards if not c.get("superseded_by")]
            cry_cards = list(self.crystallized_knowledge)
        if query_tags:
            tag_set = set(query_tags)
            pat_cards = [c for c in pat_cards if tag_set & set(c.get("tags", []))]
            cry_cards = [c for c in cry_cards if tag_set & set(c.get("tags", []))]
        return {"patient_cards": pat_cards[-limit:], "crystallized": cry_cards[-limit:]}

    # —— 研究模式对话历史（复用 prediction_chat 模式）——
    def get_research_chat_history(self, user_id: str) -> List[dict]:
        with self._lock:
            return list(self.research_chat_sessions.get(user_id, []))

    def append_research_chat_message(self, user_id: str, role: str, content: str,
                                      extra: Optional[dict] = None) -> dict:
        with self._lock:
            msg = {
                "msg_id": _uid("resmsg"),
                "role": role,
                "content": content,
                "timestamp": _now(),
            }
            if extra:
                msg.update(extra)
            self.research_chat_sessions.setdefault(user_id, []).append(msg)
            if len(self.research_chat_sessions[user_id]) > 100:
                self.research_chat_sessions[user_id] = self.research_chat_sessions[user_id][-50:]
            return dict(msg)

    def clear_research_chat_history(self, user_id: str) -> int:
        with self._lock:
            n = len(self.research_chat_sessions.get(user_id, []))
            self.research_chat_sessions.pop(user_id, None)
            return n

    # ---------- 患者 / State ----------
    def upsert_patient(self, state: PatientState) -> None:
        with self._lock:
            self.patients[state["patient_id"]] = state

    def get_patient(self, patient_id: str) -> Optional[PatientState]:
        with self._lock:
            return self.patients.get(patient_id)

    def list_patients(self) -> List[PatientState]:
        with self._lock:
            return list(self.patients.values())

    def patch_patient(self, patient_id: str, patch: dict) -> Optional[PatientState]:
        """局部更新患者 State（合并写）。"""
        with self._lock:
            state = self.patients.get(patient_id)
            if state is None:
                return None
            state.update(patch)
            return state

    # ---------- SubAgent 配置 ----------
    def get_subagent_config(self) -> dict:
        with self._lock:
            return dict(self.subagent_config)

    def set_subagent_config(self, enable_emr: bool, enable_lab: bool) -> dict:
        """更新全局开关，并同步到所有患者 State（保证节点内 if 分支即时生效）。"""
        with self._lock:
            self.subagent_config["enable_emr_subagent"] = bool(enable_emr)
            self.subagent_config["enable_lab_subagent"] = bool(enable_lab)
            for state in self.patients.values():
                state["enable_emr_subagent"] = bool(enable_emr)
                state["enable_lab_subagent"] = bool(enable_lab)
            return self.get_subagent_config()

    # ---------- 留痕与通知 ----------
    def append_audit(self, patient_id: str, action: str, actor: dict, detail: str) -> None:
        with self._lock:
            state = self.patients.get(patient_id)
            if state is None:
                return
            entry: AuditLogEntry = {
                "log_id": _uid("log"),
                "action": action,
                "actor_id": actor.get("user_id", "system"),
                "actor_name": actor.get("name", "系统"),
                "detail": detail,
                "timestamp": _now(),
            }
            state.setdefault("audit_log", []).append(entry)

    def push_notify(self, patient_id: str, target_user_id: str, ntype: str, message: str) -> None:
        with self._lock:
            state = self.patients.get(patient_id)
            if state is None:
                return
            event: NotifyEvent = {
                "notify_id": _uid("ntf"),
                "type": ntype,
                "target_user_id": target_user_id,
                "message": message,
                "created_at": _now(),
                "read": False,
            }
            state.setdefault("notify_queue", []).append(event)

    def list_notifications(self, user_id: str) -> List[NotifyEvent]:
        with self._lock:
            out: List[NotifyEvent] = []
            for state in self.patients.values():
                for n in state.get("notify_queue", []):
                    if n.get("target_user_id") == user_id:
                        out.append(n)
            out.sort(key=lambda n: n.get("created_at", ""), reverse=True)
            return out

    # ---------- 权限矩阵 ----------
    def get_permission_matrix(self) -> Dict[str, Dict[str, bool]]:
        with self._lock:
            # 深拷贝避免外部修改
            return {r: dict(a) for r, a in self.permission_matrix.items()}

    def set_permission_matrix(self, matrix: Dict[str, Dict[str, bool]]) -> Dict[str, Dict[str, bool]]:
        with self._lock:
            # 以默认矩阵为基底，仅覆盖「该角色适用域」内的动作，忽略越域/非法键
            new_matrix = default_permission_matrix()
            for role in ALL_PERMISSION_ROLES:
                if role not in matrix:
                    continue
                domains = ROLE_ACTION_DOMAINS.get(role, [])
                allowed = set()
                for d in domains:
                    allowed |= set(ACTION_GROUPS.get(d, []))
                for act in ALL_PERMISSION_ACTIONS:
                    if act in matrix[role] and act in allowed:
                        new_matrix[role][act] = bool(matrix[role][act])
            self.permission_matrix = new_matrix
            return self.get_permission_matrix()

    def role_permissions(self, role: str) -> Dict[str, bool]:
        """读取某角色的全部动作权限（含临床/后台/患者三域）。

        未配置角色返回全 False；admin/platform_admin/patient 从矩阵读取，
        其后台/患者动作位可供前端权限视图与后端 require_action 使用。
        """
        with self._lock:
            row = self.permission_matrix.get(role)
            if row is None:
                return {a: False for a in ALL_PERMISSION_ACTIONS}
            return {a: bool(row.get(a, False)) for a in ALL_PERMISSION_ACTIONS}

    # ---------- 科室 ----------
    def list_departments(self) -> List[dict]:
        with self._lock:
            return list(self.departments.values())

    def add_department(self, name: str) -> dict:
        with self._lock:
            dept = {"dept_id": _uid("dept"), "name": name, "created_at": _now()}
            self.departments[dept["dept_id"]] = dept
            return dept

    def update_department(self, dept_id: str, name: str) -> Optional[dict]:
        with self._lock:
            dept = self.departments.get(dept_id)
            if dept is None:
                return None
            dept["name"] = name
            return dept

    def delete_department(self, dept_id: str) -> bool:
        with self._lock:
            return self.departments.pop(dept_id, None) is not None

    # ---------- KG 科室 → 业务科室别名映射 ----------
    # 用途：disease-kb 数据源导入的 54 个 KG 科室（用于疾病 BELONGS_TO 语义关系）
    # 与自建 14 个业务科室（用于楼宇房间/医生 department/挂号流程）名称不完全一致，
    # 通过此映射表对齐，让患者导诊返回"呼吸内科"时能落到自建的"呼吸科"诊室。
    def add_kg_dept_alias(self, kg_dept_name: str, business_dept_name: str, note: str = "") -> dict:
        """新增/更新一条 KG 科室别名映射（同 kg_dept_name 覆盖更新）。"""
        with self._lock:
            self._kg_dept_aliases[kg_dept_name] = {
                "kg_dept_name": kg_dept_name,
                "business_dept_name": business_dept_name,
                "note": note,
                "updated_at": _now(),
            }
            return self._kg_dept_aliases[kg_dept_name]

    def get_business_dept_by_kg_name(self, kg_dept_name: str) -> Optional[str]:
        """KG 科室名 → 业务科室名（找不到则原样返回，保证向后兼容）。"""
        with self._lock:
            alias = self._kg_dept_aliases.get(kg_dept_name)
            if alias:
                return alias["business_dept_name"]
            return kg_dept_name  # 兜底：未配置映射时返回原 KG 名（不阻断业务）

    def list_kg_dept_aliases(self) -> List[dict]:
        with self._lock:
            return list(self._kg_dept_aliases.values())

    def delete_kg_dept_alias(self, kg_dept_name: str) -> bool:
        with self._lock:
            return self._kg_dept_aliases.pop(kg_dept_name, None) is not None

    # ---------- 知识库 ----------
    def list_kb(self, category: Optional[str] = None) -> List[dict]:
        with self._lock:
            out = list(self.kb_entries.values())
        if category:
            out = [e for e in out if e.get("category") == category]
        out.sort(key=lambda e: e.get("updated_at", ""), reverse=True)
        return out

    def get_kb(self, kb_id: str) -> Optional[dict]:
        with self._lock:
            return self.kb_entries.get(kb_id)

    def add_kb(self, *, category: str, title: str, content: str, tags: Optional[List[str]] = None) -> dict:
        with self._lock:
            entry = {
                "kb_id": _uid("kb"),
                "category": category,
                "title": title,
                "content": content,
                "tags": tags or [],
                "created_at": _now(),
                "updated_at": _now(),
            }
            self.kb_entries[entry["kb_id"]] = entry
            return entry

    def update_kb(self, kb_id: str, *, title: str, content: str, tags: Optional[List[str]] = None) -> Optional[dict]:
        with self._lock:
            entry = self.kb_entries.get(kb_id)
            if entry is None:
                return None
            entry["title"] = title
            entry["content"] = content
            entry["tags"] = tags if tags is not None else entry.get("tags", [])
            entry["updated_at"] = _now()
            return entry

    def delete_kb(self, kb_id: str) -> bool:
        with self._lock:
            return self.kb_entries.pop(kb_id, None) is not None

    def kb_for_emr_draft(self, keyword: str = "") -> List[dict]:
        """供病历 SubAgent 引用的知识库条目（指南 + SOAP 模板 + 药品字典）。"""
        with self._lock:
            cats = {"guide", "soap_template", "drug_dict"}
            out = [e for e in self.kb_entries.values() if e.get("category") in cats]
        if keyword:
            kw = keyword.lower()
            out = [e for e in out if kw in (e.get("title", "") + e.get("content", "")).lower()]
        return out

    # ==================== 楼宇/楼层/房间（主数据） ====================
    def list_buildings(self) -> List[dict]:
        with self._lock:
            return list(self.buildings.values())

    def add_building(self, name: str) -> dict:
        with self._lock:
            b = {"building_id": _uid("bld"), "name": name, "floors": [], "created_at": _now()}
            self.buildings[b["building_id"]] = b
            return b

    def update_building(self, building_id: str, name: str) -> Optional[dict]:
        with self._lock:
            b = self.buildings.get(building_id)
            if b is None:
                return None
            b["name"] = name
            return b

    def delete_building(self, building_id: str) -> bool:
        with self._lock:
            return self.buildings.pop(building_id, None) is not None

    def add_floor(self, building_id: str, name: str) -> Optional[dict]:
        with self._lock:
            b = self.buildings.get(building_id)
            if b is None:
                return None
            f = {"floor_id": _uid("flr"), "name": name, "rooms": []}
            b["floors"].append(f)
            return f

    def delete_floor(self, building_id: str, floor_id: str) -> bool:
        with self._lock:
            b = self.buildings.get(building_id)
            if b is None:
                return False
            before = len(b["floors"])
            b["floors"] = [f for f in b["floors"] if f["floor_id"] != floor_id]
            return len(b["floors"]) < before

    def bind_room(self, building_id: str, floor_id: str, room_name: str, dept_name: str) -> Optional[dict]:
        """在楼层下绑定房间→科室。"""
        with self._lock:
            b = self.buildings.get(building_id)
            if b is None:
                return None
            for f in b["floors"]:
                if f["floor_id"] == floor_id:
                    r = {
                        "room_id": _uid("rm"),
                        "room_name": room_name,
                        "dept_name": dept_name,
                    }
                    f["rooms"].append(r)
                    return r
            return None

    def delete_room(self, building_id: str, floor_id: str, room_id: str) -> bool:
        with self._lock:
            b = self.buildings.get(building_id)
            if b is None:
                return False
            for f in b["floors"]:
                if f["floor_id"] == floor_id:
                    before = len(f["rooms"])
                    f["rooms"] = [r for r in f["rooms"] if r["room_id"] != room_id]
                    return len(f["rooms"]) < before
            return False

    # ==================== 检验/检查项目字典（主数据） ====================
    EXAM_CATEGORIES = {"blood": "血液检验", "ct": "CT影像", "mri": "磁共振", "ultrasound": "超声", "xray": "X线", "pathology": "病理", "endoscopy": "内镜", "physiology": "功能检查", "other": "其他"}

    def list_exam_items(self, category: Optional[str] = None) -> List[dict]:
        with self._lock:
            out = list(self.exam_items.values())
        if category:
            out = [e for e in out if e.get("category") == category]
        return out

    def add_exam_item(self, *, code: str, name: str, category: str, spec: str = "", ref_range: str = "") -> dict:
        with self._lock:
            item = {"item_id": _uid("exam"), "code": code, "name": name,
                    "category": category, "spec": spec, "ref_range": ref_range, "created_at": _now()}
            self.exam_items[item["item_id"]] = item
            return item

    def update_exam_item(self, item_id: str, patch: dict) -> Optional[dict]:
        with self._lock:
            item = self.exam_items.get(item_id)
            if item is None:
                return None
            for k in ("code", "name", "category", "spec", "ref_range"):
                if k in patch:
                    item[k] = patch[k]
            return item

    def delete_exam_item(self, item_id: str) -> bool:
        with self._lock:
            return self.exam_items.pop(item_id, None) is not None

    # ==================== RAG 文档库（Mock 向量） ====================
    RAG_CATEGORIES = {"clinical_guide": "诊疗规范", "soap_template": "病历模板", "sop": "院内SOP", "mdt_template": "MDT模板"}

    @staticmethod
    def _mock_chunk(doc_id: str, text: str, idx: int) -> dict:
        """Mock 分块 + Mock 向量（生产需替换为真实 Embedding + 向量库）。"""
        import random
        return {
            "chunk_id": f"chk_{doc_id}_{idx}",
            "text": text,
            "vector_mock": [round(random.random(), 4) for _ in range(8)],  # Mock 8维向量
            "chunk_no": idx,
        }

    def _auto_chunk(self, doc_id: str, content: str) -> List[dict]:
        """Mock 分块：按段落分，每段≤200字。生产需替换为真实切块策略。"""
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        chunks = []
        idx = 0
        for p in paragraphs:
            # 长段落再切分（每200字一块）
            while len(p) > 200:
                chunks.append(self._mock_chunk(doc_id, p[:200], idx))
                p = p[200:]
                idx += 1
            if p:
                chunks.append(self._mock_chunk(doc_id, p, idx))
                idx += 1
        return chunks or [self._mock_chunk(doc_id, content[:200], 0)]

    def list_rag_docs(self, category: Optional[str] = None) -> List[dict]:
        with self._lock:
            out = list(self.rag_docs.values())
        if category:
            out = [d for d in out if d.get("category") == category]
        out.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
        return out

    def get_rag_doc(self, doc_id: str) -> Optional[dict]:
        with self._lock:
            return self.rag_docs.get(doc_id)

    def add_rag_doc(self, *, title: str, category: str, content: str,
                    uploaded_by: str, uploaded_by_name: str) -> dict:
        with self._lock:
            doc_id = _uid("rag")
            chunks = self._auto_chunk(doc_id, content)
            doc = {
                "doc_id": doc_id,
                "title": title,
                "category": category,
                "content": content,
                "chunks": chunks,
                "version": 1,
                "status": "pending",  # pending / active / inactive（待审核→启用→停用）
                "uploaded_by": uploaded_by,
                "uploaded_by_name": uploaded_by_name,
                "created_at": _now(),
                "updated_at": _now(),
            }
            self.rag_docs[doc_id] = doc
            return doc

    def update_rag_doc(self, doc_id: str, *, title: str, content: str) -> Optional[dict]:
        """更新内容→生成新版本+重新分块（保留旧版本快照）。"""
        with self._lock:
            doc = self.rag_docs.get(doc_id)
            if doc is None:
                return None
            # 保留旧版本快照
            doc.setdefault("history", []).append({
                "version": doc["version"],
                "title": doc["title"],
                "content": doc["content"],
                "chunks_count": len(doc["chunks"]),
                "updated_at": doc["updated_at"],
            })
            doc["version"] += 1
            doc["title"] = title
            doc["content"] = content
            doc["chunks"] = self._auto_chunk(doc_id, content)
            doc["status"] = "pending"  # 更新后需重新审核
            doc["updated_at"] = _now()
            return doc

    def set_rag_doc_status(self, doc_id: str, status: str) -> Optional[dict]:
        with self._lock:
            doc = self.rag_docs.get(doc_id)
            if doc is None:
                return None
            doc["status"] = status
            doc["updated_at"] = _now()
            return doc

    def delete_rag_doc(self, doc_id: str) -> bool:
        with self._lock:
            return self.rag_docs.pop(doc_id, None) is not None

    def rag_recall(self, query: str, top_k: int = 3) -> List[dict]:
        """Mock 召回：按关键词匹配 active 文档的 chunks。生产需替换为真实向量检索。"""
        with self._lock:
            active_docs = [d for d in self.rag_docs.values() if d.get("status") == "active"]
        kw = query.lower()
        hits = []
        for d in active_docs:
            for c in d.get("chunks", []):
                score = sum(1 for w in kw.split() if w in c["text"].lower())
                if score > 0 or kw in c["text"].lower():
                    hits.append({**c, "doc_id": d["doc_id"], "doc_title": d["title"],
                                 "category": d["category"], "score_mock": score + 0.1})
        hits.sort(key=lambda x: x["score_mock"], reverse=True)
        return hits[:top_k]

    # ==================== Agent 能力灰度配置 ====================
    def get_agent_config(self) -> dict:
        with self._lock:
            return {
                k: {
                    "global": v["global"],
                    "hospitals": dict(v["hospitals"]),
                    "model_config": dict(v.get("model_config", {})),
                }
                for k, v in self.agent_config.items()
            }

    def set_agent_config(self, agent_key: str, *, global_on: Optional[bool] = None,
                        hospital_id: Optional[str] = None, hospital_on: Optional[bool] = None) -> dict:
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            if global_on is not None:
                cfg["global"] = bool(global_on)
            if hospital_id and hospital_on is not None:
                cfg["hospitals"][hospital_id] = bool(hospital_on)
            return {agent_key: {"global": cfg["global"], "hospitals": dict(cfg["hospitals"])}}

    def update_agent_model_config(self, agent_key: str, *, provider: Optional[str] = None,
                                  enable_real: Optional[int] = None, model: Optional[str] = None,
                                  base_url: Optional[str] = None, api_key: Optional[str] = None,
                                  timeout: Optional[int] = None) -> dict:
        """更新某个 Agent 的模型配置。

        api_key 语义（防误清）：
        - None（字段未传）→ 不修改
        - ''（空字符串，显式清除）→ 清除 Key
        - 非空字符串 → 覆盖为新值（strip 后存储）
        """
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            mc = cfg.setdefault("model_config", {})
            if provider is not None:
                mc["provider"] = provider
            if enable_real is not None:
                mc["enable_real"] = int(enable_real)
            if model is not None:
                mc["model"] = model.strip()
            if base_url is not None:
                mc["base_url"] = base_url.strip()
            if api_key is not None:
                stripped = api_key.strip()
                if stripped:
                    mc["api_key"] = stripped       # 覆盖为新值
                elif api_key == "":
                    mc["api_key"] = ""            # 显式清除
                # else: api_key 全为空白字符，不修改（防误清）
            if timeout is not None:
                mc["timeout"] = int(timeout)
            return dict(mc)

    def get_agent_model_config(self, agent_key: str) -> dict:
        """获取某个 Agent 的模型配置。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            return dict(cfg.get("model_config", {}))

    def get_agent_prompt(self, agent_key: str) -> str:
        """获取某个 Agent 的自定义 Prompt（空字符串=使用默认）。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            return cfg.get("prompt", "")

    def update_agent_prompt(self, agent_key: str, prompt: str) -> dict:
        """更新某个 Agent 的自定义 Prompt。空字符串=清除自定义，恢复默认。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            cfg["prompt"] = (prompt or "").strip()
            return {"agent_key": agent_key, "prompt": cfg["prompt"]}

    def get_agent_output_schema(self, agent_key: str) -> str:
        """获取某个 Agent 的自定义输出 Schema（空字符串=使用默认）。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            return cfg.get("output_schema", "")

    def update_agent_output_schema(self, agent_key: str, output_schema: str) -> dict:
        """更新某个 Agent 的自定义输出 Schema。空字符串=清除自定义，恢复默认。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            cfg["output_schema"] = (output_schema or "").strip()
            return {"agent_key": agent_key, "output_schema": cfg["output_schema"]}

    def is_agent_enabled(self, agent_key: str, hospital_id: str = "") -> bool:
        """供 LangGraph 节点查询：医院级覆盖 > 全局开关。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                return False
            if hospital_id and hospital_id in cfg["hospitals"]:
                return cfg["hospitals"][hospital_id]
            return cfg["global"]

    # ==================== Prompt 资源管理（版本化） ====================
    def list_prompt_resources(self, agent_key: Optional[str] = None) -> List[dict]:
        with self._lock:
            items = list(self.prompt_resources.values())
        if agent_key:
            items = [r for r in items if agent_key in r.get("bound_agents", [])]
        return items

    def get_prompt_resource(self, prompt_id: str) -> Optional[dict]:
        with self._lock:
            return self.prompt_resources.get(prompt_id)

    def add_prompt_resource(self, *, name: str, content: str, created_by: str,
                            agent_keys: Optional[List[str]] = None,
                            remark: str = "",
                            department: Optional[str] = None) -> dict:
        with self._lock:
            prompt_id = _uid("pr")
            item = {
                "prompt_id": prompt_id,
                "name": name,
                "content": content,
                "version": 1,
                "status": "draft",
                "bound_agents": agent_keys or [],
                "remark": remark,
                "department": department,   # None=通用全院, 具体科室名=专科配对
                "created_by": created_by,
                "created_at": _now(),
                "updated_at": None,
            }
            self.prompt_resources[prompt_id] = item
            # 仅通用资源(department=None)同步覆盖 agent_config.prompt_resource_id
            # 专科配对资源只入 bound_agents，由 resolve 按 department 路由匹配
            for ak in (agent_keys or []):
                cfg = self.agent_config.get(ak)
                if cfg and department is None:
                    cfg["prompt_resource_id"] = prompt_id
            return item

    def get_prompt_resource_by_department(self, agent_key: str, department: str) -> Optional[dict]:
        """按科室找绑定的 online PromptResource（专科配对优先匹配）。"""
        if not department:
            return None
        with self._lock:
            for r in self.prompt_resources.values():
                if (agent_key in r.get("bound_agents", [])
                        and r.get("department") == department
                        and r.get("status") == "online"
                        and r.get("content", "").strip()):
                    return r
        return None

    def update_prompt_resource(self, prompt_id: str, patch: dict) -> Optional[dict]:
        with self._lock:
            item = self.prompt_resources.get(prompt_id)
            if item is None:
                return None
            # 保存历史版本（升级版本号时）
            old_version = item.get("version", 1)
            if "content" in patch and patch["content"] != item.get("content", ""):
                old_content = item.get("content", "")
                item.setdefault("_history", {})[str(old_version)] = old_content
                item["version"] = old_version + 1
            for k in ("name", "content", "status", "remark", "department"):
                if k in patch:
                    item[k] = patch[k]
            if "bound_agents" in patch:
                old_bound = set(item.get("bound_agents", []))
                new_bound = set(patch["bound_agents"])
                # bound_agents 覆盖 agent_config.prompt_resource_id 时，
                # 仅当该资源为通用(department=None)才覆盖默认绑定；专科资源不覆盖
                is_generic = item.get("department") is None
                for ak in old_bound - new_bound:
                    cfg = self.agent_config.get(ak)
                    if cfg and is_generic and cfg.get("prompt_resource_id") == prompt_id:
                        cfg["prompt_resource_id"] = ""
                for ak in new_bound - old_bound:
                    cfg = self.agent_config.get(ak)
                    if cfg and is_generic:
                        cfg["prompt_resource_id"] = prompt_id
                item["bound_agents"] = sorted(new_bound)
            item["updated_at"] = _now()
            return item

    def delete_prompt_resource(self, prompt_id: str) -> bool:
        with self._lock:
            item = self.prompt_resources.pop(prompt_id, None)
            if item:
                for ak in item.get("bound_agents", []):
                    cfg = self.agent_config.get(ak)
                    if cfg and cfg.get("prompt_resource_id") == prompt_id:
                        cfg["prompt_resource_id"] = ""
                return True
            return False

    def bind_prompt_to_agent(self, prompt_id: str, agent_key: str) -> bool:
        with self._lock:
            item = self.prompt_resources.get(prompt_id)
            cfg = self.agent_config.get(agent_key)
            if item is None or cfg is None:
                return False
            if agent_key not in item.get("bound_agents", []):
                item.setdefault("bound_agents", []).append(agent_key)
            cfg["prompt_resource_id"] = prompt_id
            item["updated_at"] = _now()
            return True

    def unbind_prompt_from_agent(self, prompt_id: str, agent_key: str) -> bool:
        with self._lock:
            item = self.prompt_resources.get(prompt_id)
            cfg = self.agent_config.get(agent_key)
            if item is None or cfg is None:
                return False
            item["bound_agents"] = [a for a in item.get("bound_agents", []) if a != agent_key]
            if cfg.get("prompt_resource_id") == prompt_id:
                cfg["prompt_resource_id"] = ""
            item["updated_at"] = _now()
            return True

    # ==================== OutputSchema 资源管理（版本化） ====================
    def list_schema_resources(self, agent_key: Optional[str] = None) -> List[dict]:
        with self._lock:
            items = list(self.schema_resources.values())
        if agent_key:
            items = [r for r in items if agent_key in r.get("bound_agents", [])]
        return items

    def get_schema_resource(self, schema_id: str) -> Optional[dict]:
        with self._lock:
            return self.schema_resources.get(schema_id)

    def add_schema_resource(self, *, name: str, json_schema: dict, created_by: str,
                            agent_keys: Optional[List[str]] = None,
                            remark: str = "",
                            department: Optional[str] = None) -> dict:
        with self._lock:
            schema_id = _uid("sr")
            item = {
                "schema_id": schema_id,
                "name": name,
                "json_schema": json_schema,
                "version": 1,
                "status": "draft",
                "bound_agents": agent_keys or [],
                "remark": remark,
                "department": department,   # None=通用, 具体科室名=专科配对
                "created_by": created_by,
                "created_at": _now(),
                "updated_at": None,
            }
            self.schema_resources[schema_id] = item
            # 仅通用资源覆盖 agent_config.schema_resource_id
            for ak in (agent_keys or []):
                cfg = self.agent_config.get(ak)
                if cfg and department is None:
                    cfg["schema_resource_id"] = schema_id
            return item

    def get_schema_resource_by_department(self, agent_key: str, department: str) -> Optional[dict]:
        """按科室找绑定的 online SchemaResource（专科配对优先匹配）。"""
        if not department:
            return None
        with self._lock:
            for r in self.schema_resources.values():
                if (agent_key in r.get("bound_agents", [])
                        and r.get("department") == department
                        and r.get("status") == "online"
                        and r.get("json_schema")):
                    return r
        return None

    def update_schema_resource(self, schema_id: str, patch: dict) -> Optional[dict]:
        with self._lock:
            item = self.schema_resources.get(schema_id)
            if item is None:
                return None
            for k in ("name", "status", "remark", "department"):
                if k in patch:
                    item[k] = patch[k]
            if "json_schema" in patch:
                old_version = item.get("version", 1)
                old_schema = item.get("json_schema", {})
                item.setdefault("_history", {})[str(old_version)] = old_schema
                item["json_schema"] = patch["json_schema"]
                item["version"] = old_version + 1
            if "bound_agents" in patch:
                old_bound = set(item.get("bound_agents", []))
                new_bound = set(patch["bound_agents"])
                # 仅通用资源(department=None)覆盖 agent_config.schema_resource_id
                is_generic = item.get("department") is None
                for ak in old_bound - new_bound:
                    cfg = self.agent_config.get(ak)
                    if cfg and is_generic and cfg.get("schema_resource_id") == schema_id:
                        cfg["schema_resource_id"] = ""
                for ak in new_bound - old_bound:
                    cfg = self.agent_config.get(ak)
                    if cfg and is_generic:
                        cfg["schema_resource_id"] = schema_id
                item["bound_agents"] = sorted(new_bound)
            item["updated_at"] = _now()
            return item

    def delete_schema_resource(self, schema_id: str) -> bool:
        with self._lock:
            item = self.schema_resources.pop(schema_id, None)
            if item:
                for ak in item.get("bound_agents", []):
                    cfg = self.agent_config.get(ak)
                    if cfg and cfg.get("schema_resource_id") == schema_id:
                        cfg["schema_resource_id"] = ""
                return True
            return False

    def bind_schema_to_agent(self, schema_id: str, agent_key: str) -> bool:
        with self._lock:
            item = self.schema_resources.get(schema_id)
            cfg = self.agent_config.get(agent_key)
            if item is None or cfg is None:
                return False
            if agent_key not in item.get("bound_agents", []):
                item.setdefault("bound_agents", []).append(agent_key)
            cfg["schema_resource_id"] = schema_id
            item["updated_at"] = _now()
            return True

    def unbind_schema_from_agent(self, schema_id: str, agent_key: str) -> bool:
        with self._lock:
            item = self.schema_resources.get(schema_id)
            cfg = self.agent_config.get(agent_key)
            if item is None or cfg is None:
                return False
            item["bound_agents"] = [a for a in item.get("bound_agents", []) if a != agent_key]
            if cfg.get("schema_resource_id") == schema_id:
                cfg["schema_resource_id"] = ""
            item["updated_at"] = _now()
            return True

    # —— 版本对比（v2 调试工具） ——
    def compare_prompt_versions(self, prompt_id: str, v1: int, v2: int) -> Optional[dict]:
        """对比两个版本的 Prompt 内容差异（简易 diff，返回前后文本）。"""
        with self._lock:
            current = self.prompt_resources.get(prompt_id)
            if not current:
                return None
            # 从历史版本中获取（当前版本 + 快照）
            hist = current.get("_history", {})
            content_v1 = hist.get(str(v1), current.get("content", "")) if v1 == current.get("version") else hist.get(str(v1))
            content_v2 = current.get("content", "") if v2 == current.get("version") else hist.get(str(v2))
            if not content_v1 or not content_v2:
                return None
            return {"v1": v1, "v2": v2, "content_v1": content_v1, "content_v2": content_v2}

    def compare_schema_versions(self, schema_id: str, v1: int, v2: int) -> Optional[dict]:
        """对比两个版本的 OutputSchema JSON 差异。"""
        with self._lock:
            current = self.schema_resources.get(schema_id)
            if not current:
                return None
            hist = current.get("_history", {})
            schema_v1 = hist.get(str(v1), current.get("json_schema", {})) if v1 == current.get("version") else hist.get(str(v1))
            schema_v2 = current.get("json_schema", {}) if v2 == current.get("version") else hist.get(str(v2))
            if schema_v1 is None or schema_v2 is None:
                return None
            return {"v1": v1, "v2": v2, "schema_v1": schema_v1, "schema_v2": schema_v2}

    # —— Agent 资源绑定读写（v2 适配） ——
    def get_agent_resource_ids(self, agent_key: str) -> dict:
        """获取 Agent 当前绑定的 resource_id（优先 v2 引用，回退旧字段）。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            return {
                "prompt_resource_id": cfg.get("prompt_resource_id", ""),
                "schema_resource_id": cfg.get("schema_resource_id", ""),
            }

    def update_agent_resource_ids(self, agent_key: str, *,
                                   prompt_resource_id: Optional[str] = None,
                                   schema_resource_id: Optional[str] = None) -> dict:
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                raise KeyError(f"未知 Agent: {agent_key}")
            old_pid = cfg.get("prompt_resource_id", "")
            old_sid = cfg.get("schema_resource_id", "")
            if prompt_resource_id is not None:
                cfg["prompt_resource_id"] = prompt_resource_id
            if schema_resource_id is not None:
                cfg["schema_resource_id"] = schema_resource_id
            # 同步 Prompt/Schema 资源的 bound_agents
            new_pid = cfg.get("prompt_resource_id", "")
            new_sid = cfg.get("schema_resource_id", "")
            if old_pid != new_pid:
                if old_pid:
                    pr = self.prompt_resources.get(old_pid)
                    if pr and agent_key in pr.get("bound_agents", []):
                        pr["bound_agents"] = [a for a in pr["bound_agents"] if a != agent_key]
                if new_pid:
                    pr = self.prompt_resources.get(new_pid)
                    if pr and agent_key not in pr.get("bound_agents", []):
                        pr["bound_agents"].append(agent_key)
            if old_sid != new_sid:
                if old_sid:
                    sr = self.schema_resources.get(old_sid)
                    if sr and agent_key in sr.get("bound_agents", []):
                        sr["bound_agents"] = [a for a in sr["bound_agents"] if a != agent_key]
                if new_sid:
                    sr = self.schema_resources.get(new_sid)
                    if sr and agent_key not in sr.get("bound_agents", []):
                        sr["bound_agents"].append(agent_key)
            return {"agent_key": agent_key,
                    "prompt_resource_id": cfg.get("prompt_resource_id", ""),
                    "schema_resource_id": cfg.get("schema_resource_id", "")}

    # ==================== 模型资源管理（独立模型池） ====================

    def add_model_resource(self, *, provider: str, model: str, api_key: str,
                           base_url: str = "", timeout: int = 30,
                           agent_keys: Optional[List[str]] = None,
                           remark: str = "") -> dict:
        """创建模型资源。"""
        with self._lock:
            model_id = _uid("mod")
            item = {
                "model_id": model_id,
                "provider": provider,
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
                "timeout": timeout,
                "status": "active",  # active / inactive
                "bound_agents": agent_keys or [],
                "remark": remark,
                "created_at": _now(),
                "updated_at": None,
            }
            self.model_resources[model_id] = item
            # 同步绑定到 Agent
            for ak in (agent_keys or []):
                cfg = self.agent_config.get(ak)
                if cfg:
                    cfg["model_resource_id"] = model_id
            return item

    def list_model_resources(self, agent_key: Optional[str] = None) -> List[dict]:
        """列出模型资源。"""
        with self._lock:
            out = list(self.model_resources.values())
        if agent_key:
            out = [m for m in out if agent_key in m.get("bound_agents", [])]
        out.sort(key=lambda m: m.get("created_at", ""), reverse=True)
        return out

    def get_model_resource(self, model_id: str) -> Optional[dict]:
        """获取单个模型资源。"""
        with self._lock:
            return self.model_resources.get(model_id)

    def update_model_resource(self, model_id: str, patch: dict) -> Optional[dict]:
        """更新模型资源（不修改 api_key 除非显式传入）。"""
        with self._lock:
            item = self.model_resources.get(model_id)
            if item is None:
                return None
            for k in ("provider", "model", "base_url", "timeout", "status", "remark"):
                if k in patch:
                    item[k] = patch[k]
            # api_key: 仅当显式传入时更新
            if "api_key" in patch:
                item["api_key"] = patch["api_key"]
            if "bound_agents" in patch:
                old_bound = set(item.get("bound_agents", []))
                new_bound = set(patch["bound_agents"])
                for ak in old_bound - new_bound:
                    cfg = self.agent_config.get(ak)
                    if cfg and cfg.get("model_resource_id") == model_id:
                        cfg["model_resource_id"] = ""
                for ak in new_bound - old_bound:
                    cfg = self.agent_config.get(ak)
                    if cfg:
                        cfg["model_resource_id"] = model_id
                item["bound_agents"] = sorted(new_bound)
            item["updated_at"] = _now()
            return item

    def delete_model_resource(self, model_id: str) -> bool:
        """删除模型资源（解绑所有 Agent）。"""
        with self._lock:
            item = self.model_resources.pop(model_id, None)
            if item:
                for ak in item.get("bound_agents", []):
                    cfg = self.agent_config.get(ak)
                    if cfg and cfg.get("model_resource_id") == model_id:
                        cfg["model_resource_id"] = ""
                return True
            return False

    def bind_model_to_agent(self, model_id: str, agent_key: str) -> bool:
        """绑定模型资源到 Agent。"""
        with self._lock:
            item = self.model_resources.get(model_id)
            cfg = self.agent_config.get(agent_key)
            if item is None or cfg is None:
                return False
            if agent_key not in item.get("bound_agents", []):
                item.setdefault("bound_agents", []).append(agent_key)
            cfg["model_resource_id"] = model_id
            item["updated_at"] = _now()
            return True

    def unbind_model_from_agent(self, model_id: str, agent_key: str) -> bool:
        """解除模型资源与 Agent 的绑定。"""
        with self._lock:
            item = self.model_resources.get(model_id)
            cfg = self.agent_config.get(agent_key)
            if item is None or cfg is None:
                return False
            item["bound_agents"] = [a for a in item.get("bound_agents", []) if a != agent_key]
            if cfg.get("model_resource_id") == model_id:
                cfg["model_resource_id"] = ""
            item["updated_at"] = _now()
            return True

    def get_agent_model_resource_id(self, agent_key: str) -> str:
        """获取 Agent 当前绑定的 model_resource_id。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                return ""
            return cfg.get("model_resource_id", "")

    # ==================== 系统审计日志（跨患者，后台专用） ====================
    def append_system_audit(self, *, operator_id: str, operator_name: str, action: str,
                            entity: str, entity_id: str = "", before: Optional[dict] = None,
                            after: Optional[dict] = None) -> None:
        with self._lock:
            entry = {
                "log_id": _uid("slog"),
                "operator_id": operator_id,
                "operator_name": operator_name,
                "action": action,        # create/update/delete/activate/deactivate/agent_toggle/archive...
                "entity": entity,        # building/department/user/exam_item/rag_doc/agent_config/case...
                "entity_id": entity_id,
                "before": before,
                "after": after,
                "timestamp": _now(),
            }
            self.system_audit_log.append(entry)

    def list_system_audit(self, action: Optional[str] = None,
                          entity: Optional[str] = None) -> List[dict]:
        with self._lock:
            out = list(self.system_audit_log)
        if action:
            out = [e for e in out if e["action"] == action]
        if entity:
            out = [e for e in out if e["entity"] == entity]
        out.sort(key=lambda e: e["timestamp"], reverse=True)
        return out

    # ==================== 归档病案查阅（只读，从 patients 派生） ====================
    def list_archived_cases(self, patient_id: Optional[str] = None,
                            doctor_id: Optional[str] = None) -> List[dict]:
        """归档病案列表（只读快照，不修改原始 State）。"""
        with self._lock:
            out = []
            for pid, state in self.patients.items():
                if patient_id and pid != patient_id:
                    continue
                if doctor_id and doctor_id not in state.get("attending_doctor_ids", []):
                    continue
                out.append({
                    "patient_id": pid,
                    "patient_name": state.get("patient_name", ""),
                    "status": state.get("status", ""),
                    "attending_doctor_ids": state.get("attending_doctor_ids", []),
                    "emr_locked": state.get("emr_main", {}).get("locked", False),
                    "treatment_count": len(state.get("treatment_versions", [])),
                    "mdt_comment_count": len(state.get("mdt_comments", [])),
                    "check_task_count": len(state.get("check_tasks", [])),
                    "audit_log_count": len(state.get("audit_log", [])),
                })
        return out

    def get_archived_case_detail(self, patient_id: str) -> Optional[dict]:
        """归档病案详情（只读，返回完整 State 快照）。"""
        with self._lock:
            state = self.patients.get(patient_id)
            if state is None:
                return None
            # 返回只读快照（禁止通过此接口修改）
            return dict(state)


# 模块级单例
store = Store()


def uid(prefix: str) -> str:
    return _uid(prefix)


def now() -> str:
    return _now()
