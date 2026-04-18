"""Authentication router."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from pynamodb.exceptions import DoesNotExist

from ..models.user import UserModel
from ..schemas.user import LoginRequest, LoginResponse, UserCreate, UserUpdate, UserOut, ChangePassword
from ..schemas.common import APIResponse
from ..utils.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_roles
)

router = APIRouter(prefix="/api/auth", tags=["认证管理"])


@router.post("/init-admin")
def init_admin():
    """Initialize default admin user if no users exist. Safe to call multiple times."""
    from ..utils.auth import hash_password
    from datetime import datetime, timezone
    
    users = list(UserModel.scan(
        filter_condition=UserModel.entity_type == "user",
        limit=1
    ))
    if users:
        return APIResponse(message="管理员已存在，无需初始化", data={"exists": True})
    
    user_id = "admin001"
    now = datetime.now(timezone.utc).isoformat()
    admin = UserModel()
    admin.PK = UserModel.make_pk(user_id)
    admin.SK = UserModel.make_sk()
    admin.GSI1PK = UserModel.make_gsi1pk("admin")
    admin.GSI1SK = UserModel.make_gsi1sk(user_id)
    admin.entity_type = "user"
    admin.user_id = user_id
    admin.username = "admin"
    admin.display_name = "系统管理员"
    admin.password_hash = hash_password("admin123")
    admin.role = "admin"
    admin.is_active = True
    admin.login_fail_count = 0
    admin.created_at = now
    admin.updated_at = now
    admin.save()
    return APIResponse(message="管理员初始化成功", data={"username": "admin", "password": "admin123"})


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """User login."""
    # Find user by username - scan for username match (small dataset, ok for 20 users)
    users = list(UserModel.scan(
        filter_condition=(UserModel.entity_type == "user") & (UserModel.username == req.username),
        limit=1
    ))
    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    
    user = users[0]
    
    # Check if account is locked
    if user.locked_until:
        lock_time = datetime.fromisoformat(user.locked_until)
        if datetime.now(timezone.utc) < lock_time:
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="账号已锁定，请1小时后再试")
        else:
            user.locked_until = None
            user.login_fail_count = 0
            user.save()
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
    
    if not verify_password(req.password, user.password_hash):
        user.login_fail_count = (user.login_fail_count or 0) + 1
        if user.login_fail_count >= 3:
            from datetime import timedelta
            user.locked_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        user.save()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    
    # Reset fail count on successful login
    user.login_fail_count = 0
    user.locked_until = None
    user.save()
    
    token = create_access_token({
        "sub": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    })
    
    from ..services.audit import log_action
    log_action(user.user_id, f"{user.username}({user.display_name})", "login", "user", user.user_id, "用户登录")
    
    return LoginResponse(
        access_token=token,
        user={
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "department": user.department,
        }
    )


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    try:
        user = UserModel.get(
            UserModel.make_pk(current_user["user_id"]),
            UserModel.make_sk()
        )
        return APIResponse(data={
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "phone": user.phone,
            "email": user.email,
            "department": user.department,
            "is_active": user.is_active,
        })
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="用户不存在")


@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user)):
    """User logout - record audit log."""
    from ..services.audit import log_action
    log_action(current_user["user_id"], f"{current_user['username']}({current_user['display_name']})", "logout", "user", current_user["user_id"], "用户退出登录")
    return APIResponse(message="退出成功")


@router.post("/change-password")
def change_password(req: ChangePassword, current_user: dict = Depends(get_current_user)):
    """Change password."""
    try:
        user = UserModel.get(
            UserModel.make_pk(current_user["user_id"]),
            UserModel.make_sk()
        )
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    
    user.password_hash = hash_password(req.new_password)
    user.updated_at = datetime.now(timezone.utc).isoformat()
    user.save()
    return APIResponse(message="密码修改成功")


@router.get("/users")
def list_users(current_user: dict = Depends(require_roles("admin"))):
    """List all users (admin only)."""
    users = list(UserModel.scan(filter_condition=UserModel.entity_type == "user"))
    result = []
    for u in users:
        result.append({
            "user_id": u.user_id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "phone": u.phone,
            "email": u.email,
            "department": u.department,
            "is_active": u.is_active,
            "created_at": u.created_at,
        })
    return APIResponse(data=result, total=len(result))


@router.post("/users")
def create_user(req: UserCreate, current_user: dict = Depends(require_roles("admin"))):
    """Create a new user (admin only)."""
    # Check duplicate username
    existing = list(UserModel.scan(
        filter_condition=(UserModel.entity_type == "user") & (UserModel.username == req.username),
        limit=1
    ))
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    user_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    
    user = UserModel()
    user.PK = UserModel.make_pk(user_id)
    user.SK = UserModel.make_sk()
    user.GSI1PK = UserModel.make_gsi1pk(req.role)
    user.GSI1SK = UserModel.make_gsi1sk(user_id)
    user.entity_type = "user"
    user.user_id = user_id
    user.username = req.username
    user.display_name = req.display_name
    user.password_hash = hash_password(req.password)
    user.role = req.role
    user.phone = req.phone
    user.email = req.email
    user.department = req.department
    user.is_active = True
    user.login_fail_count = 0
    user.created_at = now
    user.updated_at = now
    user.created_by = current_user["user_id"]
    user.save()
    
    return APIResponse(message="用户创建成功", data={"user_id": user_id})


@router.put("/users/{user_id}")
def update_user(user_id: str, req: UserUpdate, current_user: dict = Depends(require_roles("admin"))):
    """Update user (admin only)."""
    try:
        user = UserModel.get(UserModel.make_pk(user_id), UserModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    if req.role:
        user.GSI1PK = UserModel.make_gsi1pk(req.role)
    
    user.updated_at = datetime.now(timezone.utc).isoformat()
    user.updated_by = current_user["user_id"]
    user.save()
    
    return APIResponse(message="用户更新成功")


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Reset user password (admin only). Resets to '123456'."""
    try:
        user = UserModel.get(UserModel.make_pk(user_id), UserModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    new_password = "123456"
    user.password_hash = hash_password(new_password)
    user.login_fail_count = 0
    user.locked_until = None
    user.updated_at = datetime.now(timezone.utc).isoformat()
    user.updated_by = current_user["user_id"]
    user.save()
    return APIResponse(message=f"密码已重置为: {new_password}")


@router.delete("/users/{user_id}")
def delete_user(user_id: str, current_user: dict = Depends(require_roles("admin"))):
    """Delete user (admin only)."""
    try:
        user = UserModel.get(UserModel.make_pk(user_id), UserModel.make_sk())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user.delete()
    return APIResponse(message="用户删除成功")
