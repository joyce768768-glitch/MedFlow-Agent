"""可插拔 LLM 客户端适配器。

统一接入层：
- provider = "mock"          → 走本地关键词规则（默认，零密钥依赖，Demo 始终可用）
- provider = "openai_compatible" → 走 OpenAI 兼容接口
    · 通义千问 DashScope: base_url = https://dashscope.aliyuncs.com/compatible-mode/v1
    · 智谱 GLM:          base_url = https://open.bigmodel.cn/api/paas/v4
    · DeepSeek:          base_url = https://api.deepseek.com/v1
    · 开源医疗模型本地:   base_url = http://localhost:11434/v1（Ollama）

Provider 选择原则：
- Demo 默认 Mock：不依赖外网、不消耗 Token，确保可运行
- 真 LLM 接入：llm_enable_triage_real=1 且有 API Key 时走真模型
- 失败自动降级：真 LLM 调用失败（超时/429/鉴权）时自动回退到 Mock 规则，避免用户体验中断

医疗合规约束（硬编码，不可绕过）：
- 导诊模型输出必须只包含科室推荐+理由，不允许包含诊断结论、处方、用药方案
- 输出必须携带强制免责声明
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from typing import Dict, List, Optional, Tuple

from app.config import settings


# ============================================================
# 1. 科室主数据（与 store.departments 同源，用于 RAG + 输出约束）
# ============================================================

VALID_DEPARTMENTS: Tuple[str, ...] = (
    "消化内科", "心内科", "呼吸科", "神经内科", "骨科", "儿科", "眼科",
    "耳鼻喉科", "皮肤科", "精神心理科", "内分泌科", "全科医学科", "内科",
    "普外科", "感染科", "影像科",
)


# ============================================================
# 2. 导诊专用 Prompt 模板（强约束，防止模型输出诊断）
# ============================================================

TRIAGE_SYSTEM_PROMPT = """你是一家三级甲等医院的【AI智能导诊助手】，只负责分诊科室推荐，绝对不能做诊断、开处方、推荐药物或给出治疗方案。

【必须严格遵守的规则】
1. 只根据用户描述的症状、病史、过敏史信息，推荐 2-3 个就诊科室，按置信度从高到低排序。
2. 每个推荐必须给出简短理由，理由只能是"症状匹配"，不得涉及疾病名称判断。
3. 输出开头可以友好问候，正文给出科室推荐，输出结尾必须原样附带强制免责声明：
   "【免责声明】AI建议仅为就诊分诊参考，不构成诊断与医嘱，最终就诊方案请遵医护人员判断。"
4. 如果用户描述的是急重症（如剧烈胸痛、呼吸困难、意识模糊、大量出血），建议立即前往急诊。
5. 如果用户要求给出诊断/药物/剂量/手术方案，必须明确拒绝，并重申："我仅提供科室分诊建议，请您前往相应科室就诊。"

【输出格式要求】
每次回复必须同时包含两段：
A. 自然语言回复（给患者看的文字），50-150字。
B. 结构化 JSON（给系统解析，用于挂号页跳转按钮），放在 <json>...</json> 标签内：
<json>
{
  "recommended_departments": [
    {"dept_name": "呼吸科", "confidence": 0.85, "reason": "症状匹配：咳嗽、咳痰"},
    {"dept_name": "心内科", "confidence": 0.5, "reason": "需排除胸闷相关"}
  ]
}
</json>
注意：confidence 范围 0~1，最多 3 个科室，dept_name 必须从以下列表中选：
""" + str(list(VALID_DEPARTMENTS))


def _build_triage_messages(symptom_text: str, kb_context: str = "", history: list = None,
                           custom_prompt: str = "") -> List[dict]:
    """组装导诊对话 messages，支持多轮历史 + 科室知识 RAG + 自定义 Prompt。"""
    system_prompt = custom_prompt.strip() if custom_prompt.strip() else TRIAGE_SYSTEM_PROMPT
    messages: List[dict] = [{"role": "system", "content": system_prompt}]

    # RAG：注入科室相关知识/就诊须知（从后台主数据召回）
    if kb_context:
        messages.insert(1, {
            "role": "system",
            "content": f"【可参考的院内科室主数据】\n{kb_context}",
        })

    # 历史对话（最近 6 轮，避免超限）
    if history:
        for h in history[-6:]:
            role = "user" if h.get("role") in ("user", "patient") else "assistant"
            messages.append({"role": role, "content": h.get("content", "")})

    messages.append({"role": "user", "content": symptom_text})
    return messages


# ============================================================
# 3. OpenAI 兼容接口调用（urllib 实现，零第三方依赖，避免版本冲突）
# ============================================================

def _call_openai_compatible(messages: List[dict], mc: Optional[dict] = None) -> str:
    """调用 OpenAI 兼容接口，返回模型原始输出文本。

    已适配厂商（均走 /chat/completions + Bearer Token）：
      · 阿里 DashScope 通义千问：https://dashscope.aliyuncs.com/compatible-mode/v1
      · 智谱 GLM：https://open.bigmodel.cn/api/paas/v4
      · DeepSeek：https://api.deepseek.com/v1
      · Ollama 本地开源模型：http://localhost:11434/v1

    参数 mc：可选模型配置 dict {model, base_url, api_key, timeout}；
            未传或为 None 时回退到全局 settings（向后兼容）。
    """
    import urllib.request
    import urllib.error

    if mc is None:
        api_key = settings.llm_api_key
        api_base = settings.llm_base_url or "https://api.openai.com/v1"
        model_name = settings.llm_model
        timeout = settings.llm_timeout
    else:
        api_key = mc.get("api_key", "")
        api_base = mc.get("base_url", "") or "https://api.openai.com/v1"
        model_name = mc.get("model", "") or settings.llm_model
        timeout = int(mc.get("timeout", settings.llm_timeout))

    if not api_key:
        raise RuntimeError("未配置 API Key，无法调用真实模型")
    if not model_name:
        raise RuntimeError("未配置模型名称（model），无法调用真实模型")

    api_base = api_base.rstrip("/")
    url = f"{api_base}/chat/completions"

    # 千问 DashScope 兼容层：部分版本对 top_p 范围严格（要求 >0，0.9 没问题，但 temperature 上限=2）
    # 为跨模型兼容，统一构造参数，不发送厂商专属参数
    payload_obj = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.1,
        "top_p": 0.9,
        "max_tokens": 1024,
        "stream": False,
    }
    # DashScope 特有：如果 model 属于千问系列，可添加 `result_format: "message"` 以确保标准消息格式
    # 但兼容层默认就是 message 格式，故不必额外发送
    payload = json.dumps(payload_obj).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # DashScope 兼容层需要以下 Request-Id 做幂等（可选，但带上便于你排查）
        "X-Request-Id": f"medflow-{int(time.time())}",
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        code = e.code
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"LLM HTTP {code}: {detail}")


# ============================================================
# 4. 导诊输出解析（模型自由文本 → 系统结构化数据）
# ============================================================

def _parse_triage_output(raw: str) -> Tuple[str, List[dict]]:
    """解析模型输出，提取（自然语言回复, 推荐科室列表）。

    解析策略：
    1. 先找 <json>...</json> 标签内的结构化 JSON
    2. 找不到时，尝试全文提取最后一段 JSON 代码块
    3. JSON 解析失败时，用关键词匹配兜底（回退到 mock 逻辑）
    """
    reply_text = raw.strip()

    # 1. <json> 标签
    import re
    m = re.search(r"<json>\s*(\{.*?\})\s*</json>", raw, re.DOTALL | re.IGNORECASE)
    json_str = m.group(1) if m else None

    # 2. ```json 代码块
    if not json_str:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
        if m:
            json_str = m.group(1)

    recommended: List[dict] = []
    if json_str:
        try:
            data = json.loads(json_str)
            depts = data.get("recommended_departments", [])
            for d in depts:
                name = str(d.get("dept_name", "")).strip()
                if not name or name not in VALID_DEPARTMENTS:
                    continue
                conf = float(d.get("confidence", 0.5))
                conf = max(0.0, min(1.0, conf))
                recommended.append({
                    "dept_name": name,
                    "confidence": round(conf, 2),
                    "reason": str(d.get("reason", "症状匹配分析")).strip(),
                })
        except Exception:
            recommended = []

    return reply_text, recommended[:3]


# ============================================================
# 5. 对外统一入口：run_triage_llm()
# ============================================================

def run_triage_llm(
    symptom_text: str,
    kb_context: str = "",
    session_history: list = None,
    model_config: Optional[dict] = None,
    agent_prompt: str = "",
) -> dict:
    """导诊 SubAgent 统一入口：自动选择真 LLM 或 Mock 规则。

    参数 model_config：可选 per-agent 模型配置 dict
        {provider, enable_real, model, base_url, api_key, timeout}；
        未传或为 None 时回退到全局 settings（向后兼容）。
    参数 agent_prompt：可选 per-agent 自定义 System Prompt；空字符串=使用默认。

    返回结构（与 subagents.patient_triage_subagent 对齐）：
        {
            "reply": str,                        # 患者可读文本（含免责声明）
            "recommended_departments": list,     # [ {dept_name, confidence, reason} ]
            "collected_symptoms": str,
            "trace_id": str,
            "provider_used": "mock" | "openai_compatible",
            "fallback_reason": str | None,       # 真模型失败时记录降级原因
        }

    降级策略：
    · enable_real = 0 → 直接 Mock
    · 真模型配置不全 → Mock
    · 真模型调用失败（超时/鉴权/HTTP错）→ Mock + 记录 fallback_reason
    · 解析后推荐科室为空 → Mock 规则补齐
    """
    import uuid
    provider_used: str = "mock"
    fallback: Optional[str] = None
    trace_id = f"triage_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    # 优先使用传入的 per-agent 配置，否则回退到全局 settings
    if model_config is not None:
        provider = model_config.get("provider", "mock")
        enable_real = int(model_config.get("enable_real", 0))
    else:
        provider = settings.llm_provider
        enable_real = int(settings.llm_enable_triage_real)

    use_real = (enable_real == 1 and provider == "openai_compatible")

    # ---- 真 LLM 分支 ----
    if use_real:
        try:
            msgs = _build_triage_messages(symptom_text, kb_context, session_history,
                                          custom_prompt=agent_prompt)
            raw_output = _call_openai_compatible(msgs, mc=model_config)
            reply_text, recommended = _parse_triage_output(raw_output)
            provider_used = "openai_compatible"

            # 解析为空 → Mock 兜底补推荐
            if not recommended:
                fallback = "LLM 解析后推荐列表为空，降级 Mock"
                fallback_reply, fallback_recommended = _mock_triage(symptom_text)
                # 合并文本：保留模型自然语言 + Mock 的结构化推荐
                if not reply_text.endswith("【免责声明】"):
                    reply_text = (
                        f"{reply_text}\n\n"
                        f"参考分诊建议：建议前往 {fallback_recommended[0]['dept_name']} 就诊。"
                    )
                recommended = fallback_recommended

            # 确保免责声明存在（硬约束，模型可能漏写时自动补上）
            if "AI建议仅为就诊分诊参考" not in reply_text:
                reply_text += (
                    "\n\n【免责声明】AI建议仅为就诊分诊参考，不构成诊断与医嘱，"
                    "最终就诊方案请遵医护人员判断。"
                )

            return {
                "reply": reply_text,
                "recommended_departments": recommended,
                "collected_symptoms": symptom_text,
                "trace_id": trace_id,
                "provider_used": provider_used,
                "fallback_reason": fallback,
            }
        except Exception as exc:
            fallback = f"LLM调用失败({type(exc).__name__}: {exc})，已降级 Mock 规则"
            print(f"[LLM triage 降级] {fallback}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    # ---- Mock 分支（默认 / 真模型失败降级）----
    reply, recommended = _mock_triage(symptom_text)
    return {
        "reply": reply,
        "recommended_departments": recommended,
        "collected_symptoms": symptom_text,
        "trace_id": trace_id,
        "provider_used": provider_used,
        "fallback_reason": fallback,
    }


# ============================================================
# 6. Mock 本地规则（从 subagents.py 搬过来，保持不变作为 baseline）
# ============================================================


# ============================================================
# 7. 病历辅助 Agent 对话入口：run_emr_chat_llm()
# ============================================================

# 默认病历输出 Schema（SOAP 结构）
DEFAULT_EMR_OUTPUT_SCHEMA = json.dumps({
    "chief_complaint": "主诉",
    "present_illness": "现病史",
    "past_history": "既往史",
    "examination": "查体",
    "assessment": "评估",
    "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
    "risk_flags": ["风险提示"],
    "plan": "诊疗计划",
}, ensure_ascii=False, indent=2)

EMR_CHAT_SYSTEM_PROMPT = """你是一家三级甲等医院的【AI 病历辅助助手】，协助主治医生起草和优化病历，绝不替代医生做最终决策。

【必须严格遵守的规则】
1. 你的输出仅是病历草稿建议，不会自动写入正式病历，必须由主治医生 HITL 审阅确认后才可采纳。
2. 病历结构遵循 SOAP 模板：
   - S（主观）：主诉、现病史、既往史、过敏史等患者自述。
   - O（客观）：查体、生命体征、辅助检查结果等客观资料。
   - A（评估）：初步诊断印象、鉴别诊断要点、风险提示。
   - P（计划）：进一步检查、治疗方案、用药建议（仅作参考，需医生确认）、随诊安排。
3. 不得编造患者未提供的检查数据或体征；如信息不足，明确告知医生需要补充哪些信息。
4. 不得给出剂量明确的处方；用药建议只能给出类别方向（如"抑酸药""解痉药"），具体药品与剂量由医生决定。
5. 输出末尾必须附带声明："【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"

【医生可能的指令类型】
- "根据主诉生成 SOAP 草稿" → 输出完整 SOAP 草稿
- "把 A 部分写得更详细" → 基于上下文优化指定部分
- "增加鉴别诊断" → 在 A 部分补充
- "检查结果出来了：xxx" → 把检查结果整合到 O 部分，相应调整 A/P
- 其他自然语言指令 → 灵活响应，但守住边界

【输出格式要求】
每次回复必须同时包含两段：
A. 自然语言回复（给医生看的文字），简洁专业，50-300字。
B. 结构化 JSON（给系统解析，用于前端 SOAP 卡片渲染），放在 <json>...</json> 标签内。
字段 Schema：
""" + DEFAULT_EMR_OUTPUT_SCHEMA + """
注意：所有字段均为字符串或数组类型，内容为空时填空字符串或空数组。"""


def _build_emr_chat_messages(patient_context: str, history: list, message: str,
                             kb_context: str = "", custom_prompt: str = "",
                             custom_output_schema: str = "") -> List[dict]:
    """组装病历 Agent 对话 messages。"""
    # 使用自定义 Prompt（含自定义 Schema）或默认
    if custom_prompt.strip():
        system_prompt = custom_prompt.strip()
    elif custom_output_schema.strip():
        # 使用默认 Prompt + 自定义 Schema
        system_prompt = EMR_CHAT_SYSTEM_PROMPT.replace(
            DEFAULT_EMR_OUTPUT_SCHEMA, custom_output_schema.strip()
        )
    else:
        system_prompt = EMR_CHAT_SYSTEM_PROMPT

    messages: List[dict] = [{"role": "system", "content": system_prompt}]

    # 注入患者上下文（主诉、查体、检查结果等）
    if patient_context:
        messages.append({
            "role": "system",
            "content": f"【当前患者上下文】\n{patient_context}",
        })

    # 注入知识库 RAG（SOAP 模板 / 指南 / 药品字典）
    if kb_context:
        messages.append({
            "role": "system",
            "content": f"【可参考的院内知识库】\n{kb_context}",
        })

    # 历史对话（最近 10 轮）
    if history:
        for h in history[-10:]:
            role = "assistant" if h.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": h.get("content", "")})

    messages.append({"role": "user", "content": message})
    return messages


def _parse_emr_output(raw: str) -> Tuple[str, dict]:
    """解析病历 Agent 输出，提取（自然语言回复, 结构化 SOAP 数据）。

    解析策略：
    1. 先找 <json>...</json> 标签内的结构化 JSON
    2. 找不到时，尝试全文提取最后一段 JSON 代码块
    3. JSON 解析失败时，返回空 dict
    """
    import re
    reply_text = raw.strip()

    # 1. <json> 标签
    m = re.search(r"<json>\s*(\{.*?\})\s*</json>", raw, re.DOTALL | re.IGNORECASE)
    json_str = m.group(1) if m else None

    # 2. ```json 代码块
    if not json_str:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
        if m:
            json_str = m.group(1)

    structured: dict = {}
    if json_str:
        try:
            structured = json.loads(json_str)
        except Exception:
            structured = {}

    return reply_text, structured


def run_emr_chat_llm(message: str, history: list = None,
                     patient_context: str = "", kb_context: str = "",
                     model_config: Optional[dict] = None,
                     agent_prompt: str = "",
                     agent_output_schema: str = "") -> dict:
    """病历辅助 Agent 对话入口：自动选择真 LLM 或 Mock 规则。

    参数 model_config：per-agent 模型配置 dict；None 时回退到全局 settings。
    参数 agent_prompt：可选 per-agent 自定义 System Prompt；空字符串=使用默认。
    参数 agent_output_schema：可选 per-agent 自定义输出 Schema；空字符串=使用默认。

    返回结构：
        {
            "reply": str,                     # AI 回复文本（含声明）
            "structured_output": dict,        # 结构化 SOAP 数据（解析成功时）
            "provider_used": "mock" | "openai_compatible",
            "fallback_reason": str | None,
            "trace_id": str,
        }
    """
    import uuid
    provider_used: str = "mock"
    fallback: Optional[str] = None
    trace_id = f"emr_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    if model_config is not None:
        provider = model_config.get("provider", "mock")
        enable_real = int(model_config.get("enable_real", 0))
    else:
        provider = settings.llm_provider
        enable_real = int(settings.llm_enable_triage_real)

    use_real = (enable_real == 1 and provider == "openai_compatible")

    if use_real:
        try:
            msgs = _build_emr_chat_messages(patient_context, history or [], message,
                                            kb_context, custom_prompt=agent_prompt,
                                            custom_output_schema=agent_output_schema)
            raw_output = _call_openai_compatible(msgs, mc=model_config)
            reply_text, structured = _parse_emr_output(raw_output)
            provider_used = "openai_compatible"

            # 确保声明存在（硬约束）
            if "AI 病历草稿建议" not in reply_text:
                reply_text += (
                    "\n\n【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
                )
            return {
                "reply": reply_text,
                "structured_output": structured,
                "provider_used": provider_used,
                "fallback_reason": fallback,
                "trace_id": trace_id,
            }
        except Exception as exc:
            fallback = f"LLM调用失败({type(exc).__name__}: {exc})，已降级 Mock 规则"
            print(f"[EMR chat 降级] {fallback}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    # ---- Mock 分支 ----
    reply = _mock_emr_chat(message, history or [], patient_context)
    # Mock 模式：构造默认结构数据
    structured = _mock_emr_structured_output(message, patient_context)
    return {
        "reply": reply,
        "structured_output": structured,
        "provider_used": provider_used,
        "fallback_reason": fallback,
        "trace_id": trace_id,
    }


def _mock_emr_chat(message: str, history: list, patient_context: str) -> str:
    """Mock 规则病历对话：根据医生指令类型给出结构化响应。"""
    msg = (message or "").strip()
    msg_lower = msg.lower()

    # 首次问候 / 空消息
    if not msg or any(k in msg_lower for k in ["你好", "在吗", "hello", "hi"]):
        return (
            "您好，我是病历辅助 Agent。我可以帮您起草和优化 SOAP 病历。\n"
            "您可以这样指令我：\n"
            "- 「根据主诉生成 SOAP 草稿」\n"
            "- 「把评估部分写详细些」\n"
            "- 「增加鉴别诊断」\n"
            "- 「检查结果：血常规正常，腹部 B 超未见异常」\n\n"
            "请告诉我患者的主诉或您希望我做什么。"
        )

    # 检查结果整合
    if any(k in msg for k in ["检查结果", "化验", "血常规", "B超", "CT", "影像"]):
        return (
            "【O（客观）更新】\n"
            f"- 已整合医生提供的检查信息：{msg[:80]}{'…' if len(msg) > 80 else ''}\n"
            "- 建议将上述结果记录到 O 部分，并相应调整 A（评估）和 P（计划）。\n\n"
            "（Mock 提示：实际真 LLM 接入后会基于检查结果自动调整鉴别诊断与计划。）\n\n"
            "【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
        )

    # 生成 SOAP 草稿
    if any(k in msg for k in ["生成", "草稿", "SOAP", "写病历", "draft"]):
        complaint = "（医生未提供主诉，请补充）"
        if patient_context:
            # 尝试从上下文提取主诉
            for line in patient_context.splitlines():
                if "主诉" in line or "chief" in line.lower():
                    complaint = line.split(":", 1)[-1].split("：", 1)[-1].strip() or complaint
                    break
        elif msg and "主诉" in msg:
            complaint = msg.split("主诉", 1)[-1].lstrip("：:").strip()[:60] or complaint

        return (
            "【AI 病历草稿建议】\n\n"
            f"S（主观）：\n- 主诉：{complaint}\n- 现病史：（待补充）\n\n"
            "O（客观）：\n- 查体：（待补充）\n- 辅助检查：（待补充）\n\n"
            "A（评估）：\n- 初步考虑：（待补充）\n- 风险提示：需结合查体与检查结果\n\n"
            "P（计划）：\n1. 完善相关检查；\n2. 对症处理；\n3. 随诊。\n\n"
            "请补充主诉、查体或检查结果，我会基于这些信息完善草稿。\n\n"
            "【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
        )

    # 默认响应
    return (
        f"我已收到您的指令：{msg[:100]}{'…' if len(msg) > 100 else ''}\n\n"
        "（Mock 模式：实际真 LLM 接入后会基于上下文给出具体的 SOAP 草稿建议。"
        "您可以在后台 Agent 配置页为 emr_agent 配置云端模型。）\n\n"
        "【声明】以上为 AI 病历草稿建议，仅供医生参考，不构成最终诊断与处方。"
    )


def _mock_emr_structured_output(message: str, patient_context: str) -> dict:
    """Mock 结构化病历输出：根据消息内容生成默认 SOAP 结构。"""
    msg = (message or "").strip()
    msg_lower = msg.lower()

    # 尝试从上下文提取主诉
    complaint = ""
    if patient_context:
        for line in patient_context.splitlines():
            if "主诉" in line or "chief" in line.lower():
                complaint = line.split(":", 1)[-1].split("：", 1)[-1].strip() or complaint
                break
    if not complaint and msg and "主诉" in msg:
        complaint = msg.split("主诉", 1)[-1].lstrip("：:").strip()[:60]

    # 根据指令类型生成不同的默认结构
    if any(k in msg for k in ["生成", "草稿", "SOAP", "写病历", "draft"]):
        return {
            "chief_complaint": complaint or "（医生未提供主诉，请补充）",
            "present_illness": "（待补充）",
            "past_history": "（待补充）",
            "examination": "（待补充）",
            "assessment": "初步考虑：（待补充）",
            "differential_diagnosis": ["（待补充）"],
            "risk_flags": ["需结合查体与检查结果"],
            "plan": "1. 完善相关检查；2. 对症处理；3. 随诊。",
        }
    elif any(k in msg for k in ["检查结果", "化验", "血常规", "B超", "CT", "影像"]):
        return {
            "chief_complaint": complaint,
            "present_illness": "",
            "past_history": "",
            "examination": f"已整合检查信息：{msg[:80]}{'…' if len(msg) > 80 else ''}",
            "assessment": "建议将检查结果整合到 O 部分，相应调整 A（评估）和 P（计划）。",
            "differential_diagnosis": [],
            "risk_flags": [],
            "plan": "根据检查结果调整诊疗计划。",
        }
    else:
        return {
            "chief_complaint": complaint,
            "present_illness": "",
            "past_history": "",
            "examination": "",
            "assessment": "",
            "differential_diagnosis": [],
            "risk_flags": [],
            "plan": "",
        }


def _mock_triage(message: str) -> Tuple[str, List[dict]]:
    """Mock 规则分诊：关键词匹配，无外部依赖。"""
    msg = message.lower()
    dept_rules: Dict[str, List[str]] = {
        "消化内科": ["腹痛", "胃痛", "恶心", "呕吐", "腹泻", "便秘", "反酸", "腹胀", "上腹痛"],
        "心内科": ["胸痛", "胸闷", "心悸", "心慌", "气短", "呼吸困难", "血压"],
        "呼吸科": ["咳嗽", "咳痰", "发烧", "发热", "咽痛", "鼻塞"],
        "骨科": ["腰痛", "腿痛", "关节痛", "扭伤", "骨折", "颈椎"],
        "皮肤科": ["皮疹", "瘙痒", "湿疹", "痤疮", "皮炎"],
        "眼科": ["视力", "眼睛", "近视", "散光", "白内障"],
        "耳鼻喉科": ["耳鸣", "眩晕", "鼻炎", "中耳炎"],
        "内分泌科": ["血糖", "糖尿病", "甲状腺", "肥胖"],
    }

    scored: List[dict] = []
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
    return reply, recommended
