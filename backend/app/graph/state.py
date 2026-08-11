"""LangGraph 全局 State 定义（TypedDict）。

PatientState 是整个 Workflow 的全局状态，贯穿 7 个节点。
设计原则：
- 规则节点不调用 LLM，只读写本 State；
- SubAgent 节点根据 enable_*_subagent 开关分支（方案A：同一节点内 if 分支）；
- AI 草稿（ai_draft）与正式主病历（emr_main）物理隔离，AI 输出绝不自动写入 emr_main；
- 采纳标记（MdtComment.is_adopted）独立留痕，不依靠病历文本反推。
"""
from __future__ import annotations

from typing import List, Optional, TypedDict


class EmrMain(TypedDict, total=False):
    """正式主病历（HITL 终审后才锁定）。"""

    content: str           # 正文
    locked: bool           # 是否定稿锁定
    locked_at: Optional[str]
    locked_by: Optional[str]
    locked_by_name: Optional[str]


class TreatmentVersion(TypedDict, total=False):
    """诊疗方案版本（只增不改，倒序存储）。"""

    version_id: str
    version_no: int                  # 版本号，从 1 递增
    content: str                     # 方案原文
    created_at: str                  # ISO 时间戳
    created_by: str
    created_by_name: str


class MdtComment(TypedDict, total=False):
    """MDT 专家意见（提交后冻结，不可修改删除）。"""

    comment_id: str
    author_id: str
    author_name: str
    author_role: str
    content: str
    created_at: str
    is_adopted: bool                 # 采纳标记，独立留痕
    adopted_by: Optional[str]
    adopted_by_name: Optional[str]
    adopted_at: Optional[str]


class CheckTask(TypedDict, total=False):
    """检查任务（Mock 流转：已开立 → 待执行 → 已完成）。"""

    task_id: str
    task_type: str                   # blood / ct / ultrasound
    task_label: str                  # 中文名：血常规 / CT / B超
    status: str                      # ordered / pending / done
    created_at: str
    created_by: str
    created_by_name: str
    completed_at: Optional[str]
    result: Optional[dict]           # 完成后结构化结果回填


class MdtInvitation(TypedDict, total=False):
    """MDT 邀请临时授权（带时效）。"""

    invitation_id: str
    expert_id: str
    expert_name: str
    invited_at: str
    expires_at: str                  # 时效控制
    active: bool                     # 是否仍有效


class AuditLogEntry(TypedDict, total=False):
    """审计日志（纯规则落盘）。"""

    log_id: str
    action: str
    actor_id: str
    actor_name: str
    detail: str
    timestamp: str


class NotifyEvent(TypedDict, total=False):
    """Mock 站内通知。"""

    notify_id: str
    type: str                        # mdt_invited / mdt_adopted / check_done / ...
    target_user_id: str
    message: str
    created_at: str
    read: bool


class PatientState(TypedDict, total=False):
    """LangGraph 全局状态：单个患者的完整诊疗上下文。"""

    # —— 患者与权限范围 ——
    patient_id: str
    patient_name: str
    attending_doctor_ids: List[str]          # 主治医生（数据范围 + 动作权限）
    mdt_invitations: List[MdtInvitation]     # MDT 临时授权白名单（时效）

    # —— 病历与方案 ——
    emr_main: EmrMain                        # 正式主病历（HITL 锁定）
    treatment_versions: List[TreatmentVersion]  # 历史诊疗方案（倒序，只增不改）
    ai_draft: Optional[str]                  # AI 草稿（隔离区，不进 emr_main）

    # —— MDT ——
    mdt_comments: List[MdtComment]

    # —— 检查任务 ——
    check_tasks: List[CheckTask]

    # —— SubAgent 开关（方案A：节点内 if 分支）——
    enable_emr_subagent: bool
    enable_lab_subagent: bool

    # —— 留痕 ——
    audit_log: List[AuditLogEntry]
    notify_queue: List[NotifyEvent]

    # —— 流转状态 ——
    status: str                              # waiting / in_progress / archived
    hitl_pending: bool                       # 是否等待人工终审
