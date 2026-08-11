"""内存 Mock 存储（Demo 简化，不引入数据库）。

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


# 权限矩阵：4 个临床角色 × 11 个动作开关（admin 角色独立，固定拥有后台管理权限）
PERMISSION_ROLES = ["attending", "mdt_expert", "nurse", "readonly"]
PERMISSION_ACTIONS = [
    "can_view_emr", "can_edit_emr", "can_lock_emr", "can_generate_ai",
    "can_open_check", "can_invite_mdt", "can_adopt_comment", "can_submit_comment",
    "can_view_history", "can_view_mdt", "can_view_check",
]

# 知识库分类
KB_CATEGORIES = {
    "guide": "临床指南/诊疗常规",
    "soap_template": "SOAP 病历模板",
    "drug_dict": "药品/检查项字典",
    "mdt_template": "MDT 会诊模板",
}


def default_permission_matrix() -> Dict[str, Dict[str, bool]]:
    """默认权限矩阵（与原硬编码一致，作为后台可编辑初始值）。"""
    return {
        "attending": {
            "can_view_emr": True, "can_edit_emr": True, "can_lock_emr": True,
            "can_generate_ai": True, "can_open_check": True, "can_invite_mdt": True,
            "can_adopt_comment": True, "can_submit_comment": False,
            "can_view_history": True, "can_view_mdt": True, "can_view_check": True,
        },
        "mdt_expert": {
            "can_view_emr": True, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": True,
            "can_view_history": True, "can_view_mdt": True, "can_view_check": True,
        },
        "nurse": {
            "can_view_emr": False, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": False,
            "can_view_history": False, "can_view_mdt": False, "can_view_check": True,
        },
        "readonly": {
            "can_view_emr": True, "can_edit_emr": False, "can_lock_emr": False,
            "can_generate_ai": False, "can_open_check": False, "can_invite_mdt": False,
            "can_adopt_comment": False, "can_submit_comment": False,
            "can_view_history": True, "can_view_mdt": True, "can_view_check": True,
        },
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
        self.kb_entries: Dict[str, dict] = {}
        self.permission_matrix: Dict[str, Dict[str, bool]] = default_permission_matrix()
        # 后台扩展：主数据 / RAG文档 / 系统审计 / Agent灰度配置
        self.buildings: Dict[str, dict] = {}           # 楼宇(含楼层/房间)
        self.exam_items: Dict[str, dict] = {}           # 检验/检查项目字典
        self.rag_docs: Dict[str, dict] = {}             # RAG文档(含chunks+Mock向量)
        self.system_audit_log: List[dict] = []          # 系统审计日志(跨患者)
        self.agent_config: dict = {                     # Agent能力灰度配置
            "emr_agent": {"global": True, "hospitals": {}},
            "imaging_agent": {"global": False, "hospitals": {}},
        }
        self.patient_users: Dict[str, dict] = {}  # 患者端登录用户（patient_id -> info）
        self.patient_events: List[dict] = []       # 患者端行为埋点事件

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

    def create_user(self, *, username, password, name, role, department, title) -> dict:
        with self._lock:
            user = {
                "user_id": _uid("u"),
                "username": username,
                "password": password,
                "name": name,
                "role": role,
                "department": department,
                "title": title,
                "active": True,
            }
            self.users[user["user_id"]] = user
            return user

    def update_user(self, user_id: str, patch: dict) -> Optional[dict]:
        with self._lock:
            user = self.users.get(user_id)
            if user is None:
                return None
            for k in ("name", "role", "department", "title", "password", "active"):
                if k in patch:
                    user[k] = patch[k]
            return user

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
            # 仅接受已知角色与动作，忽略非法键
            new_matrix = default_permission_matrix()
            for role in PERMISSION_ROLES:
                if role in matrix:
                    for act in PERMISSION_ACTIONS:
                        if act in matrix[role]:
                            new_matrix[role][act] = bool(matrix[role][act])
            self.permission_matrix = new_matrix
            return self.get_permission_matrix()

    def role_permissions(self, role: str) -> Dict[str, bool]:
        """读取某角色的动作权限（admin 角色返回全 False 临床权限）。"""
        with self._lock:
            if role == "admin":
                return {a: False for a in PERMISSION_ACTIONS}
            return dict(self.permission_matrix.get(role, {a: False for a in PERMISSION_ACTIONS}))

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
                    r = {"room_id": _uid("rm"), "name": room_name, "dept_name": dept_name}
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
    EXAM_CATEGORIES = {"blood": "血液检验", "ct": "CT影像", "ultrasound": "超声", "pathology": "病理", "other": "其他"}

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
                k: {"global": v["global"], "hospitals": dict(v["hospitals"])}
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

    def is_agent_enabled(self, agent_key: str, hospital_id: str = "") -> bool:
        """供 LangGraph 节点查询：医院级覆盖 > 全局开关。"""
        with self._lock:
            cfg = self.agent_config.get(agent_key)
            if cfg is None:
                return False
            if hospital_id and hospital_id in cfg["hospitals"]:
                return cfg["hospitals"][hospital_id]
            return cfg["global"]

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
