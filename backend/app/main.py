"""FastAPI main application."""
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import (
    auth, projects, contracts, reimbursements, acceptances, inventory, upload,
    analysis, audit_logs, reimburse_categories, invoices, alerts,
)

settings = get_settings()

app = FastAPI(
    title="Skyeye - 信息化弱电公司管理系统",
    description="内部信息管理系统 - 合同管理、报销流程、验收资料、项目分析、库存管理",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(contracts.router)
app.include_router(reimbursements.router)
app.include_router(acceptances.router)
app.include_router(inventory.router)
app.include_router(upload.router)
app.include_router(analysis.router)
app.include_router(audit_logs.router)
app.include_router(reimburse_categories.router)
app.include_router(invoices.router)
app.include_router(alerts.router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "skyeye-api", "version": "1.0.0"}


@app.on_event("startup")
def startup_event():
    """Create DynamoDB table if not exists, then initialize default admin user."""
    from .models.base import BaseModel
    from .models.user import UserModel
    from .utils.auth import hash_password

    # Step 1: Create DynamoDB table if it doesn't exist
    try:
        if not BaseModel.exists():
            print(f"Creating DynamoDB table: {BaseModel.Meta.table_name} ...")
            BaseModel.create_table(wait=True)
            print(f"✅ Table '{BaseModel.Meta.table_name}' created successfully.")
        else:
            print(f"✅ Table '{BaseModel.Meta.table_name}' already exists.")
    except Exception as e:
        print(f"⚠️ Table creation warning: {e}")
        return  # Can't proceed without table

    # Step 2: Create default admin user if no users exist
    try:
        users = list(UserModel.scan(filter_condition=UserModel.entity_type == "user", limit=1))
        if not users:
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
            print("✅ Default admin user created: admin / admin123")
    except Exception as e:
        print(f"⚠️ Admin user creation warning: {e}")

    # Step 3: Seed default reimburse categories if empty
    try:
        from .models.reimburse_category import ReimburseCategoryModel
        existing = list(ReimburseCategoryModel.scan(
            filter_condition=ReimburseCategoryModel.entity_type == "reimburse_category", limit=1))
        if not existing:
            now = datetime.now(timezone.utc).isoformat()
            seeds = [
                ("material", "物料采购", None, 1, 10),
                ("travel", "差旅费", None, 1, 20),
                ("equipment_rental", "设备租赁", None, 1, 30),
                ("other", "其他", None, 1, 99),
            ]
            for cid, name, parent, level, sort in seeds:
                c = ReimburseCategoryModel()
                c.PK = ReimburseCategoryModel.make_pk(cid)
                c.SK = ReimburseCategoryModel.make_sk()
                c.GSI1PK = ReimburseCategoryModel.make_gsi1pk(parent)
                c.GSI1SK = ReimburseCategoryModel.make_gsi1sk(sort, cid)
                c.entity_type = "reimburse_category"
                c.category_id = cid
                c.name = name
                c.parent_id = parent
                c.level = level
                c.sort_order = sort
                c.is_active = True
                c.created_at = now
                c.updated_at = now
                c.save()
            print("✅ Default reimburse categories seeded.")
    except Exception as e:
        print(f"⚠️ Reimburse category seeding warning: {e}")
