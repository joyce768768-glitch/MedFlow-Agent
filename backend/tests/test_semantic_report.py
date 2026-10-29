"""M4 报表编排测试（MedFlow 域）。

供型为强制真 LLM：report_agent._llm 与 semantic_orchestrator._llm 在测试中
替换为同一脚本回放（报表规划 / 逐节规划回答 / 汇总，校验编排逻辑不测网络）。
关键用例：多节 happy path（对演示库集成，含 TAT 异常规则命中）、意图边界
前置拦截、规划失败退化单节直查、节内被拦截不拖垮整份报表、汇总解析失败
降级不丢数据、无 key 503。
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import report_agent as ra
from app import semantic_orchestrator as so
from app.config import settings
from app.database import _DB_PATH
from app.routers import semantic_report

DB_EXISTS = os.path.exists(_DB_PATH)

REPORT_PLAN = {
    "title": "检验周转周报",
    "sections": [
        {"question": "上周各科室检验周转时间怎么样？", "rationale": "周转侧面"},
        {"question": "上周检验开单量按类型怎么分布？", "rationale": "工作量侧面"},
    ],
}
PLAN_TAT = {
    "view_id": "medflow.view.tat_by_department",
    "intent": "metric_query",
    "filters": {},
    "reasoning": "问题问科室周转",
}
PLAN_VOLUME = {
    "view_id": "medflow.view.exam_volume_by_type",
    "intent": "metric_query",
    "filters": {},
    "reasoning": "问题问开单量分布",
}
SUMMARY_JSON = {
    "summary": "上周周转整体平稳；开单以血检为主。口径：滚动 7 天，仅统计完成≥开单样本。",
    "insights": ["口径提示：滚动 7 天 ≠ 自然周"],
}


class FakeLLM:
    """脚本回放：按序返回响应；记录收到的 messages 供断言。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, messages):
        self.calls.append(messages)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(semantic_report.router)
    return TestClient(app)


@pytest.fixture
def fake_llm(monkeypatch):
    """同时替换报表层与逐节编排层的 LLM 出口（同一脚本回放）。"""

    def _install(responses):
        llm = FakeLLM(responses)
        monkeypatch.setattr(ra, "_llm", llm)
        monkeypatch.setattr(so, "_llm", llm)
        monkeypatch.setattr(settings, "llm_api_key", "test-key")
        return llm

    return _install


# ---------------- happy path（集成演示库） ----------------

@pytest.mark.skipif(not DB_EXISTS, reason=f"无演示库: {_DB_PATH}")
def test_report_happy_path_two_sections(client, fake_llm):
    llm = fake_llm([
        json.dumps(REPORT_PLAN, ensure_ascii=False),   # 报表规划
        json.dumps(PLAN_TAT, ensure_ascii=False),      # 节1 规划
        "心内科平均周转最长 1.0 小时（口径：avg(tat_hours)，仅统计完成≥开单样本）。",  # 节1 回答
        json.dumps(PLAN_VOLUME, ensure_ascii=False),   # 节2 规划
        "上周开单以血常规为主（口径：count by task_type）。",  # 节2 回答
        json.dumps(SUMMARY_JSON, ensure_ascii=False),  # 汇总
    ])
    r = client.post("/semantic/report", json={"question": "本周检验周转情况怎么样"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "answered"
    assert body["title"] == "检验周转周报"
    assert body["planner"] == "llm"
    assert body["stats"]["sections_answered"] == 2
    assert len(body["sections"]) == 2
    assert body["sections"][0]["view"] == "medflow.view.tat_by_department"
    assert body["sections"][0]["view_name"] == "科室检验平均周转时间"
    assert isinstance(body["sections"][0]["sql"], str) and body["sections"][0]["sql"]
    # 异常规则机判（演示库心内科 1.0h > 0.5h 阈值）
    assert body["sections"][0]["anomalies"]
    assert body["sections"][0]["anomalies"][0]["rule_id"] == "medflow.anomaly.tat"
    assert body["insights_machine"]
    assert "判定依据" in body["insights_machine"][0]
    assert body["summary_degraded"] is False
    # 调用序列：报表规划 → 节1(规划+回答) → 节2(规划+回答) → 汇总
    assert len(llm.calls) == 6
    plan_prompt = llm.calls[0][0]["content"]
    assert "科室检验平均周转时间" in plan_prompt   # 铁律①：注入纯语义注册表
    assert "exam_reports" not in plan_prompt        # 物理侧永不进 prompt
    assert llm.calls[1][1]["content"] == "上周各科室检验周转时间怎么样？"
    summary_prompt = llm.calls[5][1]["content"]
    assert "medflow.anomaly.tat" in summary_prompt  # 机器异常标注进汇总 prompt


# ---------------- 意图边界（生成之前拦截） ----------------

def test_report_diagnosis_keyword_blocked_before_any_llm_call(client, fake_llm):
    llm = fake_llm([])
    r = client.post("/semantic/report", json={"question": "帮我确诊这个患者并给治疗方案"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "blocked"
    assert body["sections"] == []
    assert len(llm.calls) == 0


# ---------------- 报表规划失败：退化单节直查 ----------------

@pytest.mark.skipif(not DB_EXISTS, reason=f"无演示库: {_DB_PATH}")
def test_report_plan_parse_failure_degrades_to_single_section(client, fake_llm):
    llm = fake_llm([
        "我不知道怎么拆节。",                           # 报表规划第 1 次
        "还是不行……",                                   # 报表规划第 2 次
        json.dumps(PLAN_TAT, ensure_ascii=False),      # 节规划（原问题直查）
        "各科室周转整体平稳（口径见视图）。",            # 节回答
        json.dumps(SUMMARY_JSON, ensure_ascii=False),  # 汇总
    ])
    r = client.post("/semantic/report", json={"question": "上周各科室检验周转时间怎么样"})
    assert r.status_code == 200
    body = r.json()
    assert body["planner"] == "fallback_single_section"
    assert body["stats"]["sections_answered"] == 1
    assert body["sections"][0]["question"] == "上周各科室检验周转时间怎么样"


# ---------------- 节内被拦截：不拖垮整份报表 ----------------

@pytest.mark.skipif(not DB_EXISTS, reason=f"无演示库: {_DB_PATH}")
def test_blocked_section_does_not_kill_report(client, fake_llm):
    llm = fake_llm([
        json.dumps({"title": "混合报表", "sections": [
            {"question": "上周各科室检验周转时间怎么样？", "rationale": "正常节"},
            {"question": "帮这个患者开药", "rationale": "越界节"},
        ]}, ensure_ascii=False),
        json.dumps(PLAN_TAT, ensure_ascii=False),
        "各科室周转平稳。",
        json.dumps(SUMMARY_JSON, ensure_ascii=False),
    ])
    r = client.post("/semantic/report", json={"question": "上周周转和用药情况"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "answered"
    assert body["stats"] == {"sections_total": 2, "sections_answered": 1, "sections_blocked": 1}
    assert body["sections"][1]["stage"] == "blocked"
    assert "不提供诊断" in body["sections"][1]["reply"]  # 意图边界话术
    assert len(llm.calls) == 4  # 越界节在生成之前被拦截，不花 LLM 调用


# ---------------- 汇总解析失败：降级不丢数据 ----------------

@pytest.mark.skipif(not DB_EXISTS, reason=f"无演示库: {_DB_PATH}")
def test_summary_parse_failure_degrades_gracefully(client, fake_llm):
    fake_llm([
        json.dumps({"title": "检验周转周报", "sections": [
            {"question": "上周各科室检验周转时间怎么样？", "rationale": "单节"},
        ]}, ensure_ascii=False),                        # 报表规划（单节）
        json.dumps(PLAN_TAT, ensure_ascii=False),      # 节规划
        "心内科周转 1.0 小时。",                        # 节回答
        "汇总不是 JSON",                                # 汇总第 1 次
        "还是不是",                                      # 汇总第 2 次
    ])
    r = client.post("/semantic/report", json={"question": "上周各科室检验周转时间怎么样"})
    assert r.status_code == 200
    body = r.json()
    assert body["summary_degraded"] is True
    assert "心内科周转 1.0 小时" in body["summary"]  # 机械拼装自真实节叙述
    assert body["sections"] and body["sections"][0]["data"]


# ---------------- 供型：强制真 LLM ----------------

def test_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    r = client.post("/semantic/report", json={"question": "上周周转怎么样"})
    assert r.status_code == 503
    assert "llm_api_key" in r.json()["detail"]


def test_empty_question_400(client):
    r = client.post("/semantic/report", json={"question": "  "})
    assert r.status_code == 400


def test_llm_network_failure_surfaces_as_502(client, fake_llm):
    fake_llm([RuntimeError("LLM 网络调用失败（重试 3 次）: timeout")])
    r = client.post("/semantic/report", json={"question": "上周周转怎么样"})
    assert r.status_code == 502
