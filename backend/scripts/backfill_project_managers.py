#!/usr/bin/env python3
"""把存量项目的「项目负责人」文本回填成系统账号 (project_manager_id)。

背景：项目负责人原本是手填文本，只有 project_manager_name 没有 project_manager_id。
预警与待办是按账号 id 派发的，所以没有 id 的项目，负责人本人收不到任何提醒。

按 display_name 精确匹配启用账号；匹配不上的一律不动，只报告出来人工处理
（同名、用了小名、账号还没建等情况，猜错了比不动更糟）。

用法（默认只演练，不写库）：
    cd backend
    source .venv/bin/activate
    AWS_PROFILE=skyeye AWS_REGION=cn-northwest-1 DYNAMODB_TABLE_NAME=skyeye-dev \\
        python scripts/backfill_project_managers.py

确认无误后再真正写库：
    ... python scripts/backfill_project_managers.py --apply
"""
import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.project import ProjectModel  # noqa: E402
from app.models.user import UserModel  # noqa: E402


def load_users() -> dict[str, list[UserModel]]:
    """display_name -> 启用账号列表（列表是为了识别同名）。"""
    by_name: dict[str, list[UserModel]] = {}
    for user in UserModel.scan(filter_condition=UserModel.entity_type == "user"):
        if not user.is_active:
            continue
        by_name.setdefault((user.display_name or "").strip(), []).append(user)
    return by_name


def main() -> int:
    parser = argparse.ArgumentParser(description="回填项目负责人账号")
    parser.add_argument("--apply", action="store_true",
                        help="真正写入 DynamoDB；不带这个参数只演练")
    args = parser.parse_args()

    table = os.getenv("DYNAMODB_TABLE_NAME", "skyeye-dev")
    region = os.getenv("AWS_REGION", "us-east-1")
    print(f"表: {table} | 区域: {region} | 模式: {'写入' if args.apply else '演练(不写库)'}")
    print("=" * 70)

    users = load_users()
    projects = list(ProjectModel.scan(filter_condition=ProjectModel.entity_type == "project"))

    matched, ambiguous, unmatched, already, empty = [], [], [], [], []
    for project in projects:
        name = (project.project_manager_name or "").strip()
        if project.project_manager_id:
            already.append(project)
            continue
        if not name:
            empty.append(project)
            continue
        candidates = users.get(name, [])
        if len(candidates) == 1:
            matched.append((project, candidates[0]))
        elif len(candidates) > 1:
            ambiguous.append((project, candidates))
        else:
            unmatched.append(project)

    print(f"项目总数: {len(projects)}")
    print(f"  已关联账号，跳过:      {len(already)}")
    print(f"  负责人为空，跳过:      {len(empty)}")
    print(f"  可回填(唯一匹配):      {len(matched)}")
    print(f"  同名多账号，需人工:    {len(ambiguous)}")
    print(f"  找不到账号，需人工:    {len(unmatched)}")

    if matched:
        print("\n可回填：")
        for project, user in matched:
            print(f"  {project.project_id}  {project.project_name[:24]:24} "
                  f"「{project.project_manager_name}」 → {user.user_id} ({user.username}/{user.role})")

    if ambiguous:
        print("\n同名多账号（未处理，请在界面上手动指派）：")
        for project, candidates in ambiguous:
            ids = ", ".join(f"{u.user_id}({u.username})" for u in candidates)
            print(f"  {project.project_id}  {project.project_name[:24]:24} "
                  f"「{project.project_manager_name}」 → {ids}")

    if unmatched:
        print("\n找不到对应账号（未处理，先建账号或在界面上指派）：")
        for project in unmatched:
            print(f"  {project.project_id}  {project.project_name[:24]:24} "
                  f"「{project.project_manager_name}」")

    if empty:
        print("\n负责人为空（未处理，需要在界面上指派）：")
        for project in empty:
            print(f"  {project.project_id}  {project.project_name[:24]}")

    if not args.apply:
        print("\n演练结束，未写库。确认无误后加 --apply 执行。")
        return 0

    if not matched:
        print("\n没有可回填的项目，未写库。")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    for project, user in matched:
        project.project_manager_id = user.user_id
        project.project_manager_name = user.display_name  # 以账号档案为准
        project.updated_at = now
        project.save()
        print(f"  ✅ {project.project_id} → {user.user_id} ({user.display_name})")

    print(f"\n完成：回填 {len(matched)} 个项目。"
          f"仍需人工处理 {len(ambiguous) + len(unmatched) + len(empty)} 个。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
