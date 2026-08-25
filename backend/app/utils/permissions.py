"""Centralized permission registry.

One table maps a permission key to the roles allowed to use it, so tightening or
relaxing access is a single-line edit instead of a hunt through routers.

Naming: `{resource}:{action}`. Two granularities exist on purpose:
- `*:view`    full records (amounts, terms, attachments) — restricted
- `*:options` id + name only, for dropdowns — broadly available
"""
from fastapi import Depends, HTTPException, status

from .auth import get_current_user

ALL_ROLES = (
    "admin",
    "finance",
    "project_manager",
    "procurement",
    "construction",
    "warehouse",
)

# NOTE: HZY 2026-08-20 — 项目列表/合同/验收资料 仅管理员、项目负责人可查看。
# 财务与采购改用 `*:options` 精简接口完成付款、收款确认等本职工作。
PERMISSION_ROLES: dict[str, tuple[str, ...]] = {
    # 用户
    # 精简用户选项：给项目指派负责人用。完整用户管理仍然只有 admin。
    "user:options": ("admin", "project_manager"),
    # 项目
    "project:list": ("admin", "project_manager"),
    "project:options": ALL_ROLES,
    "project:write": ("admin", "project_manager"),
    "project:delete": ("admin",),
    # 合同
    "contract:view": ("admin", "project_manager"),
    "contract:options": ("admin", "project_manager", "finance", "procurement"),
    "contract:write": ("admin", "project_manager", "procurement"),
    "contract:delete": ("admin",),
    "contract:payment": ("admin", "finance"),
    # 验收资料
    "acceptance:view": ("admin", "project_manager"),
    "acceptance:write": ("admin", "project_manager"),
    "acceptance:delete": ("admin",),
    # 发票
    "invoice:view": ("admin", "project_manager", "finance"),
    "invoice:manage": ("admin", "finance"),
    # 报销链路
    "reimburse:audit_manager": ("admin", "project_manager"),
    "reimburse:audit_finance": ("admin", "finance"),
    "reimburse:receipt": ("admin", "finance"),
    "reimburse:receipt_skip": ("admin",),
    "reimburse:document": ("admin", "finance"),
    "reimburse:voucher": ("admin", "finance"),
    "reimburse:pay": ("admin", "finance"),
    "reimburse:delete": ("admin",),
    # 分析 / 预警
    "analysis:overview": ("admin", "finance", "project_manager"),
    # 看板的预警文案里带预算、合同金额、未开票余额，跟项目/合同查看权限对齐。
    # 「我的待办」(`/api/todos`) 不在此列：它按用户逐条派发，只包含该用户本职要处理的事。
    "alerts:board": ("admin", "finance", "project_manager"),
}


def roles_for(permission: str) -> tuple[str, ...]:
    """Roles allowed to use `permission`. Unknown keys grant nobody but admin."""
    return PERMISSION_ROLES.get(permission, ("admin",))


def has_permission(role: str, permission: str) -> bool:
    """Whether `role` may use `permission`."""
    return role in roles_for(permission)


def require_permission(permission: str):
    """FastAPI dependency enforcing `permission` on the current user's role."""

    def permission_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if not has_permission(current_user.get("role"), permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足，无法执行此操作",
            )
        return current_user

    return permission_checker
