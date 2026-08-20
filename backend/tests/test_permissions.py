"""Tests for the centralized permission registry.

HZY 2026-08-20: 项目列表 / 合同 / 验收资料 仅管理员、项目负责人可查看；
财务与采购改用 `*:options` 精简接口。这些默认值是需求，不是实现细节，所以钉住。
"""
import pytest
from fastapi import HTTPException

from app.utils.permissions import (
    ALL_ROLES,
    PERMISSION_ROLES,
    has_permission,
    require_permission,
    roles_for,
)

RESTRICTED_VIEWS = ("project:list", "contract:view", "acceptance:view")


def _check(permission: str, role: str) -> dict:
    """Invoke the dependency's inner checker directly."""
    return require_permission(permission)(current_user={"role": role, "user_id": "u1"})


# --- 需求钉子: 三个受限视图只有 admin + 项目负责人 -------------------------

@pytest.mark.parametrize("permission", RESTRICTED_VIEWS)
def test_restricted_views_are_admin_and_project_manager_only(permission):
    assert roles_for(permission) == ("admin", "project_manager")


@pytest.mark.parametrize("permission", RESTRICTED_VIEWS)
@pytest.mark.parametrize("role", ["finance", "procurement", "construction", "warehouse"])
def test_restricted_views_reject_other_roles(permission, role):
    assert has_permission(role, permission) is False
    with pytest.raises(HTTPException) as exc:
        _check(permission, role)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("permission", RESTRICTED_VIEWS)
@pytest.mark.parametrize("role", ["admin", "project_manager"])
def test_restricted_views_allow_admin_and_pm(permission, role):
    assert has_permission(role, permission) is True
    assert _check(permission, role)["role"] == role


# --- options 粒度: 收紧后财务/采购仍能完成本职工作 -------------------------

def test_project_options_available_to_everyone():
    assert roles_for("project:options") == ALL_ROLES
    for role in ALL_ROLES:
        assert has_permission(role, "project:options") is True


@pytest.mark.parametrize("role", ["finance", "procurement"])
def test_contract_options_available_where_view_is_not(role):
    assert has_permission(role, "contract:view") is False
    assert has_permission(role, "contract:options") is True


def test_contract_options_still_excludes_construction_and_warehouse():
    for role in ("construction", "warehouse"):
        assert has_permission(role, "contract:options") is False


def test_finance_keeps_contract_payment_without_contract_view():
    assert has_permission("finance", "contract:payment") is True
    assert has_permission("finance", "contract:view") is False


# --- 报销链路权限 -----------------------------------------------------------

def test_receipt_skip_is_admin_only():
    assert roles_for("reimburse:receipt_skip") == ("admin",)
    assert has_permission("finance", "reimburse:receipt") is True
    assert has_permission("finance", "reimburse:receipt_skip") is False


@pytest.mark.parametrize("permission", [
    "reimburse:receipt", "reimburse:document", "reimburse:voucher", "reimburse:pay",
])
def test_finance_owns_the_money_side_of_the_chain(permission):
    assert has_permission("finance", permission) is True
    assert has_permission("construction", permission) is False


def test_manager_audit_belongs_to_project_manager_not_finance():
    assert has_permission("project_manager", "reimburse:audit_manager") is True
    assert has_permission("finance", "reimburse:audit_manager") is False
    assert has_permission("project_manager", "reimburse:audit_finance") is False


# --- 兜底行为 ---------------------------------------------------------------

def test_unknown_permission_grants_admin_only():
    assert roles_for("nope:whatever") == ("admin",)
    assert has_permission("admin", "nope:whatever") is True
    assert has_permission("project_manager", "nope:whatever") is False


def test_admin_is_allowed_everywhere():
    for permission in PERMISSION_ROLES:
        assert has_permission("admin", permission) is True, permission


def test_missing_role_is_rejected():
    with pytest.raises(HTTPException) as exc:
        require_permission("project:list")(current_user={"user_id": "u1"})
    assert exc.value.status_code == 403
