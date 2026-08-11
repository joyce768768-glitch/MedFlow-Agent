"""MDT 讨论路由：评论列表 / 提交 / 采纳 / 邀请专家。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import assert_patient_access, get_current_user, require_action
from app.graph.nodes import node_adopt_mdt_comment, node_mdt_invite
from app.schemas import MdtCommentIn, MdtCommentOut, MdtInviteRequest
from app.storage import store

router = APIRouter(prefix="/patients/{patient_id}/mdt", tags=["mdt"])


@router.get("/comments", response_model=list[MdtCommentOut])
def list_comments(patient_id: str, user: dict = Depends(require_action("can_view_mdt"))):
    """MDT 评论列表（提交后冻结，不可修改删除）。"""
    assert_patient_access(user, patient_id, need_write=False)
    state = store.get_patient(patient_id)
    return state.get("mdt_comments", [])


@router.post("/comments", response_model=MdtCommentOut)
def submit_comment(patient_id: str, body: MdtCommentIn, user: dict = Depends(require_action("can_submit_comment"))):
    """提交 MDT 评论（仅 MDT 受邀专家；后端强制 can_submit_comment 权限）。"""
    assert_patient_access(user, patient_id, need_write=False)
    if user["role"] != "mdt_expert":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅 MDT 受邀专家可提交意见")
    from app.storage import now, uid
    state = store.get_patient(patient_id)
    comment = {
        "comment_id": uid("cmt"),
        "author_id": user["user_id"],
        "author_name": user["name"],
        "author_role": user["role"],
        "content": body.content,
        "created_at": now(),
        "is_adopted": False,
        "adopted_by": None,
        "adopted_by_name": None,
        "adopted_at": None,
    }
    comments = list(state.get("mdt_comments", []))
    comments.append(comment)
    store.patch_patient(patient_id, {"mdt_comments": comments})
    store.append_audit(patient_id, "mdt_comment_submit", user, "提交 MDT 专家意见（冻结留痕）")
    return comment


@router.post("/comments/{comment_id}/adopt", response_model=MdtCommentOut)
def adopt_comment(patient_id: str, comment_id: str, user: dict = Depends(get_current_user)):
    """采纳 MDT 意见（仅主治；写入标记 + 推送通知）。"""
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    patch = node_adopt_mdt_comment(state, comment_id=comment_id, actor=user)
    if not patch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "评论不存在")
    store.patch_patient(patient_id, patch)
    store.append_audit(patient_id, "mdt_comment_adopt", user, f"采纳 MDT 意见 {comment_id}")
    # 同步通知索引
    for c in patch["mdt_comments"]:
        if c["comment_id"] == comment_id:
            return c
    raise HTTPException(status.HTTP_404_NOT_FOUND, "评论不存在")


@router.get("/invitations")
def list_invitations(patient_id: str, user: dict = Depends(get_current_user)):
    """MDT 邀请白名单（主治可查）。"""
    assert_patient_access(user, patient_id, need_write=True)
    state = store.get_patient(patient_id)
    return state.get("mdt_invitations", [])


@router.post("/invite")
def invite_expert(patient_id: str, body: MdtInviteRequest, user: dict = Depends(get_current_user)):
    """邀请 MDT 专家：调用 MDT 邀请子 Workflow（临时授权 + 时效 + 白名单写入）。"""
    assert_patient_access(user, patient_id, need_write=True)
    expert = store.get_user(body.expert_id)
    if expert is None or expert["role"] != "mdt_expert":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "受邀用户不是 MDT 专家")
    state = store.get_patient(patient_id)
    # 调用 MDT 邀请子 Workflow 的节点（带业务参数；子图 mdt_invite_graph 已编译，可供编排演示）
    patch = node_mdt_invite(
        state,
        expert_id=body.expert_id,
        expert_name=expert["name"],
        expires_hours=body.expires_hours,
        actor=user,
    )
    store.patch_patient(patient_id, patch)
    # 推送站内通知给专家
    store.push_notify(patient_id, body.expert_id, "mdt_invited",
                      f"您被邀请参与患者 {state.get('patient_name')} 的 MDT 会诊。")
    store.append_audit(patient_id, "mdt_invite", user, f"邀请专家 {expert['name']}（时效 {body.expires_hours}h）")
    return store.get_patient(patient_id).get("mdt_invitations", [])
