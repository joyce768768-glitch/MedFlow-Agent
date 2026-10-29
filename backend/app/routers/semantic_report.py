"""M4 报表编排路由：Data Agent 多节报表的 REST 出口。

POST /api/semantic/report   NL 问题 → 多节复合报表（规划 → 逐节 M3 链路 → 异常标注 → 汇总）

供型为强制真 LLM：未配置 API key 返回 503 + 配置指引；逐节校验拦截不降级；
LLM 网络失败如实上报 502。报表节内单个 LLM 失败上抛（不做节级静默降级），
仅「汇总文本解析失败」降级为机械拼装（数据层不受影响，打 summary_degraded 标记）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from semantic_contract import PolicyViolationError

from ..report_agent import ask_report
from ..semantic_orchestrator import LLMNotConfiguredError

router = APIRouter(prefix="/semantic", tags=["semantic-report"])


class ReportRequest(BaseModel):
    question: str


@router.post("/report")
def report(req: ReportRequest):
    """NL 报表：规划 Agent 拆节，每节只走语义视图编排链路，永不直接摸物理 schema。"""
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    try:
        return ask_report(question)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PolicyViolationError as exc:
        # 逐节执行的编译期策略机判（如 tat 无时间窗）——结构化暴露违规
        raise HTTPException(
            status_code=422,
            detail={"blocked_by": "machine_check", "violations": exc.violations},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"报表计划不可执行: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}") from exc
