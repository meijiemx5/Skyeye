"""项目负责人与系统账号的绑定。

预警与待办按账号 id 派发，所以负责人必须是账号而不是一段文本，
否则"提醒对应的负责人"只能提醒到管理员。
"""
import pytest

from app.models.user import UserModel
from tests.conftest import USERS, seed_project


def seed_user(user_id="u-pm", username="pm", display_name="项目张三",
              role="project_manager", is_active=True):
    u = UserModel()
    u.PK = UserModel.make_pk(user_id)
    u.SK = UserModel.make_sk()
    u.entity_type = "user"
    u.user_id = user_id
    u.username = username
    u.display_name = display_name
    u.password_hash = "x:y"
    u.role = role
    u.is_active = is_active
    u.login_fail_count = 0
    u.created_at = u.updated_at = "2026-01-01T00:00:00+00:00"
    u.save()
    return u


@pytest.fixture
def seeded(store):
    seed_user()
    seed_user(user_id="u-pm2", username="pm2", display_name="项目李四")
    seed_user(user_id="u-off", username="off", display_name="已离职", is_active=False)
    return store


# --- 用户选项接口 -----------------------------------------------------------

def test_user_options_available_to_project_manager(seeded, as_user):
    """项目负责人也要能给项目指派负责人，而完整用户管理只有 admin。"""
    pm = as_user("pm")
    assert pm.get("/api/auth/users").status_code == 403
    res = pm.get("/api/auth/users/options")
    assert res.status_code == 200


def test_user_options_hides_disabled_accounts_and_sensitive_fields(seeded, client):
    data = client.get("/api/auth/users/options").json()["data"]
    assert "u-off" not in [u["user_id"] for u in data]
    assert set(data[0]) == {"user_id", "username", "display_name", "role"}


@pytest.mark.parametrize("role", ["finance", "procurement", "construction", "warehouse"])
def test_user_options_closed_to_other_roles(seeded, as_user, role):
    assert as_user(role).get("/api/auth/users/options").status_code == 403


# --- 指派负责人 -------------------------------------------------------------

def _create(client, **overrides):
    payload = {"project_name": "某小区弱电", **overrides}
    res = client.post("/api/projects", json=payload)
    assert res.status_code == 200, res.text
    return res.json()["data"]["project_id"]


def test_manager_name_comes_from_the_account_not_the_client(seeded, client):
    """前端乱传显示名也不会写进库 —— 姓名一律取账号档案。"""
    pid = _create(client, project_manager_id="u-pm", project_manager_name="随便乱写")
    project = client.get(f"/api/projects/{pid}").json()["data"]
    assert project["project_manager_id"] == "u-pm"
    assert project["project_manager_name"] == "项目张三"


def test_assigning_an_unknown_account_is_rejected(seeded, client):
    res = client.post("/api/projects", json={
        "project_name": "x", "project_manager_id": "u-nobody"})
    assert res.status_code == 400
    assert "负责人不存在" in res.json()["detail"]


def test_assigning_a_disabled_account_is_rejected(seeded, client):
    res = client.post("/api/projects", json={
        "project_name": "x", "project_manager_id": "u-off"})
    assert res.status_code == 400
    assert "已禁用" in res.json()["detail"]


def test_reassigning_updates_both_id_and_name(seeded, client):
    pid = _create(client, project_manager_id="u-pm")
    assert client.put(f"/api/projects/{pid}", json={"project_manager_id": "u-pm2"}).status_code == 200
    project = client.get(f"/api/projects/{pid}").json()["data"]
    assert project["project_manager_id"] == "u-pm2"
    assert project["project_manager_name"] == "项目李四"


def test_empty_string_unassigns_the_manager(seeded, client):
    """清空负责人要真的清掉：传 None 会被 exclude_none 丢弃，所以用空串表达。"""
    pid = _create(client, project_manager_id="u-pm")
    assert client.put(f"/api/projects/{pid}", json={"project_manager_id": ""}).status_code == 200
    project = client.get(f"/api/projects/{pid}").json()["data"]
    assert project["project_manager_id"] is None
    assert project["project_manager_name"] is None


def test_untouched_manager_survives_other_edits(seeded, client):
    pid = _create(client, project_manager_id="u-pm")
    assert client.put(f"/api/projects/{pid}", json={"client_name": "新客户"}).status_code == 200
    project = client.get(f"/api/projects/{pid}").json()["data"]
    assert project["project_manager_id"] == "u-pm"
    assert project["project_manager_name"] == "项目张三"


def test_legacy_free_text_manager_still_accepted(seeded, client):
    """老客户端只传名字仍然能存，只是本人收不到待办（界面会标未关联账号）。"""
    pid = _create(client, project_manager_name="外包老王")
    project = client.get(f"/api/projects/{pid}").json()["data"]
    assert project["project_manager_id"] is None
    assert project["project_manager_name"] == "外包老王"


# --- 闭环：指派后负责人真的能收到自己项目的待办 -----------------------------

def test_assigned_manager_now_receives_their_project_todos(seeded, as_user):
    """这才是补这一环的目的：绑定账号后，负责人的看板和待办不再是空的。"""
    admin = as_user("admin")
    pid = _create(admin, project_manager_id=USERS["pm"]["user_id"],
                  start_date="2026-01-01", end_date="2026-06-30")

    pm = as_user("pm")
    board = pm.get("/api/alerts/board").json()["data"]
    assert [p["project_id"] for p in board["projects"]] == [pid]

    todos = pm.get("/api/todos").json()["data"]["todos"]
    checklist_todos = [t for t in todos if t["type"] == "project_checklist"]
    assert checklist_todos, "负责人应当收到自己项目的缺件待办"
    assert all(t["project_id"] == pid for t in checklist_todos)


def test_unassigned_project_reaches_admin_only(seeded, as_user):
    """没指派负责人的项目不会凭空消失 —— 管理员仍然看得到、催得到。"""
    admin = as_user("admin")
    pid = _create(admin, start_date="2026-01-01", end_date="2026-06-30")

    assert [p["project_id"] for p in admin.get("/api/alerts/board").json()["data"]["projects"]] == [pid]
    assert admin.get("/api/todos").json()["data"]["summary"]["total"] > 0
    # 其他项目负责人不该被别人的无主项目打扰
    assert as_user("pm").get("/api/todos").json()["data"]["todos"] == []


def test_todos_follow_the_manager_after_reassignment(seeded, as_user):
    admin = as_user("admin")
    pid = _create(admin, project_manager_id=USERS["pm"]["user_id"],
                  start_date="2026-01-01", end_date="2026-06-30")
    assert as_user("pm").get("/api/todos").json()["data"]["todos"]

    # 转给另一个人后，原负责人就不该再被催
    seed_user(user_id=USERS["procurement"]["user_id"], username="buy",
              display_name="采购小李", role="project_manager")
    admin.put(f"/api/projects/{pid}", json={"project_manager_id": USERS["procurement"]["user_id"]})
    assert as_user("pm").get("/api/todos").json()["data"]["todos"] == []
