"""JWT 简易登录 + RBAC 权限依赖。

设计要点：
- 动作权限（能不能编辑/采纳/开单）与病例数据范围（能看哪些患者）解耦；
- 后端强制二次鉴权，前端仅做视图显隐，不依赖前端做安全控制；
- Demo 角色固定：attending / mdt_expert / nurse / readonly。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings
from app.storage import store

# tokenUrl 仅用于 OpenAPI 文档展示，实际登录走 /auth/login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def create_access_token(user: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user["user_id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """从 Bearer Token 解析当前用户（强制鉴权）。"""
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未提供认证令牌")
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "认证令牌无效或已过期")
    user = store.get_user(payload.get("sub", ""))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


def require_roles(*roles: str):
    """动作权限：要求当前用户属于指定角色之一。"""

    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"当前角色({user['role']})无此操作权限")
        return user

    return _dep


# ---------- 数据范围 & 二次鉴权 ----------
def assert_patient_access(user: dict, patient_id: str, need_write: bool = False) -> None:
    """病例数据范围二次鉴权（后端强制）。

    - need_write=True：仅该患者的主治医生可写；
    - need_write=False：
        * attending：仅自己的患者可读；
        * mdt_expert：仅被有效邀请的患者可读；
        * nurse：可读所有患者基础信息（分诊）；
        * readonly：可读所有患者（全病案只读）。
    """
    state = store.get_patient(patient_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "患者不存在")

    role = user["role"]
    uid_ = user["user_id"]

    if need_write:
        # 写权限：仅该患者的主治医生
        if role != "attending" or uid_ not in state.get("attending_doctor_ids", []):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "无该患者的写权限（仅主治医生）")
        return

    # 只读范围
    if role == "attending":
        if uid_ not in state.get("attending_doctor_ids", []):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "非该患者主治医生，无权查看")
    elif role == "mdt_expert":
        invited = any(
            inv.get("expert_id") == uid_ and inv.get("active")
            for inv in state.get("mdt_invitations", [])
        )
        if not invited:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "未受邀参与该患者 MDT")
    elif role == "nurse":
        return  # 护士可读基础信息
    elif role == "readonly":
        return  # 历史只读医生可读全病案
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "未知角色")


def can_write_patient(user: dict, patient_id: str) -> bool:
    """便捷判断（不抛异常）。"""
    try:
        assert_patient_access(user, patient_id, need_write=True)
        return True
    except HTTPException:
        return False


def build_permission_view(user: dict) -> dict:
    """根据角色构建前端动作权限位（仅视图显隐，安全以后端为准）。

    权限由后台「角色-动作开关矩阵」动态驱动（store.permission_matrix），
    管理员可在 /admin/permissions 调整，保存后即时影响前端显隐与后端 require_action 鉴权。
    admin 角色返回全 False 临床权限（其权限在后台管理域）。
    """
    role = user["role"]
    perm = store.role_permissions(role)
    perm["role"] = role
    return perm


def require_action(action: str):
    """资源级动作权限依赖（后端强制二次鉴权，不依赖前端视图显隐）。

    读取后台可配置的权限矩阵；例如管理员关闭护士 can_view_check 后，
    护士请求检查任务列表将被后端直接拦截返回 403。
    """

    def _dep(user: dict = Depends(get_current_user)) -> dict:
        perm = store.role_permissions(user["role"])
        if not perm.get(action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"当前角色无 {action} 权限")
        return user

    return _dep


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """后台管理域权限：仅 admin 角色可访问 /admin/* 路由。"""
    if user["role"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅管理员可访问后台")
    return user
