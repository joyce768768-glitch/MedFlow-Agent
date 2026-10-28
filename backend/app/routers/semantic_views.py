"""M2 语义视图层：契约 YAML → 编译器 → SQLite 实跑的 REST 出口。

三层铁律的路由级落地：
- GET  /semantic/views            纯语义注册表（id/口径/粒度/时间窗），直接可注入 LLM prompt
- GET  /semantic/views/{view_id}/probe  单视图元数据（含字段语义，供规划 Agent 引用）
- POST /semantic/views/{view_id}/query  编译 → 策略机判 → 实跑，返回数据 + provenance + SQL

本路由只做「视图调用」，不碰业务表——AI 永不直接摸物理 schema 的边界示范。
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from semantic_contract import (
    PolicyViolationError,
    compile_view,
    load_entity,
    semantic_registry,
)
from semantic_contract.executor import execute, open_sqlite

from ..database import _DB_PATH, ensure_schema

router = APIRouter(prefix="/semantic", tags=["semantic"])

_ENTITY = load_entity("medflow")


class ViewQueryRequest(BaseModel):
    """维度过滤（可选）。时间窗由视图定义固定（时态策略：禁止全表聚合）。"""

    filters: Dict[str, Any] = {}


@router.get("/views")
def list_views():
    """纯语义视图注册表——查询规划 Agent 的命中目标清单。"""
    return {
        "entity": _ENTITY["metadata"]["id"],
        "version": _ENTITY["metadata"]["version"],
        "views": semantic_registry(_ENTITY),
    }


@router.get("/views/{view_id}/probe")
def probe_view(view_id: str):
    """单视图探测：编译 SQL 但不执行（诊断/教学用，暴露物理层于受控出口）。"""
    try:
        q = compile_view(_ENTITY, view_id, dialect="sqlite")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"compiled_sql": q.sql, "columns": q.columns, "provenance": q.provenance}


@router.post("/views/{view_id}/query")
def query_view(view_id: str, req: ViewQueryRequest):
    """执行语义视图：编译 → 策略机判 → SQLite 实跑 → 数据 + 依据。"""
    try:
        q = compile_view(_ENTITY, view_id, dialect="sqlite", params=req.filters)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PolicyViolationError as exc:
        raise HTTPException(status_code=422, detail={"blocked_by": "policy", "violations": exc.violations}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ensure_schema()  # 幂等；演示库可能尚未初始化
    conn = open_sqlite(_DB_PATH)
    try:
        result = execute(q, conn)
    except Exception as exc:  # SQL 层错误原样上报（演示可观测性）
        raise HTTPException(status_code=500, detail=f"视图执行失败: {exc}") from exc
    finally:
        conn.close()
    return result
