"""M3 双 Agent 编排：查询规划 Agent + 校验 Agent + 带依据回答。

三铁律的编排层落地（契约参考实现在 semantic_contract.orchestration，本模块
是医疗域的组装与领域规则）：

    NL 问题
      → [校验·第一道] 意图边界：诊断/处方类问题在生成之前拦截（不浪费规划调用）
      → [查询规划 Agent] semantic_registry 注入 prompt（铁律①：注入语义不注入 DDL）
         真 LLM 输出 JSON 计划；解析失败重试 1 次；仍失败 → rule_plan 关键词兜底
      → [校验·第二道] 视图合法性：臆造 view_id 拦截 / blocked 视图治理解释
      → [校验·第三道] 编译期机判：compile_view 的 machine_check
      → [执行] compile → execute → 数据 + sql + provenance（铁律②）
      → [回答] 真 LLM 基于口径与结果作答（数字只从结果引用）

供型：强制真 LLM（openai_compatible，复用 llm_client 统一传输与埋点）。
未配置 API key → LLMNotConfiguredError，路由层转 503 配置指引；不做 Mock 演示降级。
规划兜底（rule_plan）是解析鲁棒性手段——只在「LLM 输出无法解析为合法计划」时触发，
LLM 网络失败直接上抛，不静默降级。
"""
from __future__ import annotations

from typing import Any, Dict, List

from semantic_contract import (
    PlanParseError,
    compile_view,
    execute,
    load_entity,
    open_sqlite,
    parse_plan,
    planner_prompt,
    rule_plan,
    answer_prompt,
    semantic_registry,
    validate_plan,
)

from .config import settings
from .database import _DB_PATH, ensure_schema
from .llm_client import _call_openai_compatible

_ENTITY = load_entity("medflow")
_REGISTRY = semantic_registry(_ENTITY)

PROVIDER_USED = "openai_compatible"

# —— 校验 Agent · 第一道：意图边界（规则优先于 LLM，吸收 policy_guard 结构）——
# 问题侧关键词机判：命中即 block，规划调用都不发起（生成之前拦截）
QUESTION_FORBIDDEN_KEYWORDS = (
    "确诊", "诊断", "处方", "开药", "吃什么药", "用药建议", "治疗方案", "怎么治",
)
BOUNDARY_REPLY = (
    "我是医疗数据统计助手，只能回答语义视图覆盖的经营/流程统计问题，"
    "不提供诊断、处方或治疗建议。如需诊疗支持，请走医生确认工作台（HITL 流程）。"
)


class LLMNotConfiguredError(RuntimeError):
    """强制真 LLM 策略：未配置 API Key 时链路不可用（配置问题，不是运行时故障）。"""


def _llm(messages: List[dict]) -> str:
    """强制真 LLM 统一出口：无 key 直接拒绝，复用 llm_client 传输（重试/埋点内聚）。"""
    if not settings.llm_api_key:
        raise LLMNotConfiguredError(
            "未配置 LLM API Key（settings.llm_api_key 为空）。"
            "语义问答链路为强制真 LLM 供型，不做 Mock 降级；"
            "请在环境变量中配置 llm_api_key / llm_base_url / llm_model 后重试。"
        )
    return _call_openai_compatible(messages)


# ============================================================
# 1. 查询规划 Agent
# ============================================================

def plan_query(question: str) -> Dict[str, Any]:
    """NL → 查询计划。真 LLM JSON 规划，解析失败重试 1 次，仍失败规则兜底。

    返回 {plan, planner}；planner ∈ llm | llm_retry | rule_fallback | rule_fallback_none。
    """
    messages = [
        {"role": "system", "content": planner_prompt(_REGISTRY)},
        {"role": "user", "content": question},
    ]
    planner = "llm"
    for attempt in (1, 2):
        raw = _llm(messages)
        try:
            plan = parse_plan(raw, _REGISTRY)
            return {"plan": plan, "planner": planner}
        except PlanParseError:
            if attempt == 1:
                planner = "llm_retry"

    # 两次解析均失败 → 关键词规则兜底（命不中也是合法计划：view_id=None）
    plan = rule_plan(question, _REGISTRY) or {
        "view_id": None,
        "intent": "metric_query",
        "filters": {},
        "reasoning": "规则兜底未命中任何视图",
    }
    planner = "rule_fallback" if plan.get("view_id") else "rule_fallback_none"
    plan.setdefault("planner", "rule_fallback")
    return {"plan": plan, "planner": planner}


# ============================================================
# 2. 校验 Agent（独立于生成；规则优先于 LLM）
# ============================================================

def validate(question: str, plan: dict) -> Dict[str, Any]:
    """三道校验中的前两道（第三道 machine_check 在 compile_view 内）。

    VA-001 意图边界：问题关键词机判 ∪ 规划意图枚举（LLM intent 仅作交叉信号）
    VA-002 视图合法性：臆造拦截 / blocked 治理解释（契约 validate_plan）
    """
    violations: List[dict] = []

    hits = [kw for kw in QUESTION_FORBIDDEN_KEYWORDS if kw in question]
    if hits:
        violations.append({
            "rule_id": "VA-001",
            "severity": "block",
            "message": f"问题包含诊疗越界关键词（{('、'.join(hits))}），已按 medflow.policy.no_direct_ai_diagnosis 拦截",
            "agent": "semantic_validator",
        })
    elif plan.get("intent") in ("diagnosis_request", "prescription_request"):
        violations.append({
            "rule_id": "VA-001",
            "severity": "block",
            "message": f"规划意图为 {plan.get('intent')}（诊疗越界），已按 medflow.policy.no_direct_ai_diagnosis 拦截",
            "agent": "semantic_validator",
        })

    violations.extend(validate_plan(plan, _ENTITY))

    return {"passed": not violations, "violations": violations}


# ============================================================
# 3. 执行 + 回答
# ============================================================

def execute_plan(plan: dict) -> Dict[str, Any]:
    """编译（内含第三道机判）→ SQLite 实跑 → 数据 + provenance。"""
    q = compile_view(_ENTITY, plan["view_id"], dialect="sqlite", params=plan.get("filters") or {})
    ensure_schema()  # 幂等；演示库可能尚未初始化
    conn = open_sqlite(_DB_PATH)
    try:
        return execute(q, conn)
    finally:
        conn.close()


def answer_question(question: str, plan: dict, result: dict) -> str:
    """带依据回答：口径元数据 + 结果 + provenance → 真 LLM 作答。"""
    view_meta = next(v for v in _REGISTRY if v["id"] == plan["view_id"])
    return _llm(answer_prompt(question, view_meta, result))


def _no_view_reply() -> str:
    names = "、".join(v["name_zh"] for v in _REGISTRY)
    return (
        "当前语义视图注册表中没有能回答该问题的视图，不做臆测。"
        f"已发布视图：{names}。"
    )


# ============================================================
# 4. 编排入口
# ============================================================

def ask_question(question: str) -> Dict[str, Any]:
    """双 Agent 编排主链路。返回结构（stage = answered|blocked|no_view）：

    {question, reply, stage, plan, planner, validation, view,
     data, sql, provenance, provider_used}
    """
    base = {"question": question, "provider_used": PROVIDER_USED}

    # 校验·第一道：意图边界（生成之前拦截）
    pre = validate(question, {"intent": "metric_query", "view_id": None})
    if not pre["passed"]:
        return {**base, "stage": "blocked", "reply": BOUNDARY_REPLY,
                "plan": None, "planner": None, "validation": pre,
                "view": None, "data": None, "sql": None, "provenance": None}

    # 查询规划 Agent
    planned = plan_query(question)
    plan, planner = planned["plan"], planned["planner"]

    # 校验·第二道：视图合法性
    validation = validate(question, plan)
    if not validation["passed"]:
        messages = "；".join(v["message"] for v in validation["violations"])
        return {**base, "stage": "blocked", "reply": f"该查询已被校验 Agent 拦截：{messages}",
                "plan": plan, "planner": planner, "validation": validation,
                "view": plan.get("view_id"), "data": None, "sql": None, "provenance": None}

    # 无对应视图：如实相告 + 列出可回答范围
    if not plan.get("view_id"):
        return {**base, "stage": "no_view", "reply": _no_view_reply(),
                "plan": plan, "planner": planner, "validation": validation,
                "view": None, "data": None, "sql": None, "provenance": None}

    # 执行（第三道机判在 compile_view 内，PolicyViolationError 由路由层转 422）
    result = execute_plan(plan)

    # 带依据回答
    reply = answer_question(question, plan, result)
    return {**base, "stage": "answered", "reply": reply,
            "plan": plan, "planner": planner, "validation": validation,
            "view": plan["view_id"],
            "data": {"columns": result["columns"], "rows": result["rows"],
                     "row_count": result["row_count"]},
            "sql": result["sql"], "provenance": result["provenance"]}
