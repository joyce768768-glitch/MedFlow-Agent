"""M3 语义问答路由：双 Agent 编排的 REST 出口。

POST /api/semantic/ask   NL 问答主链路（规划 → 校验 → 执行 → 带依据回答）

供型为强制真 LLM：未配置 API key 返回 503 + 配置指引；规划意图越界 / 视图
不合法 / 策略机判不通过分别返回 blocked 响应或 422，不做 Mock 降级。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from semantic_contract import PolicyViolationError

from ..semantic_orchestrator import LLMNotConfiguredError, ask_question

router = APIRouter(prefix="/semantic", tags=["semantic-ask"])


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(req: AskRequest):
    """NL 问答：永不直接摸物理 schema，只走语义视图编排链路。"""
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    try:
        return ask_question(question)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PolicyViolationError as exc:
        # 第三道校验：编译期策略机判（如 tat 无时间窗）——结构化暴露违规
        raise HTTPException(
            status_code=422,
            detail={"blocked_by": "machine_check", "violations": exc.violations},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"查询计划不可执行: {exc}") from exc
    except RuntimeError as exc:
        # LLM 网络/HTTP 失败：强制真 LLM 策略下不降级，如实上报
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}") from exc
