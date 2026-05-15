"""Reimbursement category management - two-level tree."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pynamodb.exceptions import DoesNotExist

from ..models.reimburse_category import ReimburseCategoryModel
from ..models.reimbursement import ReimbursementModel
from ..schemas.reimburse_category import CategoryCreate, CategoryUpdate
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user, require_roles
from ..services.audit import log_action

router = APIRouter(prefix="/api/reimburse-categories", tags=["报销类型管理"])


def _to_dict(c):
    return {
        "category_id": c.category_id,
        "name": c.name,
        "parent_id": c.parent_id,
        "level": int(c.level or 1),
        "sort_order": int(c.sort_order or 0),
        "is_active": bool(c.is_active),
        "code": c.code,
    }


def _scan_all():
    return list(ReimburseCategoryModel.scan(filter_condition=ReimburseCategoryModel.entity_type == "reimburse_category"))


def _build_tree(categories):
    items = [_to_dict(c) for c in categories]
    items.sort(key=lambda x: (x["sort_order"], x["category_id"]))
    by_id = {it["category_id"]: {**it, "children": []} for it in items}
    roots = []
    for it in items:
        node = by_id[it["category_id"]]
        if it["parent_id"] and it["parent_id"] in by_id:
            by_id[it["parent_id"]]["children"].append(node)
        else:
            roots.append(node)
    return roots


@router.get("")
def list_tree(current_user: dict = Depends(get_current_user)):
    """List categories as a tree."""
    categories = _scan_all()
    return APIResponse(data=_build_tree(categories))


@router.get("/flat")
def list_flat(current_user: dict = Depends(get_current_user)):
    """List categories as a flat array."""
    categories = _scan_all()
    data = [_to_dict(c) for c in categories]
    data.sort(key=lambda x: (x["level"], x["sort_order"], x["category_id"]))
    return APIResponse(data=data, total=len(data))


@router.post("")
def create_category(req: CategoryCreate, current_user: dict = Depends(require_roles("admin"))):
    """Create a category. Two levels max."""
    level = 1
    parent_id = req.parent_id or None
    if parent_id:
        try:
            parent = ReimburseCategoryModel.get(ReimburseCategoryModel.make_pk(parent_id), ReimburseCategoryModel.make_sk())
        except DoesNotExist:
            raise HTTPException(status_code=400, detail="父类不存在")
        if int(parent.level or 1) >= 2:
            raise HTTPException(status_code=400, detail="最多支持两级分类")
        level = 2

    category_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    c = ReimburseCategoryModel()
    c.PK = ReimburseCategoryModel.make_pk(category_id)
    c.SK = ReimburseCategoryModel.make_sk()
    c.GSI1PK = ReimburseCategoryModel.make_gsi1pk(parent_id)
    c.GSI1SK = ReimburseCategoryModel.make_gsi1sk(req.sort_order or 0, category_id)
    c.entity_type = "reimburse_category"
    c.category_id = category_id
    c.name = req.name
    c.parent_id = parent_id
    c.level = level
    c.sort_order = req.sort_order or 0
    c.is_active = True
    c.code = req.code
    c.created_at = now
    c.updated_at = now
    c.created_by = current_user["user_id"]
    c.save()
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "create", "reimburse_category", category_id, f"创建报销类型: {req.name}")
    return APIResponse(message="创建成功", data={"category_id": category_id})


@router.put("/{category_id}")
def update_category(category_id: str, req: CategoryUpdate, current_user: dict = Depends(require_roles("admin"))):
    """Update a category."""
    try:
        c = ReimburseCategoryModel.get(ReimburseCategoryModel.make_pk(category_id), ReimburseCategoryModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="分类不存在")

    update_data = req.model_dump(exclude_none=True)
    for k, v in update_data.items():
        setattr(c, k, v)

    if "sort_order" in update_data:
        c.GSI1SK = ReimburseCategoryModel.make_gsi1sk(c.sort_order or 0, category_id)
    c.updated_at = datetime.now(timezone.utc).isoformat()
    c.updated_by = current_user["user_id"]
    c.save()
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "update", "reimburse_category", category_id, f"更新报销类型: {c.name}")
    return APIResponse(message="更新成功")


@router.delete("/{category_id}")
def delete_category(category_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete a category. Reject if it has children or is referenced by reimbursements."""
    try:
        c = ReimburseCategoryModel.get(ReimburseCategoryModel.make_pk(category_id), ReimburseCategoryModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="分类不存在")

    # Block if has children
    children = [x for x in _scan_all() if x.parent_id == category_id]
    if children:
        raise HTTPException(status_code=400, detail="存在子分类，不能删除")

    # Block if referenced by reimbursements
    refs = list(ReimbursementModel.scan(
        filter_condition=(ReimbursementModel.entity_type == "reimbursement") &
                         (ReimbursementModel.expense_type == category_id),
        limit=1,
    ))
    if refs:
        raise HTTPException(status_code=400, detail="已被报销引用，不能删除")

    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "delete", "reimburse_category", category_id, f"删除报销类型: {c.name}")
    c.delete()
    return APIResponse(message="删除成功")
