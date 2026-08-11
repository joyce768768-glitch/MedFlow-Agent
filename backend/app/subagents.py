"""可插拔 SubAgent（Mock LLM）。

设计要点：
- SubAgent 是"认知型"节点，负责生成建议（病历草稿 / 检验汇总），不直接写正式病历；
- 真实场景替换为 LangChain + LLM 即可，此处 Mock 固定样例，无密钥依赖；
- 节点内根据 enable_*_subagent 开关决定是否调用（方案A：同节点 if 分支）。
"""
from __future__ import annotations

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
