"""M3 双 Agent 编排测试（MedFlow 域）。

供型为强制真 LLM：传输层 _llm 在测试中替换为脚本回放（校验规划/回答的编排
逻辑，不测网络）；关键用例覆盖意图边界前置拦截、臆造视图拦截、解析失败
规则兜底、无视图如实相告、无 key 503。TAT 链路对演示库实跑（集成）。
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import semantic_orchestrator as so
from app.config import settings
from app.database import _DB_PATH
from app.routers import semantic_ask

DB_EXISTS = os.path.exists(_DB_PATH)

PLAN_TAT = {
    "view_id": "medflow.view.tat_by_department",
    "intent": "metric_query",
    "filters": {},
    "reasoning": "问题问科室周转，命中 avg(tat_hours) by day, department",
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
    app.include_router(semantic_ask.router)
    return TestClient(app)


@pytest.fixture
def fake_llm(monkeypatch):
    def _install(responses):
        llm = FakeLLM(responses)
        monkeypatch.setattr(so, "_llm", llm)
        monkeypatch.setattr(settings, "llm_api_key", "test-key")
        return llm
    return _install


# ---------------- 链路：回答成功（集成演示库） ----------------

@pytest.mark.skipif(not DB_EXISTS, reason=f"无演示库: {_DB_PATH}")
def test_happy_path_tat_question(client, fake_llm):
    llm = fake_llm([
        json.dumps(PLAN_TAT, ensure_ascii=False),      # 规划轮
        "近 7 天心内科平均检验周转最长，为 4.2 小时（口径：avg(tat_hours)，仅统计完成≥开单的有效样本）。",  # 回答轮
    ])
    r = client.post("/semantic/ask", json={"question": "上周哪个科室检验周转最慢？"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "answered"
    assert body["view"] == "medflow.view.tat_by_department"
    assert body["planner"] == "llm"
    assert body["provider_used"] == "openai_compatible"
    assert body["data"]["row_count"] > 0
    assert body["sql"]                                     # 铁律②：SQL/provenance 随结果可溯
    assert body["provenance"]
    # 规划 prompt 只含语义注册表，不含物理列名（铁律①）
    plan_msgs = llm.calls[0]
    assert "科室检验平均周转时间" in plan_msgs[0]["content"]
    assert "exam_reports" not in plan_msgs[0]["content"]


# ---------------- 校验·第一道：意图边界（生成之前拦截） ----------------

def test_diagnosis_keyword_blocked_before_any_llm_call(client, fake_llm):
    llm = fake_llm([])
    r = client.post("/semantic/ask", json={"question": "帮我确诊这个患者是不是胃炎"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "blocked"
    v = body["validation"]["violations"]
    assert v
    assert v[0]["rule_id"] == "VA-001"
    assert "no_direct_ai_diagnosis" in v[0]["message"]
    assert len(llm.calls) == 0                             # 拦截在规划调用之前


def test_planner_intent_enum_blocked(client, fake_llm):
    llm = fake_llm([
        json.dumps({"view_id": None, "intent": "prescription_request", "reasoning": "要开药"}),
    ])
    r = client.post("/semantic/ask", json={"question": "针对这个指标给患者下一步方案"})
    body = r.json()
    assert body["stage"] == "blocked"
    assert body["validation"]["violations"][0]["rule_id"] == "VA-001"
    assert len(llm.calls) == 1                             # 只花了一次规划调用


# ---------------- 校验·第二道：视图合法性 ----------------

def test_hallucinated_view_blocked_by_validator(client, fake_llm):
    fake_llm([
        json.dumps({"view_id": "medflow.view.ghost", "intent": "metric_query"}),
    ])
    r = client.post("/semantic/ask", json={"question": "上月门诊量多少？"})
    body = r.json()
    assert body["stage"] == "blocked"
    v = body["validation"]["violations"][0]
    assert v["rule_id"] == "SC-V002"                       # 契约 validate_plan 的机判编号
    assert "臆造" in v["message"]


# ---------------- 规划：解析失败重试 → 规则兜底 ----------------

@pytest.mark.skipif(not DB_EXISTS, reason=f"无演示库: {_DB_PATH}")
def test_parse_failure_twice_falls_back_to_rule_plan(client, fake_llm):
    llm = fake_llm([
        "抱歉，我无法输出 JSON。",                          # 规划第 1 次：解析失败
        "这个问题嘛……",                                    # 规划第 2 次：仍失败
        "近 7 天检验开单量分布如下（口径见视图）。",          # 回答轮
    ])
    r = client.post("/semantic/ask", json={"question": "上周各科室检验周转时间怎么样"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "answered"
    assert body["planner"] == "rule_fallback"
    assert body["view"] == "medflow.view.tat_by_department"
    assert len(llm.calls) == 3                             # 规划×2 + 回答×1


def test_no_view_reply_lists_published_views(client, fake_llm):
    fake_llm([json.dumps({"view_id": None, "intent": "out_of_scope", "reasoning": "无关问题"})])
    r = client.post("/semantic/ask", json={"question": "今天午饭吃什么"})
    body = r.json()
    assert body["stage"] == "no_view"
    assert "已发布视图" in body["reply"]
    assert "科室检验平均周转时间" in body["reply"]


# ---------------- 供型：强制真 LLM ----------------

def test_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", None)
    r = client.post("/semantic/ask", json={"question": "上周哪个科室检验周转最慢？"})
    assert r.status_code == 503
    assert "llm_api_key" in r.json()["detail"]


def test_empty_question_400(client):
    r = client.post("/semantic/ask", json={"question": "   "})
    assert r.status_code == 400


def test_llm_network_failure_surfaces_as_502(client, fake_llm):
    fake_llm([RuntimeError("LLM 网络调用失败（重试 3 次）: timeout")])
    r = client.post("/semantic/ask", json={"question": "上周哪个科室检验周转最慢？"})
    assert r.status_code == 502
