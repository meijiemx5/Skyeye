"""Tests for T1: contract invoice_amount + invoice_date fields.

Runs without AWS/DynamoDB:
- Schema tests import pure Pydantic models from app.schemas.contract.
- _contract_to_dict is exercised with a SimpleNamespace stub (no model.save()).
"""
import types

import pytest
from pydantic import ValidationError

from app.schemas.contract import ContractCreate, ContractUpdate, ContractOut
from app.routers.contracts import _contract_to_dict


# --- helpers ---------------------------------------------------------------

# Minimal-but-complete valid payload for the required ContractCreate fields.
_CREATE_REQUIRED = {
    "contract_name": "施工合同A",
    "contract_type": "client",
    "party_name": "甲方公司",
}

# Fields required by ContractOut (those without defaults).
_OUT_REQUIRED = {
    "contract_id": "c0001",
    "contract_no": "JF-20260709-ABCD",
    "contract_name": "施工合同A",
    "contract_type": "client",
    "party_name": "甲方公司",
    "status": "signed",
    "created_at": "2026-07-09T00:00:00+00:00",
    "updated_at": "2026-07-09T00:00:00+00:00",
}


def _full_stub():
    """A contract-like object exposing every attribute _contract_to_dict reads."""
    return types.SimpleNamespace(
        contract_id="c0001",
        contract_no="JF-20260709-ABCD",
        contract_name="施工合同A",
        contract_type="client",
        party_name="甲方公司",
        party_contact="张三",
        party_phone="13800000000",
        party_address="北京市",
        project_id="p0001",
        project_name="项目一",
        status="signed",
        sign_date="2026-07-01",
        amount_with_tax=113000.0,
        amount_without_tax=100000.0,
        invoice_amount=88888.88,
        invoice_date="2026-07-05",
        paid_amount=50000.0,
        work_start_date="2026-07-10",
        work_end_date="2026-12-31",
        payment_nodes=[],
        attachments=[],
        remarks="备注",
        special_terms="特殊条款",
        penalty_clause="违约条款",
        created_at="2026-07-09T00:00:00+00:00",
        updated_at="2026-07-09T00:00:00+00:00",
    )


# --- Criterion 1: schemas expose invoice_amount + invoice_date as optional ---

@pytest.mark.parametrize("model", [ContractCreate, ContractUpdate, ContractOut])
@pytest.mark.parametrize("field", ["invoice_amount", "invoice_date"])
def test_invoice_fields_declared_and_optional(model, field):
    """Each schema declares invoice_* fields, and they are not required."""
    assert field in model.model_fields, f"{model.__name__} missing {field}"
    assert model.model_fields[field].is_required() is False, (
        f"{model.__name__}.{field} must be optional"
    )


def test_create_accepts_invoice_values_with_correct_types():
    """ContractCreate carries invoice_amount (float) and invoice_date (str)."""
    c = ContractCreate(**_CREATE_REQUIRED, invoice_amount=12345.67, invoice_date="2026-07-09")
    assert c.invoice_amount == 12345.67
    assert isinstance(c.invoice_amount, float)
    assert c.invoice_date == "2026-07-09"


def test_out_and_update_carry_invoice_values():
    """ContractOut and ContractUpdate round-trip invoice values too."""
    out = ContractOut(**_OUT_REQUIRED, invoice_amount=777.0, invoice_date="2026-08-01")
    assert out.invoice_amount == 777.0
    assert out.invoice_date == "2026-08-01"

    upd = ContractUpdate(invoice_amount=1.5, invoice_date="2026-09-01")
    assert upd.invoice_amount == 1.5
    assert upd.invoice_date == "2026-09-01"


def test_invoice_amount_rejects_non_numeric():
    """invoice_amount is typed as a number, not a free-form string."""
    with pytest.raises(ValidationError):
        ContractCreate(**_CREATE_REQUIRED, invoice_amount="not-a-number")


# --- Criterion 2: _contract_to_dict returns invoice_amount + invoice_date ---

def test_contract_to_dict_emits_invoice_fields():
    """_contract_to_dict surfaces both invoice fields with the source values."""
    d = _contract_to_dict(_full_stub())
    assert "invoice_amount" in d
    assert "invoice_date" in d
    assert d["invoice_amount"] == 88888.88
    assert d["invoice_date"] == "2026-07-05"


def test_contract_to_dict_preserves_none_invoice_fields():
    """None invoice values pass through unchanged (not coerced to 0/"")."""
    stub = _full_stub()
    stub.invoice_amount = None
    stub.invoice_date = None
    d = _contract_to_dict(stub)
    assert d["invoice_amount"] is None
    assert d["invoice_date"] is None


def test_contract_to_dict_does_not_confuse_invoice_amount_with_other_amounts():
    """invoice_amount is distinct from amount_with/without_tax and paid_amount."""
    d = _contract_to_dict(_full_stub())
    assert d["invoice_amount"] == 88888.88
    assert d["amount_with_tax"] == 113000.0
    assert d["amount_without_tax"] == 100000.0
    assert d["paid_amount"] == 50000.0


# --- Criterion 3: omitting invoice fields is backward compatible -------------

def test_create_without_invoice_fields_defaults_to_none():
    """Legacy payloads (no invoice fields) still build; fields default to None."""
    c = ContractCreate(**_CREATE_REQUIRED)
    assert c.invoice_amount is None
    assert c.invoice_date is None


def test_update_without_invoice_fields_defaults_to_none():
    """ContractUpdate with no fields set leaves invoice fields None (safe partial update)."""
    upd = ContractUpdate()
    assert upd.invoice_amount is None
    assert upd.invoice_date is None
    # exclude_none is how the router applies updates; unset invoice fields must not leak.
    dumped = upd.model_dump(exclude_none=True)
    assert "invoice_amount" not in dumped
    assert "invoice_date" not in dumped
