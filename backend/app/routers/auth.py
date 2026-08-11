"""鉴权路由：登录 / 当前用户 / 权限视图。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import build_permission_view, create_access_token, get_current_user
from app.schemas import LoginRequest, LoginResponse, PermissionView, UserOut
from app.storage import store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    user = store.find_user_by_username(body.username)
    if user is None or user.get("password") != body.password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    token = create_access_token(user)
    return {
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "department": user["department"],
            "title": user["title"],
        },
    }


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "department": user["department"],
        "title": user["title"],
    }


@router.get("/permissions", response_model=PermissionView)
def permissions(user: dict = Depends(get_current_user)):
    """返回当前角色的前端动作权限位（仅视图显隐）。"""
    return build_permission_view(user)
