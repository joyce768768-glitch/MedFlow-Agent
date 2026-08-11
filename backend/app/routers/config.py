"""SubAgent 配置路由：在线开关病历 Agent / 检验汇总 Agent。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_user, require_roles
from app.schemas import SubAgentConfigOut, SubAgentConfigUpdate
from app.storage import store

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/subagents", response_model=SubAgentConfigOut)
def get_config(user: dict = Depends(get_current_user)):
    """读取全局 SubAgent 开关。"""
    return store.get_subagent_config()


@router.put("/subagents", response_model=SubAgentConfigOut)
def update_config(body: SubAgentConfigUpdate, user: dict = Depends(require_roles("attending"))):
    """更新全局 SubAgent 开关，同步到所有患者 State（节点内 if 分支即时生效）。"""
    cfg = store.set_subagent_config(body.enable_emr_subagent, body.enable_lab_subagent)
    return cfg
