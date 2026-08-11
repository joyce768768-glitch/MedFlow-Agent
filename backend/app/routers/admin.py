"""后台管理路由：用户 / 科室 / 权限矩阵 / 知识库 CRUD。

仅 admin 角色可访问（require_admin 依赖）。
Demo 全 Mock 存储，进程重启数据重置。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.auth import require_admin
from app.schemas import (
    AdminUserCreate,
    AdminUserOut,
    AdminUserUpdate,
    DepartmentCreate,
    DepartmentOut,
    KbEntryCreate,
    KbEntryOut,
    KbEntryUpdate,
    PermissionMatrixOut,
    PermissionMatrixUpdate,
)
from app.storage import KB_CATEGORIES, PERMISSION_ACTIONS, PERMISSION_ROLES, store

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

_VALID_ROLES = set(PERMISSION_ROLES) | {"admin"}


# ==================== 用户管理 ====================
@router.get("/users", response_model=list[AdminUserOut])
def list_users():
    return store.list_users()


@router.post("/users", response_model=AdminUserOut)
def create_user(body: AdminUserCreate):
    if body.role not in _VALID_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"角色非法，可选：{sorted(_VALID_ROLES)}")
    if store.find_user_by_username(body.username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "用户名已存在")
    user = store.create_user(
        username=body.username, password=body.password, name=body.name,
        role=body.role, department=body.department, title=body.title,
    )
    return user


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: str, body: AdminUserUpdate):
    if body.role is not None and body.role not in _VALID_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "角色非法")
    user = store.update_user(user_id, body.model_dump(exclude_none=True))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return user


@router.delete("/users/{user_id}")
def delete_user(user_id: str):
    # 禁止删除当前演示 admin 账号自身，避免锁死后台
    target = store.get_user(user_id)
    if target and target.get("username") == "admin":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "禁止删除默认管理员账号")
    ok = store.delete_user(user_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return {"deleted": True}


# ==================== 科室管理 ====================
@router.get("/departments", response_model=list[DepartmentOut])
def list_departments():
    return store.list_departments()


@router.post("/departments", response_model=DepartmentOut)
def create_department(body: DepartmentCreate):
    return store.add_department(body.name)


@router.put("/departments/{dept_id}", response_model=DepartmentOut)
def update_department(dept_id: str, body: DepartmentCreate):
    dept = store.update_department(dept_id, body.name)
    if dept is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "科室不存在")
    return dept


@router.delete("/departments/{dept_id}")
def delete_department(dept_id: str):
    ok = store.delete_department(dept_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "科室不存在")
    return {"deleted": True}


# ==================== 权限矩阵 ====================
@router.get("/permissions", response_model=PermissionMatrixOut)
def get_permissions():
    return {
        "roles": list(PERMISSION_ROLES),
        "actions": list(PERMISSION_ACTIONS),
        "matrix": store.get_permission_matrix(),
    }


@router.put("/permissions", response_model=PermissionMatrixOut)
def update_permissions(body: PermissionMatrixUpdate):
    matrix = store.set_permission_matrix(body.matrix)
    return {
        "roles": list(PERMISSION_ROLES),
        "actions": list(PERMISSION_ACTIONS),
        "matrix": matrix,
    }


# ==================== 知识库 ====================
@router.get("/kb", response_model=list[KbEntryOut])
def list_kb(category: Optional[str] = None):
    if category and category not in KB_CATEGORIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"分类非法，可选：{list(KB_CATEGORIES)}")
    return store.list_kb(category)


@router.post("/kb", response_model=KbEntryOut)
def create_kb(body: KbEntryCreate):
    if body.category not in KB_CATEGORIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"分类非法，可选：{list(KB_CATEGORIES)}")
    return store.add_kb(
        category=body.category, title=body.title, content=body.content, tags=body.tags,
    )


@router.put("/kb/{kb_id}", response_model=KbEntryOut)
def update_kb(kb_id: str, body: KbEntryUpdate):
    entry = store.update_kb(kb_id, title=body.title, content=body.content, tags=body.tags)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "条目不存在")
    return entry


@router.delete("/kb/{kb_id}")
def delete_kb(kb_id: str):
    ok = store.delete_kb(kb_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "条目不存在")
    return {"deleted": True}


@router.get("/kb/categories")
def list_kb_categories():
    """知识库分类字典（中文名）。"""
    return KB_CATEGORIES
