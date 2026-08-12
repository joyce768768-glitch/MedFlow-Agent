"""通义千问 DashScope 接入验证脚本。

使用方法：
  1. 确保 backend/.env 中已填入：
        LLM_PROVIDER=openai_compatible
        LLM_ENABLE_TRIAGE_REAL=1
        LLM_API_KEY=sk-xxxxxx        # ← 你的 DashScope Key
        LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
        LLM_MODEL=qwen-plus
  2. 运行：
        cd backend
        python3 scripts/verify_qwen_dashscope.py

验证项：
  [1] 环境变量加载
  [2] /chat/completions 直连接口（通义千问 hello world）
  [3] run_triage_llm 全链路（含 Prompt + JSON 解析）
  [4] 导诊埋点字段：provider_used / fallback_reason / trace_id
  [5] 无 Key/错误 Key → 自动降级 Mock，服务不中断
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# 把 backend 目录加到 sys.path 以便导入 app.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 先强制加载 .env（在 app.config 被 import 之前）
from dotenv import load_dotenv  # noqa: E402
env_file = ROOT / ".env"
if env_file.exists():
    loaded = load_dotenv(env_file, override=True)
    print(f"[INFO] 加载 .env 成功: {loaded}  ({env_file})")
else:
    print(f"[WARN] 未找到 .env: {env_file}，请按文档说明 cp .env.example .env 并填 Key")

from app.config import settings  # noqa: E402
from app.llm_client import (  # noqa: E402
    VALID_DEPARTMENTS,
    _call_openai_compatible,
    _parse_triage_output,
    run_triage_llm,
)


RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


def _ok(msg: str):
    print(f"{GREEN}[OK]{RESET} {msg}")


def _fail(msg: str):
    print(f"{RED}[FAIL]{RESET} {msg}")


def _warn(msg: str):
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def _info(msg: str):
    print(f"{CYAN}[INFO]{RESET} {msg}")


def step1_env_check():
    print("\n" + "=" * 70)
    print("Step 1: 检查 .env 配置")
    print("=" * 70)
    print(f"  LLM_PROVIDER            = {settings.llm_provider}")
    print(f"  LLM_ENABLE_TRIAGE_REAL  = {settings.llm_enable_triage_real}")
    print(f"  LLM_MODEL               = {settings.llm_model}")
    print(f"  LLM_BASE_URL            = {settings.llm_base_url}")
    key = settings.llm_api_key or ""
    if key:
        print(f"  LLM_API_KEY             = {key[:6]}...{key[-4:]}  (长度 {len(key)})")
    else:
        print(f"  LLM_API_KEY             = (空，Step 2/3 将失败，但 Step 5 降级测试会通过)")

    qwen_endpoint = "dashscope.aliyuncs.com" in (settings.llm_base_url or "")
    provider_openai = settings.llm_provider == "openai_compatible"
    if qwen_endpoint and provider_openai:
        _ok("Provider=openai_compatible + BaseURL 指向 DashScope 通义千问（阿里，非百度） ✔")
    elif not qwen_endpoint:
        _warn("BaseURL 未指向 DashScope；真模型走的不是千问？（如果只是测试可忽略）")
    else:
        _warn(f"LLM_PROVIDER={settings.llm_provider}，需要 = openai_compatible 才会调用真模型")


def step2_raw_api():
    """不经过 Prompt/封装，直接打通义千问的 /chat/completions。"""
    print("\n" + "=" * 70)
    print("Step 2: DashScope 直连接口 —— Hello World（最小消息）")
    print("=" * 70)
    if not settings.llm_api_key:
        _fail("缺少 LLM_API_KEY，跳过直连测试")
        return False
    try:
        t0 = time.time()
        out = _call_openai_compatible([
            {"role": "user", "content": "你好，请用 20 字以内自我介绍。"},
        ])
        dt = (time.time() - t0) * 1000
        _ok(f"通义千问 {settings.llm_model} 直连成功（耗时 {dt:.0f}ms）")
        _info(f"  模型回复: {out[:120]}{'…' if len(out) > 120 else ''}")
        return True
    except Exception as e:
        _fail(f"通义千问直连失败: {type(e).__name__}: {e}")
        _info("排查建议：")
        print("   · 检查 Key 前缀 sk- 是否完整")
        print("   · 确认 DashScope 控制台已开通 qwen-plus（https://dashscope.console.aliyun.com/）")
        print("   · 检查账号是否有余额/免费额度")
        print("   · 如果走代理/内网，请改 LLM_BASE_URL 为可访问地址")
        return False


def step3_triage_llm_full_chain():
    """走 run_triage_llm() 全链路：System Prompt + RAG + 模型 + JSON 解析。"""
    print("\n" + "=" * 70)
    print("Step 3: run_triage_llm 导诊全链路（模拟患者胸闷咳嗽）")
    print("=" * 70)
    if not settings.llm_api_key:
        _warn("缺少 LLM_API_KEY，本步将自动降级 Mock")
    symptom = "最近三天咳嗽加重，伴有胸闷，之前有支气管炎病史，无药物过敏"
    kb_context = (
        "【院内科室】呼吸科（擅长咳嗽、支气管炎）、心内科（擅长胸闷胸痛）、"
        "全科医学科、消化内科、神经内科。"
        "【就诊须知】发热咳嗽建议先到预检分诊。"
    )
    t0 = time.time()
    result = run_triage_llm(symptom, kb_context=kb_context, session_history=[])
    dt = (time.time() - t0) * 1000

    provider = result.get("provider_used")
    fallback = result.get("fallback_reason")
    depts = result.get("recommended_departments", [])
    reply = result.get("reply", "")
    trace = result.get("trace_id")

    print(f"  Provider            : {provider}")
    if fallback:
        _warn(f"  Fallback Reason     : {fallback}")
    print(f"  Trace ID            : {trace}")
    print(f"  推荐科室数           : {len(depts)}")
    for d in depts:
        print(f"    · {d['dept_name']}  conf={d['confidence']:.0%}  理由: {d.get('reason','')}")
    print(f"  含免责声明           : {'是' if 'AI建议仅为就诊分诊参考' in reply else '否'}")
    print(f"  总耗时               : {dt:.0f}ms")

    # 断言
    all_pass = True
    if provider not in ("mock", "openai_compatible", "mock_fallback"):
        _fail(f"provider 未知: {provider}"); all_pass = False
    if len(depts) == 0:
        _fail("推荐科室列表为空，导诊不可用"); all_pass = False
    else:
        for d in depts:
            if d["dept_name"] not in VALID_DEPARTMENTS:
                _fail(f"不合规科室名白名单外：{d['dept_name']}"); all_pass = False
    if "AI建议仅为就诊分诊参考" not in reply:
        _fail("缺少强制免责声明，违反合规约束"); all_pass = False
    if not trace or len(trace) < 10:
        _fail("trace_id 太短，埋点不满足"); all_pass = False

    print(f"  回复预览(前 200 字):\n  {reply[:200].replace(chr(10), chr(10)+'  ')}")
    if all_pass:
        _ok("导诊全链路 ✔")
    else:
        _fail("导诊全链路 ❌（见上方）")
    return all_pass


def step4_provider_independent_tests():
    """和外部服务无关的纯本地测试（解析 + 白名单）。"""
    print("\n" + "=" * 70)
    print("Step 4: 纯本地单元测试（<json>解析 + 白名单过滤）")
    print("=" * 70)
    sample_ok = """
您好，根据您的症状分析，推荐：
<json>{
  "recommended_departments": [
    {"dept_name": "呼吸科", "confidence": 0.88, "reason": "症状匹配咳嗽胸闷"},
    {"dept_name": "心内科", "confidence": 0.6, "reason": "需排除心肺问题"},
    {"dept_name": "全科医学科", "confidence": 0.3, "reason": "综合就诊备选"}
  ]
}</json>
【免责声明】AI建议仅为就诊分诊参考，不构成诊断与医嘱，最终就诊方案请遵医护人员判断。
"""
    _reply, depts = _parse_triage_output(sample_ok)
    ok = len(depts) == 3 and all(d["dept_name"] in VALID_DEPARTMENTS for d in depts)
    if ok:
        _ok(f"<json>解析 + 白名单验证通过（提取 {len(depts)} 个科室） ✔")
    else:
        _fail(f"<json>解析异常: {depts}")
        ok = False

    sample_bad = """
<json>{"recommended_departments": [
    {"dept_name": "宇宙诊疗科", "confidence": 1.0},
    {"dept_name": "消化内科", "confidence": 0.7}
]}</json>"""
    _, bad_depts = _parse_triage_output(sample_bad)
    if len(bad_depts) == 1 and bad_depts[0]["dept_name"] == "消化内科":
        _ok("违规科室名「宇宙诊疗科」被自动过滤，只保留合法科室 ✔")
    else:
        _fail(f"违规科室名未过滤干净: {bad_depts}")
        ok = False
    return ok


def step5_fail_fallback():
    """强制配置错误 Key → 确保服务自动降级，不崩溃。"""
    print("\n" + "=" * 70)
    print("Step 5: 自动降级测试（模拟 API Key 错误 → Mock 兜底）")
    print("=" * 70)
    original_key = settings.llm_api_key
    original_provider = settings.llm_provider
    original_enable = settings.llm_enable_triage_real
    try:
        # 临时替换为错误 Key + 强制启用真模型
        settings.llm_provider = "openai_compatible"
        settings.llm_enable_triage_real = 1
        settings.llm_api_key = "sk-fake-wrong-key-123456"
        t0 = time.time()
        r = run_triage_llm("头痛三天伴恶心")
        dt = (time.time() - t0) * 1000

        print(f"  Provider        : {r.get('provider_used')}")
        print(f"  Fallback Reason : {r.get('fallback_reason','(无)')[:120]}")
        print(f"  推荐科室         : {[d['dept_name'] for d in r['recommended_departments']]}")
        print(f"  总耗时           : {dt:.0f}ms")

        conds = [
            r.get("provider_used") == "mock",
            r.get("fallback_reason") is not None,  # 有降级原因
            len(r.get("recommended_departments", [])) > 0,
            "AI建议仅为就诊分诊参考" in r.get("reply", ""),
        ]
        if all(conds):
            _ok("错误 Key 场景自动降级 Mock，服务不中断 ✔")
            return True
        else:
            _fail(f"降级逻辑异常，条件: {conds}")
            return False
    finally:
        settings.llm_api_key = original_key
        settings.llm_provider = original_provider
        settings.llm_enable_triage_real = original_enable


def main():
    print("🚀 MedFlow 通义千问 DashScope 接入验证")
    print(f"   backend 根目录: {ROOT}")

    step1_env_check()
    step2_raw_api()
    step3_ok = step3_triage_llm_full_chain()
    step4_ok = step4_provider_independent_tests()
    step5_ok = step5_fail_fallback()

    print("\n" + "=" * 70)
    print("📊 汇总")
    print("=" * 70)
    all_ok = step3_ok and step4_ok and step5_ok
    if all_ok:
        print(GREEN + "全部关键验证通过 ✅" + RESET)
        print("现在你可以：")
        print("   1. 重启 MedFlow 后端（lsof -ti:8000 | xargs kill; 重新 uvicorn）")
        print("   2. 浏览器访问 http://localhost:5173/patient/login，用 p021/622202000021 登录")
        print("   3. 进入 AI 智能导诊 → 输入症状 → 患者端 meta.provider_used = openai_compatible")
        print("   4. 观测看板埋点 event_type=patient_triage_agent 里会带 provider_used/fallback_reason")
    else:
        print(RED + "有失败项，见上方各步骤排查" + RESET)
        print("   · 如果 Step 2 直连失败，请检查 DashScope Key 与网络，然后重试本脚本")
        print("   · 如果 Step 5 降级失败，请联系代码维护者（降级逻辑有 Bug）")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
