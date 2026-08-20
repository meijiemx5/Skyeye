"""Project completeness checklist + todo aggregation.

HZY 2026-08-20: 一个项目的完整组成部分包含预算、报价、合同（甲方合同、采购合同）、
验收资料、报销、工费；某项迟迟未完成就提醒对应负责人。

Pure functions over plain dicts (the routers pass their existing `_to_dict`
output), so every rule is unit-testable without AWS.
"""
from datetime import date, datetime, timedelta

from .invoice_calc import AMOUNT_TOLERANCE

# --- statuses & severities --------------------------------------------------

OK = "ok"              # 已完成
MISSING = "missing"    # 未完成，未到期
OVERDUE = "overdue"    # 未完成，已逾期
WARNING = "warning"    # 完成了但有风险（如预算超支）

HIGH, MEDIUM, LOW = "high", "medium", "low"
SEVERITY_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}

# 各项相对基准日的宽限天数
GRACE_DAYS = {
    "budget": 7,             # 开工后 7 天内应有预算
    "quote": 7,              # 开工后 7 天内应有报价
    "client_contract": 14,   # 开工后 14 天内应签甲方合同
    "supplier_contract": 30,
    "labor_contract": 30,
    "invoice": 30,           # 计划完工后 30 天内应开完票
}

# 在途报销停留超过这个天数就算逾期，提醒当前处理人
REIMBURSE_STALE_DAYS = 7

CHECKLIST_KEYS = (
    "budget",
    "quote",
    "client_contract",
    "supplier_contract",
    "labor_contract",
    "acceptance",
    "invoice",
    "reimbursement",
)


# --- helpers ----------------------------------------------------------------

def _as_date(value) -> date | None:
    """Parse 'YYYY-MM-DD' / ISO timestamp / date; None when unusable."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _today(today=None) -> date:
    return _as_date(today) or date.today()


def _due(basis: date | None, grace_days: int = 0) -> date | None:
    return basis + timedelta(days=grace_days) if basis else None


def _amount(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _item(
    key: str,
    label: str,
    done: bool,
    *,
    today: date,
    due_date: date | None = None,
    done_message: str = "",
    todo_message: str = "",
    owner_role: str = "project_manager",
    owner_id: str | None = None,
    owner_name: str | None = None,
    applicable: bool = True,
    not_applicable_message: str = "",
) -> dict:
    """Build one checklist entry, deriving status/severity from `done` and `due_date`."""
    if not applicable:
        status, severity, message, days_overdue = OK, LOW, not_applicable_message, 0
    elif done:
        status, severity, message, days_overdue = OK, LOW, done_message, 0
    elif due_date and today > due_date:
        days_overdue = (today - due_date).days
        status, severity = OVERDUE, HIGH
        message = f"{todo_message}（已逾期 {days_overdue} 天）"
    else:
        status, severity, days_overdue = MISSING, MEDIUM, 0
        message = todo_message
        if due_date:
            message = f"{todo_message}（应于 {due_date.isoformat()} 前完成）"

    return {
        "key": key,
        "label": label,
        "status": status,
        "severity": severity,
        "message": message,
        "due_date": due_date.isoformat() if due_date else None,
        "days_overdue": days_overdue,
        "owner_role": owner_role,
        "owner_id": owner_id,
        "owner_name": owner_name,
        "applicable": applicable,
    }


# --- checklist --------------------------------------------------------------

def evaluate_project_checklist(
    project: dict,
    *,
    contracts=(),
    acceptances=(),
    reimbursements=(),
    stock_records=(),
    invoice_items=(),
    material_cost: float = 0.0,
    used_amount: float = 0.0,
    today=None,
) -> dict:
    """Evaluate the 8 completeness rules for one project.

    All collections must already be filtered to this project.
    """
    now = _today(today)
    pm_id = project.get("project_manager_id")
    pm_name = project.get("project_manager_name")
    start = _as_date(project.get("start_date")) or _as_date(project.get("created_at"))
    end = _as_date(project.get("end_date"))

    client_contracts = [c for c in contracts if c.get("contract_type") == "client"]
    supplier_contracts = [c for c in contracts if c.get("contract_type") == "supplier"]
    labor_contracts = [c for c in contracts if c.get("contract_type") == "construction"]
    signed_client = [c for c in client_contracts if c.get("status") in ("signed", "fulfilled")]
    client_amount = sum(_amount(c.get("amount_with_tax")) for c in client_contracts)

    budget_amount = _amount(project.get("budget_amount"))
    quote_amount = _amount(project.get("quote_amount"))

    items: list[dict] = []

    # 1. 预算 — 缺失要催，超支/接近要预警
    budget_item = _item(
        "budget", "预算", budget_amount > 0,
        today=now, due_date=_due(start, GRACE_DAYS["budget"]),
        done_message=f"预算 ¥{budget_amount:,.2f}",
        todo_message="未填写项目预算",
        owner_id=pm_id, owner_name=pm_name,
    )
    if budget_amount > 0 and used_amount > budget_amount:
        over = used_amount - budget_amount
        budget_item.update({
            "status": WARNING, "severity": HIGH,
            "message": f"成本已超预算 ¥{over:,.2f}（预算 ¥{budget_amount:,.2f} / 已发生 ¥{used_amount:,.2f}）",
        })
    elif budget_amount > 0 and used_amount >= budget_amount * 0.9:
        budget_item.update({
            "status": WARNING, "severity": MEDIUM,
            "message": f"成本已用到预算的 {used_amount / budget_amount * 100:.1f}%",
        })
    items.append(budget_item)

    # 2. 报价
    items.append(_item(
        "quote", "报价", quote_amount > 0,
        today=now, due_date=_due(start, GRACE_DAYS["quote"]),
        done_message=f"报价 ¥{quote_amount:,.2f}",
        todo_message="未填写项目报价",
        owner_id=pm_id, owner_name=pm_name,
    ))

    # 3. 甲方合同
    items.append(_item(
        "client_contract", "甲方合同", bool(signed_client),
        today=now, due_date=_due(start, GRACE_DAYS["client_contract"]),
        done_message=f"已签甲方合同 {len(signed_client)} 份，合计 ¥{client_amount:,.2f}",
        todo_message="未签订甲方合同" if not client_contracts else "甲方合同尚未签订（仍为待签订状态）",
        owner_id=pm_id, owner_name=pm_name,
    ))

    # 4. 采购合同 — 只有产生了材料成本才必需
    items.append(_item(
        "supplier_contract", "采购合同", bool(supplier_contracts),
        today=now, due_date=_due(start, GRACE_DAYS["supplier_contract"]),
        done_message=f"已有采购合同 {len(supplier_contracts)} 份",
        todo_message=f"项目已发生材料成本 ¥{material_cost:,.2f}，但没有采购合同",
        owner_role="procurement",
        applicable=material_cost > 0,
        not_applicable_message="项目暂无材料采购",
    ))

    # 5. 工费（施工合同）
    items.append(_item(
        "labor_contract", "工费", bool(labor_contracts),
        today=now, due_date=_due(start, GRACE_DAYS["labor_contract"]),
        done_message=f"已有施工合同 {len(labor_contracts)} 份",
        todo_message="未登记工费（施工合同）",
        owner_id=pm_id, owner_name=pm_name,
    ))

    # 6. 验收资料 — 有记录还不够，得真的传了资料
    doc_fields = ("basic_docs", "engineering_docs", "compliance_docs",
                  "result_docs", "other_docs", "rectification_docs")
    doc_count = sum(len(a.get(f) or []) for a in acceptances for f in doc_fields)
    needs_rectification = [a for a in acceptances if a.get("status") == "needs_rectification"]
    acceptance_item = _item(
        "acceptance", "验收资料", doc_count > 0,
        today=now, due_date=end,
        done_message=f"已上传验收资料 {doc_count} 份",
        todo_message="验收资料未上传" if acceptances else "尚未创建验收记录，验收资料未上传",
        owner_id=pm_id, owner_name=pm_name,
    )
    if needs_rectification:
        acceptance_item.update({
            "status": WARNING if acceptance_item["status"] == OK else acceptance_item["status"],
            "severity": HIGH,
            "message": f"有 {len(needs_rectification)} 条验收需整改",
        })
    items.append(acceptance_item)

    # 7. 发票 — 分批次开票，看的是未开票余额
    invoiced = round(sum(_amount(i.get("amount_with_tax")) for i in invoice_items), 2)
    remaining = round(client_amount - invoiced, 2)
    items.append(_item(
        "invoice", "发票", client_amount > 0 and remaining <= AMOUNT_TOLERANCE,
        today=now, due_date=_due(end, GRACE_DAYS["invoice"]),
        done_message=f"已开票 ¥{invoiced:,.2f}，已开完",
        todo_message=f"未开票余额 ¥{remaining:,.2f}（合同 ¥{client_amount:,.2f} / 已开 ¥{invoiced:,.2f}）",
        owner_role="finance",
        applicable=client_amount > 0,
        not_applicable_message="暂无甲方合同金额，无需开票",
    ))

    # 8. 报销 — 在途报销卡太久要催当前处理人
    stale = [r for r in reimbursements if _reimburse_pending_days(r, now) > REIMBURSE_STALE_DAYS]
    in_flight = [r for r in reimbursements if _is_in_flight(r)]
    items.append(_item(
        "reimbursement", "报销", not stale,
        today=now, due_date=None,
        done_message=(f"在途报销 {len(in_flight)} 笔，均在处理时限内" if in_flight else "无在途报销"),
        todo_message=f"有 {len(stale)} 笔报销停留超过 {REIMBURSE_STALE_DAYS} 天未处理",
        owner_role="finance",
    ))
    if stale:
        items[-1].update({"status": OVERDUE, "severity": HIGH,
                          "days_overdue": max(_reimburse_pending_days(r, now) for r in stale)})

    applicable = [i for i in items if i["applicable"]]
    done = [i for i in applicable if i["status"] == OK]
    return {
        "project_id": project.get("project_id"),
        "project_name": project.get("project_name"),
        "project_status": project.get("status"),
        "project_manager_id": pm_id,
        "project_manager_name": pm_name,
        "items": items,
        "health_score": round(len(done) / len(applicable) * 100, 1) if applicable else 100.0,
        "counts": {
            "total": len(applicable),
            "ok": len(done),
            "missing": len([i for i in applicable if i["status"] == MISSING]),
            "overdue": len([i for i in applicable if i["status"] == OVERDUE]),
            "warning": len([i for i in applicable if i["status"] == WARNING]),
        },
    }


def _is_in_flight(reimbursement: dict) -> bool:
    return reimbursement.get("status") not in ("paid", "rejected")


def _reimburse_pending_days(reimbursement: dict, today: date) -> int:
    """Days the reimbursement has sat in its current status (0 if settled)."""
    if not _is_in_flight(reimbursement):
        return 0
    since = _as_date(reimbursement.get("updated_at")) or _as_date(reimbursement.get("created_at"))
    return (today - since).days if since else 0


# --- todos ------------------------------------------------------------------

def _todo(todo_id, todo_type, title, detail, severity, *, link="/", project_id=None,
          project_name=None, due_date=None, days_pending=0) -> dict:
    return {
        "todo_id": todo_id,
        "type": todo_type,
        "title": title,
        "detail": detail,
        "severity": severity,
        "link": link,
        "project_id": project_id,
        "project_name": project_name,
        "due_date": due_date,
        "days_pending": days_pending,
    }


def _owns_checklist_item(item: dict, user: dict) -> bool:
    """Whether this checklist item lands on `user`'s desk."""
    role = user.get("role")
    if role == "admin":
        return True
    if item.get("owner_role") != role:
        return False
    owner_id = item.get("owner_id")
    return owner_id is None or owner_id == user.get("user_id")


def todos_from_checklists(checklists, user: dict) -> list[dict]:
    """未完成的项目清单项 → 待办（只给该项的负责人和管理员）。"""
    todos = []
    for checklist in checklists:
        for item in checklist["items"]:
            if item["status"] == OK or not item["applicable"]:
                continue
            if not _owns_checklist_item(item, user):
                continue
            todos.append(_todo(
                f"checklist:{checklist['project_id']}:{item['key']}",
                "project_checklist",
                f"{checklist['project_name']} · {item['label']}未完成",
                item["message"],
                item["severity"],
                link=f"/projects/{checklist['project_id']}",
                project_id=checklist["project_id"],
                project_name=checklist["project_name"],
                due_date=item["due_date"],
                days_pending=item["days_overdue"],
            ))
    return todos


# 报销在途状态 → (待办标题, 负责角色)
REIMBURSE_TODO_ROLES = {
    "pending_review": ("待主管审核", ("admin", "project_manager")),
    "manager_approved": ("待确认项目收款", ("admin", "finance")),
    "receipt_confirmed": ("待创建单据", ("admin", "finance")),
    "document_created": ("待财务审核", ("admin", "finance")),
    "finance_approved": ("待生成凭证", ("admin", "finance")),
    "voucher_generated": ("待付款", ("admin", "finance")),
}


def todos_from_reimbursements(reimbursements, user: dict, today=None) -> list[dict]:
    """在途报销 → 当前处理人的待办；被驳回的回到申请人手上。"""
    now = _today(today)
    role, uid = user.get("role"), user.get("user_id")
    todos = []
    for r in reimbursements:
        status = r.get("status")
        days = _reimburse_pending_days(r, now)
        amount = _amount(r.get("amount_with_tax"))

        if status == "rejected":
            if r.get("applicant_id") != uid:
                continue
            todos.append(_todo(
                f"reimburse:{r.get('reimburse_id')}", "reimbursement_rejected",
                f"报销被驳回待修改 · ¥{amount:,.2f}",
                r.get("description") or "", MEDIUM,
                link="/reimbursements", project_id=r.get("project_id"),
                project_name=r.get("project_name"), days_pending=days,
            ))
            continue

        entry = REIMBURSE_TODO_ROLES.get(status)
        if not entry:
            continue
        title, roles = entry
        if role not in roles:
            continue
        todos.append(_todo(
            f"reimburse:{r.get('reimburse_id')}", "reimbursement",
            f"{title} · {r.get('applicant_name') or ''} ¥{amount:,.2f}",
            f"{r.get('project_name') or '未关联项目'}｜{r.get('description') or ''}"
            + (f"（已停留 {days} 天）" if days > REIMBURSE_STALE_DAYS else ""),
            HIGH if days > REIMBURSE_STALE_DAYS else MEDIUM,
            link="/reimbursements", project_id=r.get("project_id"),
            project_name=r.get("project_name"), days_pending=days,
        ))
    return todos


def todos_from_acceptances(acceptances, user: dict) -> list[dict]:
    """需整改的验收 → 项目负责人。"""
    if user.get("role") not in ("admin", "project_manager"):
        return []
    return [
        _todo(
            f"acceptance:{a.get('acceptance_id')}", "acceptance_rectification",
            f"{a.get('project_name') or ''} 验收需整改",
            a.get("rectification_requirements") or "请按整改要求补充材料后重新提交验收",
            HIGH, link="/acceptances", project_id=a.get("project_id"),
            project_name=a.get("project_name"), due_date=a.get("rectification_deadline"),
        )
        for a in acceptances
        if a.get("status") == "needs_rectification"
    ]


def todos_from_stock(materials, user: dict) -> list[dict]:
    """库存缺货/低于阈值 → 采购、仓库。"""
    if user.get("role") not in ("admin", "procurement", "warehouse"):
        return []
    todos = []
    for m in materials:
        status = m.get("stock_status")
        if status not in ("warning", "out_of_stock"):
            continue
        out_of_stock = status == "out_of_stock"
        todos.append(_todo(
            f"stock:{m.get('material_id')}", "stock_warning",
            f"{'缺货' if out_of_stock else '库存预警'} · {m.get('material_name') or ''}",
            f"当前库存 {m.get('stock_quantity') or 0} {m.get('unit') or ''}"
            + (f"，低于阈值 {m.get('min_stock_threshold')}" if m.get("min_stock_threshold") else ""),
            HIGH if out_of_stock else MEDIUM,
            link="/inventory",
        ))
    return todos


def sort_todos(todos) -> list[dict]:
    """Most urgent first: severity, then how long it has been waiting."""
    return sorted(
        todos,
        key=lambda t: (SEVERITY_ORDER.get(t["severity"], 9), -(t.get("days_pending") or 0), t["title"]),
    )


def summarize_todos(todos) -> dict:
    return {
        "total": len(todos),
        "high": len([t for t in todos if t["severity"] == HIGH]),
        "medium": len([t for t in todos if t["severity"] == MEDIUM]),
        "low": len([t for t in todos if t["severity"] == LOW]),
        "by_type": {
            t_type: len([t for t in todos if t["type"] == t_type])
            for t_type in sorted({t["type"] for t in todos})
        },
    }
