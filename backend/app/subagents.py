"""可插拔 SubAgent（Mock LLM）。

设计要点：
- SubAgent 是"认知型"节点，负责生成建议（病历草稿 / 检验汇总），不直接写正式病历；
- 真实场景替换为 LangChain + LLM 即可，此处 Mock 固定样例，无密钥依赖；
- 节点内根据 enable_*_subagent 开关决定是否调用（方案A：同节点 if 分支）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def emr_draft_subagent(patient_name: str, chief_complaint: str = "", kb_entries: list = None) -> str:
    """病历草稿 SubAgent（Mock）：引用知识库条目生成结构化 SOAP 草稿。

    真实实现：根据主诉/检查结果 + 知识库检索（RAG）调用 LLM 生成草稿。
    Demo 用规则拼接：从知识库提取指南/SOAP 模板/药品字典，组装更可信的草稿。
    AI 输出独立隔离，由医生 HITL 确认后才可采纳，绝不自动写入正式病历。
    """
    complaint = chief_complaint or "反复上腹痛 3 天，加重伴恶心 1 天"
    kb = kb_entries or []

    def _find(cat: str, keyword: str = "") -> str:
        for e in kb:
            if e.get("category") != cat:
                continue
            if not keyword or keyword in (e.get("title", "") + e.get("content", "")):
                return e.get("content", "")
        return ""

    soap_tpl = _find("soap_template")
    guide = _find("guide", "胃炎") or _find("guide")
    drug = _find("drug_dict", "抑酸") or _find("drug_dict")

    # 引用条目标题列表（留痕 SubAgent 用了哪些知识库条目）
    cited = "；".join(f"[{e.get('category')}] {e.get('title')}" for e in kb[:5]) or "无"

    head = (
        f"【AI 病历草稿（Mock·引用知识库）】 生成时间：{_now()}\n"
        f"患者：{patient_name}\n"
        f"引用知识库条目：{cited}\n"
        "—— 以下为 SubAgent 生成的建议草稿，仅供医生参考，不会自动写入正式病历 ——\n\n"
    )

    s = (
        "S（主观）：\n"
        f"- 主诉：{complaint}。\n"
        "- 现病史：患者 3 天前无明显诱因出现上腹部隐痛，餐后加重，伴恶心、未呕吐；"
        "1 天前腹痛加重，向背部放射，无发热寒战。\n"
    )
    o = (
        "\nO（客观）：\n"
        "- 查体：腹平软，上腹剑突下压痛（+），无反跳痛，Murphy 征（-）。\n"
        "- 既往：否认高血压、糖尿病史。\n"
    )
    assess = "\nA（评估）：\n- 初步考虑：急性胃炎 / 胆囊炎待排。\n"
    if guide:
        assess += f"- 指南参考：{guide.splitlines()[0] if guide else ''}\n"
    assess += "- 风险提示：需结合血常规、腹部 B 超进一步鉴别。\n"

    plan = "\nP（计划）：\n1. 完善血常规、腹部 B 超；\n2. 予抑酸、解痉对症治疗；\n"
    if drug:
        plan += f"   药品参考：{drug.splitlines()[0] if drug else ''}\n"
    plan += "3. 嘱清淡饮食，随诊。\n"

    if soap_tpl:
        plan += f"\n（结构遵循：{soap_tpl.splitlines()[0] if soap_tpl else 'SOAP 模板'}）\n"

    plan += "\n（请主治医生审阅后决定是否采纳到正式病历。）"
    return head + s + o + assess + plan


def lab_summary_subagent(check_tasks: list) -> str:
    """检验汇总 SubAgent（Mock）：汇总已完成检查结果。

    真实实现：读取 LIS 结果调用 LLM 生成解读。Demo 仅做规则汇总 + 固定话术。
    """
    done = [t for t in check_tasks if t.get("status") == "done"]
    if not done:
        return "【检验汇总（Mock）】暂无已完成检查结果，无法生成汇总。"

    lines = [f"【检验汇总（Mock）】 生成时间：{_now()}", "已完成检查汇总："]
    for t in done:
        result = t.get("result") or {}
        lines.append(
            f"- {t.get('task_label')}（{t.get('task_type')}）：{result.get('summary', '结果已回填')}"
        )
    lines.append("")
    lines.append("辅助解读：各项指标基本平稳，建议结合临床综合判断。（Mock 话术）")
    return "\n".join(lines)


def emr_chat_subagent(patient_id: str, message: str, history: list = None,
                      patient_context: str = "", kb_context: str = "") -> dict:
    """病历辅助对话 SubAgent：多轮对话辅助医生起草/优化 SOAP 病历。

    接入策略（per-agent 模型配置优先于全局 settings）：
    · 读取 store.get_agent_model_config("emr_agent") 作为模型配置
    · 读取 store.get_agent_prompt("emr_agent") 作为自定义 Prompt
    · 读取 store.get_agent_output_schema("emr_agent") 作为自定义输出 Schema
    · provider=mock 或 enable_real=0 → 走本地规则
    · provider=openai_compatible + enable_real=1 + api_key → 真 LLM 多轮对话
    · 真 LLM 调用失败自动降级 Mock，保证服务不中断
    · 输出仅为草稿建议，需医生 HITL 确认后才可采纳到正式病历
    """
    try:
        from app.llm_client import run_emr_chat_llm
        from app.storage import store
        try:
            mc = store.get_agent_model_config("emr_agent")
            ap = store.get_agent_prompt("emr_agent")
            aos = store.get_agent_output_schema("emr_agent")
        except Exception:
            mc = None
            ap = ""
            aos = ""
        result = run_emr_chat_llm(
            message=message,
            history=history,
            patient_context=patient_context,
            kb_context=kb_context,
            model_config=mc,
            agent_prompt=ap,
            agent_output_schema=aos,
        )
        result.setdefault("trace_id", f"emr_{patient_id}_{result.get('trace_id','')[-8:]}")
        return result
    except Exception as _e:
        import sys
        print(f"[emr chat] run_emr_chat_llm 异常，降级 Mock: {_e}", file=sys.stderr)
        from app.llm_client import _mock_emr_chat, _mock_emr_structured_output
        reply = _mock_emr_chat(message, history or [], patient_context)
        structured = _mock_emr_structured_output(message, patient_context)
        return {
            "reply": reply,
            "structured_output": structured,
            "provider_used": "mock",
            "fallback_reason": f"异常降级: {_e}",
            "trace_id": f"emr_{patient_id}_fallback",
        }


def patient_triage_subagent(patient_id: str, message: str, session_history: list = None, kb_context: str = "") -> dict:
    """AI 导诊 SubAgent：采集症状，推荐 2-3 个科室及置信度。

    接入策略（per-agent 模型配置优先于全局 settings）：
    · 读取 store.get_agent_model_config("patient_triage_agent") 作为模型配置
    · provider=mock 或 enable_real=0 → 走本地关键词规则（Mock，零密钥依赖）
    · provider=openai_compatible + enable_real=1 + api_key → 真 LLM
    · 真 LLM 调用失败自动降级 Mock，保证服务不中断
    · 必带强风控免责声明：输出固定提示「仅导诊参考，最终科室以护士/医生确认为准」

    kb_context 用于注入 RAG 召回的科室就诊须知/检查注意事项，增强导诊推荐的合理性。
    """
    try:
        from app.llm_client import run_triage_llm
        from app.storage import store
        # 读取 per-agent 模型配置 + 自定义 Prompt（后台 Agent 配置页可在线修改，热更新生效）
        try:
            mc = store.get_agent_model_config("patient_triage_agent")
            ap = store.get_agent_prompt("patient_triage_agent")
        except Exception:
            mc = None
            ap = ""
        result = run_triage_llm(
            symptom_text=message,
            kb_context=kb_context,
            session_history=session_history,
            model_config=mc,
            agent_prompt=ap,
        )
        # subagents 原始返回结构兼容：补 trace_id 一致性
        result.setdefault("trace_id", f"triage_{patient_id}_{result.get('trace_id','')[-8:]}")
        return result
    except Exception as _e:
        import sys
        print(f"[triage] run_triage_llm 异常，降级 Mock: {_e}", file=sys.stderr)
        # 异常兜底：纯 Mock 规则
        return _mock_triage_fallback(patient_id, message)


def _mock_triage_fallback(patient_id: str, message: str) -> dict:
    """Mock 本地规则兜底（原 patient_triage_subagent 逻辑）。"""
    import uuid
    msg = message.lower()
    dept_rules = {
        "消化内科": ["腹痛", "胃痛", "恶心", "呕吐", "腹泻", "便秘", "反酸", "腹胀", "上腹痛"],
        "心内科": ["胸痛", "胸闷", "心悸", "心慌", "气短", "呼吸困难", "血压"],
        "呼吸科": ["咳嗽", "咳痰", "发烧", "发热", "咽痛", "鼻塞"],
        "骨科": ["腰痛", "腿痛", "关节痛", "扭伤", "骨折", "颈椎"],
        "皮肤科": ["皮疹", "瘙痒", "湿疹", "痤疮", "皮炎"],
        "眼科": ["视力", "眼睛", "近视", "散光", "白内障"],
        "耳鼻喉科": ["耳鸣", "眩晕", "鼻炎", "中耳炎"],
        "内分泌科": ["血糖", "糖尿病", "甲状腺", "肥胖"],
    }
    scored = []
    for dept, keywords in dept_rules.items():
        hit = sum(1 for kw in keywords if kw in msg)
        if hit > 0:
            confidence = min(0.95, 0.5 + hit * 0.15)
            scored.append({
                "dept_name": dept,
                "confidence": round(confidence, 2),
                "reason": f"症状匹配：{', '.join(kw for kw in keywords if kw in msg)}",
            })
    if not scored:
        scored = [
            {"dept_name": "全科医学科", "confidence": 0.6, "reason": "症状不典型，建议全科首诊"},
            {"dept_name": "内科", "confidence": 0.4, "reason": "常见内科症状"},
        ]
    scored.sort(key=lambda x: x["confidence"], reverse=True)
    recommended = scored[:3]
    reply = (
        f"您好，我是 AI 导诊助手。根据您描述的症状，"
        f"我为您推荐了 {len(recommended)} 个科室："
        f"{'、'.join(d['dept_name'] for d in recommended)}。"
        f"置信度最高的是 {recommended[0]['dept_name']}（{recommended[0]['confidence']*100:.0f}%）。"
        f"建议您预约 {recommended[0]['dept_name']} 的门诊进一步就诊。\n\n"
        "【免责声明】AI建议仅为就诊分诊参考，不构成诊断与医嘱，最终就诊方案请遵医护人员判断。"
    )
    return {
        "reply": reply,
        "recommended_departments": recommended,
        "collected_symptoms": msg,
        "trace_id": f"triage_{patient_id}_{uuid.uuid4().hex[:8]}",
        "provider_used": "mock_fallback",
        "fallback_reason": None,
    }
