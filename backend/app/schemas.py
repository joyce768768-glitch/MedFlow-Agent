"""Pydantic 请求/响应模型（API 契约）。"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- 鉴权 ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    user_id: str
    username: str
    name: str
    role: str
    department: str
    title: str


# ---------- 患者 ----------
class PatientSummary(BaseModel):
    patient_id: str
    patient_name: str
    status: str
    attending_doctor_ids: List[str]
    check_task_count: int
    mdt_comment_count: int


# ---------- 诊疗方案 ----------
class NewTreatmentRequest(BaseModel):
    content: str = Field(..., description="新诊疗方案原文（新建版本，不覆盖旧版）")


class TreatmentVersionOut(BaseModel):
    version_id: str
    version_no: int
    content: str
    created_at: str
    created_by: str
    created_by_name: str


# ---------- MDT ----------
class MdtCommentIn(BaseModel):
    content: str


class MdtCommentOut(BaseModel):
    comment_id: str
    author_id: str
    author_name: str
    author_role: str
    content: str
    created_at: str
    is_adopted: bool
    adopted_by: Optional[str]
    adopted_by_name: Optional[str]
    adopted_at: Optional[str]


class MdtInviteRequest(BaseModel):
    expert_id: str
    expires_hours: int = 72


# ---------- 病历 ----------
class EmrUpdateRequest(BaseModel):
    content: str


class EmrLockRequest(BaseModel):
    locked: bool


class AiDraftResponse(BaseModel):
    ai_draft: str
    enabled: bool


# ---------- 检查任务 ----------
class CheckTaskCreate(BaseModel):
    task_type: str = Field(..., description="blood / ct / ultrasound")
    task_label: str


class CheckTaskStatusUpdate(BaseModel):
    status: str = Field(..., description="ordered / pending / done")


class CheckTaskOut(BaseModel):
    task_id: str
    task_type: str
    task_label: str
    status: str
    created_at: str
    created_by: str
    created_by_name: str
    completed_at: Optional[str]
    result: Optional[dict]


# ---------- 配置 ----------
class SubAgentConfigOut(BaseModel):
    enable_emr_subagent: bool
    enable_lab_subagent: bool


class SubAgentConfigUpdate(BaseModel):
    enable_emr_subagent: bool
    enable_lab_subagent: bool


# ---------- 通知 ----------
class NotifyOut(BaseModel):
    notify_id: str
    type: str
    target_user_id: str
    message: str
    created_at: str
    read: bool


# ---------- 权限视图 ----------
class PermissionView(BaseModel):
    """返回给前端的动作权限位（仅做视图显隐，安全以后端为准）。"""
    role: str
    can_view_emr: bool           # 查看主病历（护士隐藏）
    can_edit_emr: bool           # 主病历编辑器
    can_lock_emr: bool           # 定稿锁定
    can_generate_ai: bool        # AI 草稿生成
    can_open_check: bool         # 开立检查任务
    can_invite_mdt: bool         # 邀请专家
    can_adopt_comment: bool      # 采纳专家意见
    can_submit_comment: bool     # 提交 MDT 评论
    can_view_history: bool       # 查看历史版本折叠
    can_view_mdt: bool           # 查看 MDT 讨论区
    can_view_check: bool         # 查看检查任务


LoginResponse.model_rebuild()


# ---------- 后台管理：用户 ----------
class AdminUserOut(BaseModel):
    user_id: str
    username: str
    name: str
    role: str
    department: str
    title: str
    active: bool


class AdminUserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: str = Field(..., description="attending / mdt_expert / nurse / readonly / admin")
    department: str
    title: str = ""


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    password: Optional[str] = None
    active: Optional[bool] = None


# ---------- 科室 ----------
class DepartmentOut(BaseModel):
    dept_id: str
    name: str
    created_at: str


class DepartmentCreate(BaseModel):
    name: str


# ---------- 知识库 ----------
class KbEntryOut(BaseModel):
    kb_id: str
    category: str
    title: str
    content: str
    tags: List[str]
    created_at: str
    updated_at: str


class KbEntryCreate(BaseModel):
    category: str = Field(..., description="guide / soap_template / drug_dict / mdt_template")
    title: str
    content: str
    tags: List[str] = []


class KbEntryUpdate(BaseModel):
    title: str
    content: str
    tags: List[str] = []


# ---------- 权限矩阵 ----------
class PermissionMatrixOut(BaseModel):
    roles: List[str]
    actions: List[str]
    matrix: Dict[str, Dict[str, bool]]


class PermissionMatrixUpdate(BaseModel):
    matrix: Dict[str, Dict[str, bool]]


# ==================== 后台扩展：主数据 ====================
class BuildingOut(BaseModel):
    building_id: str
    name: str
    floors: List[dict] = []
    created_at: str


class BuildingCreate(BaseModel):
    name: str


class FloorCreate(BaseModel):
    name: str


class RoomBind(BaseModel):
    room_name: str
    dept_name: str


class ExamItemOut(BaseModel):
    item_id: str
    code: str
    name: str
    category: str
    spec: str = ""
    ref_range: str = ""
    created_at: str


class ExamItemCreate(BaseModel):
    code: str
    name: str
    category: str = Field(..., description="blood/ct/ultrasound/pathology/other")
    spec: str = ""
    ref_range: str = ""


class ExamItemUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    spec: Optional[str] = None
    ref_range: Optional[str] = None


# ==================== RAG 文档库 ====================
class RagDocOut(BaseModel):
    doc_id: str
    title: str
    category: str
    content: str
    chunks: List[dict] = []
    version: int
    status: str            # pending / active / inactive
    uploaded_by: str
    uploaded_by_name: str
    created_at: str
    updated_at: str
    history: List[dict] = []


class RagDocCreate(BaseModel):
    title: str
    category: str = Field(..., description="clinical_guide/soap_template/sop/mdt_template")
    content: str


class RagDocUpdate(BaseModel):
    title: str
    content: str


class RagDocStatusUpdate(BaseModel):
    status: str = Field(..., description="pending / active / inactive")


class RagRecallRequest(BaseModel):
    query: str
    top_k: int = 3


class RagRecallHit(BaseModel):
    chunk_id: str
    text: str
    vector_mock: List[float] = []
    chunk_no: int
    doc_id: str
    doc_title: str
    category: str
    score_mock: float


# ==================== Agent 能力配置 ====================
class AgentConfigOut(BaseModel):
    patient_triage_agent: dict
    emr_agent: dict
    imaging_agent: dict


class AgentToggleRequest(BaseModel):
    agent_key: str = Field(..., description="patient_triage_agent / emr_agent / imaging_agent")
    global_on: Optional[bool] = None
    hospital_id: Optional[str] = None
    hospital_on: Optional[bool] = None


class AgentModelConfigOut(BaseModel):
    """单个 Agent 模型配置返回（api_key 脱敏）。"""
    agent_key: str
    provider: str
    enable_real: int
    model: str
    base_url: str
    api_key_masked: str
    api_key_configured: bool
    timeout: int
    real_active: bool
    prompt: str = ""          # 自定义 System Prompt，空=使用默认
    prompt_is_default: bool = True
    output_schema: str = ""   # 自定义输出 Schema，空=使用默认
    output_schema_is_default: bool = True


class AgentModelConfigUpdate(BaseModel):
    """单个 Agent 模型配置更新。
    api_key 语义：None=不改，''=清除，非空=覆盖。
    prompt 语义：None=不改，''=清除自定义恢复默认，非空=覆盖。
    output_schema 语义：None=不改，''=清除自定义恢复默认，非空=覆盖。
    """
    provider: Optional[str] = None
    enable_real: Optional[int] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[int] = None
    prompt: Optional[str] = None
    output_schema: Optional[str] = None


# ==================== 归档病案 ====================
class ArchivedCaseSummary(BaseModel):
    patient_id: str
    patient_name: str
    status: str
    attending_doctor_ids: List[str]
    emr_locked: bool
    treatment_count: int
    mdt_comment_count: int
    check_task_count: int
    audit_log_count: int


# ==================== 系统审计日志 ====================
class SystemAuditOut(BaseModel):
    log_id: str
    operator_id: str
    operator_name: str
    action: str
    entity: str
    entity_id: str = ""
    before: Optional[dict] = None
    after: Optional[dict] = None
    timestamp: str
