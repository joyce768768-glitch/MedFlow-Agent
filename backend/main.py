"""医院诊疗 Agent 工作台 Demo —— FastAPI 入口。

启动：uvicorn main:app --host 0.0.0.0 --port 8000 --reload
（或在 backend 目录执行：python main.py）
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.storage import store
# 导入即播种 Mock 数据
import app.mock_data  # noqa: F401
from app.routers import (
    admin,
    admin_ext,
    auth,
    chat,
    check_tasks,
    config,
    consultation,
    emr,
    imaging,
    lab,
    lab_worklist,
    mdt,
    memory,
    notify,
    orchestrator,
    patient_ext,
    patients,
    prediction,
    treatment,
    kg_admin,
    semantic_views,
)

app = FastAPI(
    title="医院诊疗 Agent 工作台 Demo",
    description=(
        "垂直医疗 B 端 Agent 工作台：LangGraph Workflow 骨架 + 可插拔 SubAgent 节点（方案A：同节点 if 开关分支）。"
        "Demo 全 Mock，不对接真实 HIS/LIS/PACS。"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
for r in (auth, patients, treatment, mdt, check_tasks, emr, config, notify, admin, admin_ext, patient_ext, prediction, consultation, orchestrator, lab, lab_worklist, memory, chat, imaging, kg_admin, semantic_views):
    app.include_router(r.router)


@app.middleware("http")
async def _persist_after_request(request, call_next):
    """M1 数据底座：请求边界统一落盘（内存缓存 → SQLite）。

    Store 的 170 个方法保持纯内存语义；每个请求结束后整体 flush 一次
    （演示级数据量毫秒级），保证重启数据不丢。种子灌完后也会显式落盘。
    """
    response = await call_next(request)
    try:
        store.persist_all()
    except Exception as exc:  # 落盘失败不阻断响应（下次请求会再次尝试）
        print(f"[persist] flush 失败: {exc}", file=__import__("sys").stderr)
    return response


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": "hospital-agent-workstation", "version": "1.0.0"}


@app.get("/users", tags=["users"])
def list_users():
    """演示账号列表（方便面试官切换；含 user_id 供 MDT 邀请）。"""
    return [
        {"user_id": u["user_id"], "username": u["username"], "password": "123456",
         "name": u["name"], "role": u["role"], "department": u["department"]}
        for u in store.list_users()
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.backend_host, port=settings.backend_port, reload=True)
