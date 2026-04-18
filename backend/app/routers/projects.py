"""Project router."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from pynamodb.exceptions import DoesNotExist
from typing import Optional

from ..models.project import ProjectModel
from ..schemas.project import ProjectCreate, ProjectUpdate, ProjectOut
from ..schemas.common import APIResponse
from ..utils.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/projects", tags=["项目管理"])


@router.get("")
def list_projects(
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """List projects."""
    results = list(ProjectModel.scan(filter_condition=ProjectModel.entity_type == "project"))
    
    # Filter in memory for small dataset
    if status:
        results = [r for r in results if r.status == status]
    if keyword:
        results = [r for r in results if keyword in (r.project_name or "") or keyword in (r.client_name or "")]
    
    # Role-based filtering
    if current_user["role"] == "project_manager":
        results = [r for r in results if r.project_manager_id == current_user["user_id"]]
    
    data = []
    for p in results:
        data.append({
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
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })
    
    return APIResponse(data=data, total=len(data))


@router.get("/{project_id}")
def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get project detail."""
    try:
        p = ProjectModel.get(ProjectModel.make_pk(project_id), ProjectModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    return APIResponse(data={
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
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    })


@router.post("")
def create_project(req: ProjectCreate, current_user: dict = Depends(require_roles("admin", "project_manager"))):
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
    project.created_at = now
    project.updated_at = now
    project.created_by = current_user["user_id"]
    project.save()
    
    return APIResponse(message="项目创建成功", data={"project_id": project_id})


@router.put("/{project_id}")
def update_project(project_id: str, req: ProjectUpdate, current_user: dict = Depends(require_roles("admin", "project_manager"))):
    """Update project."""
    try:
        project = ProjectModel.get(ProjectModel.make_pk(project_id), ProjectModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    
    if req.status:
        project.GSI1PK = ProjectModel.make_gsi1pk(req.status)
    
    project.updated_at = datetime.now(timezone.utc).isoformat()
    project.updated_by = current_user["user_id"]
    project.save()
    
    return APIResponse(message="项目更新成功")


@router.delete("/{project_id}")
def delete_project(project_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete project."""
    try:
        project = ProjectModel.get(ProjectModel.make_pk(project_id), ProjectModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    project.delete()
    return APIResponse(message="项目删除成功")
