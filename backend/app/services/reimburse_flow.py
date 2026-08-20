"""Reimbursement workflow state machine.

Chain (HZY 2026-08-20): 提交报销 → 项目收款 → 创建单据 → 财务审核 → 凭证生成 → 付款

Pure logic only — no DynamoDB, no FastAPI — so the routers stay thin and the
transitions are unit-testable. Routers translate `TransitionError` into HTTP 400.
"""
import uuid
from datetime import datetime, timezone

# --- statuses ---------------------------------------------------------------

PENDING_REVIEW = "pending_review"
MANAGER_APPROVED = "manager_approved"
RECEIPT_CONFIRMED = "receipt_confirmed"
DOCUMENT_CREATED = "document_created"
FINANCE_APPROVED = "finance_approved"
VOUCHER_GENERATED = "voucher_generated"
PAID = "paid"
REJECTED = "rejected"

# Order used for progress display; `rejected` is off-chain.
STATUS_ORDER = (
    PENDING_REVIEW,
    MANAGER_APPROVED,
    RECEIPT_CONFIRMED,
    DOCUMENT_CREATED,
    FINANCE_APPROVED,
    VOUCHER_GENERATED,
    PAID,
)

STATUS_LABELS = {
    PENDING_REVIEW: "待主管审核",
    MANAGER_APPROVED: "主管已审",
    RECEIPT_CONFIRMED: "项目已收款",
    DOCUMENT_CREATED: "单据已创建",
    FINANCE_APPROVED: "财务已审",
    VOUCHER_GENERATED: "凭证已生成",
    PAID: "已付款",
    REJECTED: "已驳回",
}

# Statuses whose reimbursement the applicant may still edit.
EDITABLE_STATUSES = (PENDING_REVIEW, REJECTED)

# Statuses that count as "in flight" for the todo/alert engine.
IN_FLIGHT_STATUSES = tuple(s for s in STATUS_ORDER if s != PAID)


# --- steps ------------------------------------------------------------------

AUDIT_MANAGER = "audit_manager"
CONFIRM_RECEIPT = "confirm_receipt"
CREATE_DOCUMENT = "create_document"
AUDIT_FINANCE = "audit_finance"
GENERATE_VOUCHER = "generate_voucher"
PAY = "pay"

# from_statuses: every status this step may start from.
# Legacy records sitting on an older status stay on the chain — they simply have
# to perform the newly inserted steps, nothing gets stranded.
STEPS = {
    AUDIT_MANAGER: {
        "label": "主管审核",
        "from_statuses": (PENDING_REVIEW,),
        "to_status": MANAGER_APPROVED,
        "permission": "reimburse:audit_manager",
        "audit_level": "manager",
    },
    CONFIRM_RECEIPT: {
        "label": "项目收款确认",
        "from_statuses": (MANAGER_APPROVED,),
        "to_status": RECEIPT_CONFIRMED,
        "permission": "reimburse:receipt",
        "audit_level": "receipt",
    },
    CREATE_DOCUMENT: {
        "label": "创建单据",
        "from_statuses": (RECEIPT_CONFIRMED,),
        "to_status": DOCUMENT_CREATED,
        "permission": "reimburse:document",
        "audit_level": "document",
    },
    AUDIT_FINANCE: {
        "label": "财务审核",
        "from_statuses": (DOCUMENT_CREATED,),
        "to_status": FINANCE_APPROVED,
        "permission": "reimburse:audit_finance",
        "audit_level": "finance",
    },
    GENERATE_VOUCHER: {
        "label": "凭证生成",
        "from_statuses": (FINANCE_APPROVED,),
        "to_status": VOUCHER_GENERATED,
        "permission": "reimburse:voucher",
        "audit_level": "voucher",
    },
    PAY: {
        "label": "付款",
        "from_statuses": (VOUCHER_GENERATED,),
        "to_status": PAID,
        "permission": "reimburse:pay",
        "audit_level": "payment",
    },
}

# Steps that are a review decision (may end in rejection).
REVIEW_STEPS = (AUDIT_MANAGER, AUDIT_FINANCE)


class TransitionError(Exception):
    """Raised when a workflow step is not allowed from the current status."""


def step_label(step: str) -> str:
    return STEPS.get(step, {}).get("label", step)


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def next_step(status: str) -> str | None:
    """The step expected next from `status` (None for terminal statuses)."""
    for step, spec in STEPS.items():
        if status in spec["from_statuses"]:
            return step
    return None


def next_step_label(status: str) -> str | None:
    step = next_step(status)
    return step_label(step) if step else None


def assert_can(step: str, current_status: str) -> dict:
    """Validate `step` against `current_status`; return the step spec.

    Raises TransitionError with a message aimed at the end user.
    """
    spec = STEPS.get(step)
    if spec is None:
        raise TransitionError(f"未知的操作: {step}")
    if current_status in spec["from_statuses"]:
        return spec
    if current_status == REJECTED:
        raise TransitionError("报销已驳回，需申请人修改后重新提交")
    if current_status == PAID:
        raise TransitionError("报销已付款，不能再操作")

    expected = next_step_label(current_status)
    detail = f"当前状态为「{status_label(current_status)}」，不能执行「{spec['label']}」"
    if expected:
        detail += f"，下一步应为「{expected}」"
    raise TransitionError(detail)


def apply_step(step: str, current_status: str, action: str = "approved") -> str:
    """Resulting status after `step`. `action="rejected"` only valid on review steps."""
    spec = assert_can(step, current_status)
    if action == "rejected":
        if step not in REVIEW_STEPS:
            raise TransitionError(f"「{spec['label']}」不支持驳回操作")
        return REJECTED
    return spec["to_status"]


def audit_step_for_status(current_status: str) -> str:
    """Which audit step applies at `current_status` (manager vs finance)."""
    if current_status in STEPS[AUDIT_MANAGER]["from_statuses"]:
        return AUDIT_MANAGER
    if current_status in STEPS[AUDIT_FINANCE]["from_statuses"]:
        return AUDIT_FINANCE
    expected = next_step_label(current_status)
    detail = f"当前状态为「{status_label(current_status)}」，无需审核"
    if expected:
        detail += f"，下一步应为「{expected}」"
    raise TransitionError(detail)


def is_editable(status: str) -> bool:
    return status in EDITABLE_STATUSES


def progress_index(status: str) -> int:
    """0-based position on the chain; -1 for rejected/unknown."""
    try:
        return STATUS_ORDER.index(status)
    except ValueError:
        return -1


# --- document / voucher numbering ------------------------------------------

def _serial(prefix: str, today: str | None = None) -> str:
    date_str = today or datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}-{date_str}-{str(uuid.uuid4())[:4].upper()}"


def generate_document_no(today: str | None = None) -> str:
    """报销单据号: BX-YYYYMMDD-XXXX"""
    return _serial("BX", today)


def generate_voucher_no(today: str | None = None) -> str:
    """会计凭证号: PZ-YYYYMMDD-XXXX"""
    return _serial("PZ", today)
