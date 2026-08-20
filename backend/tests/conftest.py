"""In-memory stand-in for DynamoDB so the routers can be tested without AWS.

PynamoDB's save/get/scan/query are replaced on each concrete model class with a
dict-backed store. `filter_condition` / `range_key_condition` are ignored on
purpose — every call site filters by `entity_type`, which maps 1:1 to a model
class, so filtering by class is equivalent and keeps the fake honest.
"""
import pytest
from fastapi.testclient import TestClient
from pynamodb.exceptions import DoesNotExist

from app.main import app
from app.models.acceptance import AcceptanceDocModel
from app.models.audit_log import AuditLogModel
from app.models.contract import ContractModel
from app.models.inventory import MaterialModel, StockRecordModel
from app.models.invoice import InvoiceBatchModel, InvoiceRecordModel
from app.models.project import ProjectModel
from app.models.reimburse_category import ReimburseCategoryModel
from app.models.reimbursement import ReimbursementModel
from app.models.user import UserModel
from app.utils.auth import get_current_user

MODELS = [
    ProjectModel, ContractModel, ReimbursementModel, ReimburseCategoryModel,
    AcceptanceDocModel, MaterialModel, StockRecordModel,
    InvoiceBatchModel, InvoiceRecordModel, AuditLogModel, UserModel,
]

USERS = {
    "admin": {"user_id": "u-admin", "username": "admin", "display_name": "管理员", "role": "admin"},
    "finance": {"user_id": "u-fin", "username": "fin", "display_name": "财务小王", "role": "finance"},
    "pm": {"user_id": "u-pm", "username": "pm", "display_name": "项目张三", "role": "project_manager"},
    "procurement": {"user_id": "u-buy", "username": "buy", "display_name": "采购小李", "role": "procurement"},
    "construction": {"user_id": "u-work", "username": "work", "display_name": "施工小赵", "role": "construction"},
    "warehouse": {"user_id": "u-wh", "username": "wh", "display_name": "仓库老陈", "role": "warehouse"},
}


class FakeStore:
    """(model class, PK, SK) -> model instance."""

    def __init__(self):
        self.items: dict[tuple, object] = {}

    def install(self, monkeypatch):
        store = self

        for model in MODELS:
            def save(self, *args, _model=model, **kwargs):
                store.items[(_model, self.PK, self.SK)] = self

            def delete(self, *args, _model=model, **kwargs):
                store.items.pop((_model, self.PK, self.SK), None)

            def get(cls, hash_key, range_key=None, *args, _model=model, **kwargs):
                found = store.items.get((_model, hash_key, range_key))
                if found is None:
                    raise DoesNotExist(f"{_model.__name__} {hash_key}/{range_key}")
                return found

            def scan(cls, *args, _model=model, **kwargs):
                rows = [v for (m, _pk, _sk), v in store.items.items() if m is _model]
                limit = kwargs.get("limit")
                return iter(rows[:limit] if limit else rows)

            def query(cls, hash_key, *args, _model=model, **kwargs):
                return iter([v for (m, pk, _sk), v in store.items.items()
                             if m is _model and pk == hash_key])

            monkeypatch.setattr(model, "save", save, raising=False)
            monkeypatch.setattr(model, "delete", delete, raising=False)
            monkeypatch.setattr(model, "get", classmethod(get), raising=False)
            monkeypatch.setattr(model, "scan", classmethod(scan), raising=False)
            monkeypatch.setattr(model, "query", classmethod(query), raising=False)

    def all_of(self, model):
        return [v for (m, _pk, _sk), v in self.items.items() if m is model]


@pytest.fixture
def store(monkeypatch):
    fake = FakeStore()
    fake.install(monkeypatch)
    return fake


@pytest.fixture
def as_user():
    """Log the TestClient in as one of USERS; yields a factory returning a client."""
    def _login(role_key: str) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: USERS[role_key]
        return TestClient(app)
    yield _login
    app.dependency_overrides.clear()


@pytest.fixture
def client(as_user):
    """Admin client — the common case."""
    return as_user("admin")


# --- seed helpers -----------------------------------------------------------

def seed_category(store, category_id="cat-material", name="物料采购", parent_id=None,
                  level=1, is_active=True):
    c = ReimburseCategoryModel()
    c.PK = ReimburseCategoryModel.make_pk(category_id)
    c.SK = ReimburseCategoryModel.make_sk()
    c.entity_type = "reimburse_category"
    c.category_id = category_id
    c.name = name
    c.parent_id = parent_id
    c.level = level
    c.is_active = is_active
    c.sort_order = 0
    c.created_at = c.updated_at = "2026-01-01T00:00:00+00:00"
    c.save()
    return c


def seed_project(store, project_id="p1", name="某小区弱电", manager_id="u-pm",
                 budget_amount=None, quote_amount=None, start_date="2026-01-01",
                 end_date="2026-06-30", status="active"):
    p = ProjectModel()
    p.PK = ProjectModel.make_pk(project_id)
    p.SK = ProjectModel.make_sk()
    p.entity_type = "project"
    p.project_id = project_id
    p.project_name = name
    p.project_manager_id = manager_id
    p.project_manager_name = "项目张三"
    p.status = status
    p.start_date = start_date
    p.end_date = end_date
    p.budget_amount = budget_amount
    p.quote_amount = quote_amount
    p.created_at = p.updated_at = "2026-01-01T00:00:00+00:00"
    p.save()
    return p


def seed_material(store, material_id="m1", name="网线", unit_price=50, stock_quantity=100,
                  stock_status="normal", min_stock_threshold=None):
    m = MaterialModel()
    m.PK = MaterialModel.make_pk(material_id)
    m.SK = MaterialModel.make_sk()
    m.entity_type = "material"
    m.material_id = material_id
    m.material_name = name
    m.category = "cable"
    m.unit = "米"
    m.unit_price = unit_price
    m.stock_quantity = stock_quantity
    m.stock_status = stock_status
    m.min_stock_threshold = min_stock_threshold
    m.created_at = m.updated_at = "2026-01-01T00:00:00+00:00"
    m.save()
    return m


def seed_stock_record(store, record_id="s1", material_id="m1", record_type="in",
                      quantity=100, unit_price=50, project_id="p1"):
    r = StockRecordModel()
    r.PK = StockRecordModel.make_pk(material_id)
    r.SK = StockRecordModel.make_sk(record_id)
    r.entity_type = "stock_record"
    r.record_id = record_id
    r.material_id = material_id
    r.material_name = "网线"
    r.record_type = record_type
    r.quantity = quantity
    r.unit_price = unit_price
    r.project_id = project_id
    r.project_name = "某小区弱电"
    r.record_date = "2026-03-01"
    r.created_at = r.updated_at = "2026-03-01T00:00:00+00:00"
    r.save()
    return r


def seed_contract(store, contract_id="c1", project_id="p1", contract_type="client",
                  amount=1000000, status="signed", paid_amount=0):
    c = ContractModel()
    c.PK = ContractModel.make_pk(contract_id)
    c.SK = ContractModel.make_sk()
    c.entity_type = "contract"
    c.contract_id = contract_id
    c.contract_no = f"JF-20260101-{contract_id.upper()}"
    c.contract_name = f"合同{contract_id}"
    c.contract_type = contract_type
    c.party_name = "甲方公司"
    c.project_id = project_id
    c.project_name = "某小区弱电"
    c.status = status
    c.amount_with_tax = amount
    c.paid_amount = paid_amount
    c.created_at = c.updated_at = "2026-01-01T00:00:00+00:00"
    c.save()
    return c
