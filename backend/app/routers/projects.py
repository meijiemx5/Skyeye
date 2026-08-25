"""Project router.

查看权限: 完整项目列表/详情仅管理员与项目负责人 (`project:list`)；其他角色通过
`GET /api/projects/options` 拿到精简选项，用于报销、出入库、验收的项目下拉框。
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.project import ProjectModel
from ..schemas.project import ProjectCreate, ProjectUpdate
from ..schemas.common import APIResponse
from ..utils.attachments import to_attachment_maps, attachment_dicts
from ..utils.permissions import require_permission
from ..services.audit import log_action

router = APIRouter(prefix="/api/projects", tags=["项目管理"])

# 项目负责人只能看到自己负责的项目
_OWN_PROJECTS_ONLY = ("project_manager",)


def _project_to_dict(p) -> dict:
    return {
        "project_id": p.project_id,
        "project_name": p.project_name,
        "project_manager_id": p.project_manager_id,
        "project_manager_name": p.project_manager_name,
        "client_name": p.client_name,
        "description": p.description,
        "status": p.status,
        "start_date": p.start_date,
        "end_date": p.end_date,
        "actual_end_date": p.actual_end_date,
        "address": p.address,
        "budget_amount": p.budget_amount,
        "quote_amount": p.quote_amount,
        "budget_docs": attachment_dicts(p.budget_docs),
        "quote_docs": attachment_dicts(p.quote_docs),
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def scan_projects(current_user: dict | None = None) -> list:
    """All projects, narrowed to the ones a project manager owns."""
    results = list(ProjectModel.scan(filter_condition=ProjectModel.entity_type == "project"))
    if current_user and current_user.get("role") in _OWN_PROJECTS_ONLY:
        results = [r for r in results if r.project_manager_id == current_user["user_id"]]
    return results


@router.get("")
def list_projects(
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: dict = Depends(require_permission("project:list"))
):
    """List projects (admin / project manager only)."""
    results = scan_projects(current_user)

    # Filter in memory for small dataset
    if status:
        results = [r for r in results if r.status == status]
    if keyword:
        kw = keyword.lower()
        results = [
            r for r in results
            if kw in (r.project_name or "").lower()
            or kw in (r.client_name or "").lower()
            or kw in (r.project_manager_name or "").lower()
            or kw in (r.address or "").lower()
        ]

    data = [_project_to_dict(p) for p in results]
    return APIResponse(data=data, total=len(data))


@router.get("/options")
def list_project_options(current_user: dict = Depends(require_permission("project:options"))):
    """精简项目选项 - 任何登录用户都能用来填项目下拉框（不含金额等敏感字段）。"""
    results = list(ProjectModel.scan(filter_condition=ProjectModel.entity_type == "project"))
    data = [
        {"project_id": p.project_id, "project_name": p.project_name, "status": p.status}
        for p in results
    ]
    data.sort(key=lambda x: x["project_name"] or "")
    return APIResponse(data=data, total=len(data))


@router.get("/{project_id}")
def get_project(project_id: str, current_user: dict = Depends(require_permission("project:list"))):
    """Get project detail."""
    try:
        p = ProjectModel.get(ProjectModel.make_pk(project_id), ProjectModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="项目不存在")

    if (current_user["role"] in _OWN_PROJECTS_ONLY
            and p.project_manager_id != current_user["user_id"]):
        raise HTTPException(status_code=403, detail="只能查看自己负责的项目")

    return APIResponse(data=_project_to_dict(p))


@router.post("")
def create_project(req: ProjectCreate, current_user: dict = Depends(require_permission("project:write"))):
    """Create project."""
    project_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()

    project = ProjectModel()
    project.PK = ProjectModel.make_pk(project_id)
    project.SK = ProjectModel.make_sk()
    project.GSI1PK = ProjectModel.make_gsi1pk("active")
    project.GSI1SK = f"PROJECT#{project_id}"
    project.entity_type = "project"
    project.project_id = project_id
    project.project_name = req.project_name
    project.project_manager_id = req.project_manager_id
    project.project_manager_name = req.project_manager_name
    project.client_name = req.client_name
    project.description = req.description
    project.status = "active"
    project.start_date = req.start_date
    project.end_date = req.end_date
    project.address = req.address
    project.budget_amount = req.budget_amount
    project.quote_amount = req.quote_amount
    project.budget_docs = to_attachment_maps(req.budget_docs)
    project.quote_docs = to_attachment_maps(req.quote_docs)
    project.created_at = now
    project.updated_at = now
    project.created_by = current_user["user_id"]
    project.save()
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "create", "project", project_id, f"创建项目: {req.project_name}")
    return APIResponse(message="项目创建成功", data={"project_id": project_id})


@router.put("/{project_id}")
def update_project(project_id: str, req: ProjectUpdate, current_user: dict = Depends(require_permission("project:write"))):
    """Update project."""
    try:
        project = ProjectModel.get(ProjectModel.make_pk(project_id), ProjectModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="项目不存在")

    update_data = req.model_dump(exclude_none=True, exclude={"budget_docs", "quote_docs"})
    for key, value in update_data.items():
        setattr(project, key, value)

    if req.budget_docs is not None:
        project.budget_docs = to_attachment_maps(req.budget_docs)
    if req.quote_docs is not None:
        project.quote_docs = to_attachment_maps(req.quote_docs)

    if req.status:
        project.GSI1PK = ProjectModel.make_gsi1pk(req.status)

    project.updated_at = datetime.now(timezone.utc).isoformat()
    project.updated_by = current_user["user_id"]
    project.save()
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "update", "project", project_id, f"更新项目: {project.project_name}")
    return APIResponse(message="项目更新成功")


@router.delete("/{project_id}")
def delete_project(project_id: str, current_user: dict = Depends(require_permission("project:delete"))):
    """Delete project."""
    try:
        project = ProjectModel.get(ProjectModel.make_pk(project_id), ProjectModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="项目不存在")

    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "delete", "project", project_id, f"删除项目: {project.project_name}")
    project.delete()
    return APIResponse(message="项目删除成功")
