"""Data scoping helpers shared by routers.

项目负责人只看自己负责的项目及其下属数据，这个"自己的项目集合"被多个 router 用到，
放在一处避免各自 scan 出不一致的范围。
"""
from ..models.project import ProjectModel


def own_project_ids(user_id: str) -> set[str]:
    """Ids of the projects `user_id` is the manager of."""
    return {
        p.project_id
        for p in ProjectModel.scan(filter_condition=ProjectModel.entity_type == "project")
        if p.project_manager_id == user_id
    }
