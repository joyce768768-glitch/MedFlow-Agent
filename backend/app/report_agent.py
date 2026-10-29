"""M4 Data Agent · 报表编排（医疗统计）：NL 问题 → 多节复合报表。

在 M3 单问编排（semantic_orchestrator.ask_question）之上叠报表层：

    NL 问题 → 报表规划 Agent（真 LLM 拆解 2-4 节，注入纯语义注册表）
            → 逐节复用 ask_question 全链路（三道校验逐节不旁路）
            → 声明式异常规则机判（M4 设计决策：异常判定在应用层，
              语义视图只管口径；规则可配置、报表可解释）
            → 汇总 Agent（真 LLM：summary + insights，数字只从各节引用）

供型：强制真 LLM（同 M3 策略）；报表规划解析失败重试 1 次，仍失败退化为
「原问题单节直查」（每节仍走完整校验链路），不做 Mock 降级。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from semantic_contract import (
    ReportPlanParseError,
    apply_anomaly_rules,
    parse_report_plan,
    parse_report_summary,
    report_planner_prompt,
    report_summary_prompt,
    section_digest,
    validate_report_plan,
)

from .semantic_orchestrator import (
    BOUNDARY_REPLY,
    PROVIDER_USED,
    QUESTION_FORBIDDEN_KEYWORDS,
    _REGISTRY,
    _llm,
    ask_question,
)

MAX_SECTIONS = 4

# —— 声明式异常规则（M4 设计决策：业务判定在应用层，阈值可配置、basis 可解释）——
# 语义视图只回答「科室×平均TAT」是多少；「是否异常」由这里的规则机判标注。
ANOMALY_RULES: Dict[str, List[dict]] = {
    "medflow.view.tat_by_department": [
        {
            "rule_id": "medflow.anomaly.tat",
            "label": "科室周转异常",
            "describe": "科室平均检验周转时间超过目标时限",
            "basis": "检验报告完成目标时限 30 分钟（演示口径，业务可配置）",
            "unit": "小时",
            "column": "avg_tat_hours",
            "op": ">",
            "threshold": 0.5,
        },
    ],
    "medflow.view.critical_report_latency": [
        {
            "rule_id": "medflow.anomaly.critical_latency",
            "label": "危急报告延迟",
            "describe": "危急报告平均响应时长超过目标时限",
            "basis": "危急值报告即时性要求（演示口径，业务可配置）",
            "unit": "小时",
            "column": "avg_latency_hours",
            "op": ">",
            "threshold": 0.5,
        },
    ],
}


def _rules_for(view_id: str | None) -> List[dict]:
    return ANOMALY_RULES.get(view_id or "", [])


def plan_report(question: str) -> Dict[str, Any]:
    """报表规划：真 LLM 拆节，解析失败重试 1 次，仍失败退化为单节直查。"""
    messages = [
        {"role": "system", "content": report_planner_prompt(_REGISTRY, max_sections=MAX_SECTIONS)},
        {"role": "user", "content": question},
    ]
    planner = "llm"
    for attempt in (1, 2):
        raw = _llm(messages)
        try:
            plan = parse_report_plan(raw)
            if not validate_report_plan(plan, max_sections=MAX_SECTIONS):
                if not plan["title"]:
                    plan["title"] = f"「{question}」数据报表"
                return {"plan": plan, "planner": planner}
        except ReportPlanParseError:
            pass
        if attempt == 1:
            planner = "llm_retry"

    # 两次均失败 → 退化为单节直查（原问题走完整 M3 链路，鲁棒性手段非 Mock）
    plan = {"title": f"「{question}」数据报表", "sections": [{"question": question, "rationale": "报表规划退化：原问题直查"}]}
    return {"plan": plan, "planner": "fallback_single_section"}


def run_sections(plan: dict) -> List[Dict[str, Any]]:
    """逐节执行：每节走 M3 ask_question 全链路 + 声明式异常规则机判。"""
    out: List[Dict[str, Any]] = []
    for section in plan["sections"]:
        sub_q = section["question"]
        res = ask_question(sub_q)
        view_name = next((v["name_zh"] for v in _REGISTRY if v["id"] == res.get("view")), None)
        anomalies = apply_anomaly_rules(_rules_for(res.get("view")), **_data_args(res))
        out.append({
            "question": sub_q,
            "rationale": section.get("rationale", ""),
            "stage": res.get("stage"),
            "reply": res.get("reply"),
            "view": res.get("view"),
            "view_name": view_name,
            "planner": res.get("planner"),
            "validation": res.get("validation"),
            "data": res.get("data"),
            "sql": res.get("sql"),
            "provenance": res.get("provenance"),
            "anomalies": anomalies,
        })
    return out


def _data_args(res: dict) -> dict:
    data = res.get("data") or {}
    return {"columns": data.get("columns", []), "rows": data.get("rows", [])}


def summarize(question: str, plan: dict, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总 Agent：各节摘要（含机器异常标注）→ 真 LLM 产出 summary + insights。

    解析失败重试 1 次；仍失败降级为机械拼装（拼各节叙述，数字全部来自真实
    节数据，不编造）——汇总层失败不丢弃整份已查得的报表，打 summary_degraded 标记。
    """
    digests = [section_digest(s["question"], _as_ask_shape(s), s["anomalies"]) for s in sections]
    for attempt in (1, 2):
        try:
            return parse_report_summary(_llm(report_summary_prompt(question, plan["title"], digests)))
        except ReportPlanParseError:
            if attempt == 1:
                continue
    joined = " ".join(
        f"{s['question']}：{s['reply']}" for s in sections if s.get("reply")
    )
    return {"summary": joined or "各节均未取得数据。", "insights": [], "summary_degraded": True}


def _as_ask_shape(section: dict) -> dict:
    """把 run_sections 的节结构还原成 section_digest 期望的 ask 形状。"""
    return {"stage": section.get("stage"), "view": section.get("view"),
            "reply": section.get("reply"), "data": section.get("data")}


def ask_report(question: str) -> Dict[str, Any]:
    """报表编排主链路。返回结构：

    {question, title, generated_at, planner, provider_used,
     sections[], summary, insights, insights_machine, stats}
    """
    # 意图边界（生成之前拦截：报表规划调用都不发起，复用 M3 关键词机判）
    hits = [kw for kw in QUESTION_FORBIDDEN_KEYWORDS if kw in question]
    if hits:
        return {
            "question": question, "title": None, "generated_at": datetime.now().isoformat(timespec="seconds"),
            "planner": None, "provider_used": PROVIDER_USED,
            "sections": [], "summary": BOUNDARY_REPLY, "insights": [], "insights_machine": [],
            "stats": {"sections_total": 0, "sections_answered": 0, "sections_blocked": 0},
            "stage": "blocked",
        }

    planned = plan_report(question)
    plan, planner = planned["plan"], planned["planner"]

    sections = run_sections(plan)

    summary_out = summarize(question, plan, sections)

    machine_insights = [
        f"{s['view_name'] or s['question']}：{a['label']}——{a['describe']}（命中 {a['matched_count']} 行；判定依据：{a['basis']}）"
        for s in sections for a in s["anomalies"]
    ]
    answered = sum(1 for s in sections if s["stage"] == "answered")
    blocked = sum(1 for s in sections if s["stage"] in ("blocked", "no_view"))

    return {
        "question": question,
        "title": plan["title"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "planner": planner,
        "provider_used": PROVIDER_USED,
        "sections": sections,
        "summary": summary_out["summary"],
        "insights": summary_out["insights"],
        "insights_machine": machine_insights,
        "summary_degraded": bool(summary_out.get("summary_degraded")),
        "stats": {"sections_total": len(sections), "sections_answered": answered, "sections_blocked": blocked},
        "stage": "answered",
    }
