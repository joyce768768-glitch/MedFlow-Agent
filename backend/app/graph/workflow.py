"""LangGraph Workflow 构建。

- admission_graph：主接诊流程图
    START -> 准入校验 -> 接诊(节点内 if 开关分支) -> END(HITL 卡点)
  方案A：接诊节点内部判断 enable_emr_subagent，不维护两套 Graph，
  两条分支收敛至同一 HITL 终审卡点（hitl_pending=True）。

- mdt_invite_graph：MDT 邀请子 Workflow（临时授权 + 时效 + 白名单写入）
  作为可独立调用的子图，演示子 Workflow 编排。

其余节点（开立检查任务 / 新建诊疗版本 / 采纳意见 / 归档审计）为纯函数节点，
由路由按需直接调用，复用同一份 nodes.py，保证逻辑单点维护。
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

# START 常量在不同版本 langgraph 中名称不同，使用 set_entry_point API
START = "__start__"

from app.graph.nodes import (
    node_admit_emr,
    node_admission_guard,
    node_mdt_invite,
)
from app.graph.state import PatientState


def build_admission_graph():
    """主接诊流程图：准入 -> 接诊(分支) -> HITL 卡点。"""
    g = StateGraph(PatientState)
    g.add_node("admission_guard", node_admission_guard)
    g.add_node("admit_emr", node_admit_emr)
    g.add_edge(START, "admission_guard")
    g.add_edge("admission_guard", "admit_emr")
    # 接诊后进入 HITL 终审卡点（图在此处结束，等待人工确认）
    g.add_edge("admit_emr", END)
    return g.compile()


def build_mdt_invite_graph():
    """MDT 邀请子 Workflow（独立子图）。"""
    g = StateGraph(PatientState)
    g.add_node("mdt_invite", node_mdt_invite)
    g.add_edge(START, "mdt_invite")
    g.add_edge("mdt_invite", END)
    return g.compile()


# 编译一次，模块级复用
admission_graph = build_admission_graph()
mdt_invite_graph = build_mdt_invite_graph()
