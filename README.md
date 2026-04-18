# 👁 Skyeye - 信息化弱电公司管理系统

面向20人规模弱电工程公司的内部信息管理系统，基于 AWS Serverless 架构构建。

## 功能模块

| 模块 | 说明 |
|------|------|
| **工作台** | 数据概览（项目/合同/报销/库存统计）、项目概览列表 |
| **项目管理** | 项目CRUD、状态跟踪、负责人分配、角色数据过滤 |
| **合同管理** | 甲方/供应商/施工合同CRUD、自动编号、统计、付款跟踪 |
| **报销管理** | 报销申请 → 主管审核 → 财务审核 → 付款，全流程线上化 |
| **验收资料** | 项目验收全流程资料归档、分类查询、整改管理 |
| **库存管理** | 物料CRUD、入库/出库/盘点、库存预警、统计 |
| **项目分析** | 收入/成本/利润分析、柱状图/饼图可视化 |
| **用户管理** | 6种角色、CRUD、启用/禁用、重置密码 |
| **操作日志** | 登录/退出/操作记录、按类型/日期筛选（仅管理员） |
| **用户指南** | 权限矩阵、各角色操作指南（所有用户可见） |

## 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | React 18 + TypeScript + Ant Design 5 + Vite 5 + Recharts |
| **后端** | Python 3.12 + FastAPI + PynamoDB 6 + Mangum |
| **数据库** | DynamoDB（单表设计, PAY_PER_REQUEST, 2个GSI） |
| **存储** | S3（附件存储, Presigned URL上传） |
| **部署** | AWS CDK (TypeScript) + Lambda + API Gateway + CloudFront |
| **认证** | JWT Token（24h过期）+ SHA-256+Salt密码加密 |

## 项目结构

```
Skyeye/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── models/             # PynamoDB 数据模型（单表设计）
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── routers/            # API 路由
│   │   │   ├── auth.py         # 认证 & 用户管理
│   │   │   ├── projects.py     # 项目管理
│   │   │   ├── contracts.py    # 合同管理
│   │   │   ├── reimbursements.py # 报销管理
│   │   │   ├── acceptances.py  # 验收资料
│   │   │   ├── inventory.py    # 库存管理
│   │   │   ├── analysis.py     # 项目分析
│   │   │   ├── audit_logs.py   # 操作日志
│   │   │   └── upload.py       # 文件上传
│   │   ├── services/
│   │   │   └── audit.py        # 审计日志服务
│   │   └── utils/
│   │       └── auth.py         # JWT认证工具
│   ├── lambda_handler.py       # Lambda 入口
│   └── requirements.txt
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── api/client.ts       # API客户端（全部接口封装）
│   │   ├── components/
│   │   │   └── MainLayout.tsx  # 主布局（响应式侧边栏+密码修改）
│   │   └── pages/
│   │       ├── Login.tsx       # 登录页
│   │       ├── Dashboard.tsx   # 工作台
│   │       ├── Projects.tsx    # 项目管理
│   │       ├── Contracts.tsx   # 合同管理
│   │       ├── Reimbursements.tsx # 报销管理
│   │       ├── Acceptances.tsx # 验收资料
│   │       ├── Inventory.tsx   # 库存管理
│   │       ├── Analysis.tsx    # 项目分析
│   │       ├── Users.tsx       # 用户管理
│   │       ├── AuditLogs.tsx   # 操作日志
│   │       └── UserGuide.tsx   # 用户指南
│   └── package.json
├── infrastructure/             # AWS CDK 基础设施
│   ├── lib/
│   │   ├── backend-stack.ts    # DynamoDB + Lambda + API GW + S3
│   │   └── frontend-stack.ts   # S3 + CloudFront
│   └── package.json
├── docs/                       # 文档
│   ├── 架构设计文档.md
│   ├── 数据库设计文档.md
│   ├── 业务逻辑文档.md
│   └── 软件需求文档.docx
├── deploy.sh                   # 一键部署脚本
└── README.md
```

## 一键部署

### 前提条件

- **AWS CLI** 已安装并配置了 Profile
- **Node.js** >= 18
- **Python** >= 3.9

### 部署命令

```bash
# 指定 AWS profile 和 region
./deploy.sh my-profile us-east-1
```

### 部署流程

1. ✅ 验证 AWS 凭证
2. ✅ 安装 CDK 依赖
3. ✅ CDK Bootstrap（首次需要）
4. ✅ 部署后端栈（DynamoDB + Lambda + API Gateway + S3）
5. ✅ 构建前端（注入 API URL）
6. ✅ 部署前端栈（S3 + CloudFront）

部署完成后输出:
```
🎉 Deployment Complete!
Frontend URL: https://xxxxx.cloudfront.net
API URL:      https://xxxxx.execute-api.us-east-1.amazonaws.com/api/
Default Login: admin / admin123
```

### 更新部署

代码修改后，重新运行同一命令即可增量更新：
```bash
./deploy.sh my-profile us-east-1
```

仅更新前端（更快）：
```bash
cd frontend && npm run build
aws s3 sync dist/ s3://skyeye-frontend-{account}/ --delete --profile my-profile
aws cloudfront create-invalidation --distribution-id {id} --paths "/*" --profile my-profile
```

## 本地开发

### 启动后端

```bash
cd backend
python3.12 -m venv .venv        # 首次
source .venv/bin/activate
pip install -r requirements.txt  # 首次

export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1
export DYNAMODB_TABLE_NAME=skyeye-dev

uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- 首次启动自动创建 DynamoDB 表和管理员账号

### 启动前端

```bash
cd frontend
npm install    # 首次
npm run dev
```

- 访问: http://localhost:5173
- 自动连接 http://localhost:8000

## 角色权限

| 操作 | 管理员 | 财务 | 项目负责人 | 采购 | 施工 | 仓库 |
|------|:------:|:----:|:---------:|:----:|:----:|:----:|
| 用户管理/重置密码 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 创建/编辑项目 | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 创建甲方合同 | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 创建供应商合同 | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 提交报销 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 主管审核报销 | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 财务审核/付款 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 创建验收记录 | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| 创建物料 | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| 入库/出库 | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 盘点调整 | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| 查看项目分析 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 操作日志 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 修改自己密码 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

> 没有权限的操作按钮在UI上不会显示。

## 安全机制

- **JWT认证**: 所有业务接口需Bearer Token（24h过期）
- **密码加密**: SHA-256 + 16位随机Salt
- **账号锁定**: 3次密码错误锁定1小时
- **角色权限**: 后端接口级权限校验
- **HTTPS**: API Gateway + CloudFront 默认启用

## 响应式设计

- 📱 手机端：侧边栏变为抽屉式菜单，表格横向滚动，卡片自动堆叠
- 💻 电脑端：标准侧边栏布局，完整数据展示

## 成本估算（20人规模）

| 服务 | 预估月费用 |
|------|-----------|
| DynamoDB | ~$1-5 |
| Lambda | ~$0-1 |
| API Gateway | ~$1-3 |
| S3 | ~$1-5 |
| CloudFront | ~$0-1 |
| **总计** | **~$3-15/月** |

## 文档

- [架构设计文档](docs/架构设计文档.md)
- [数据库设计文档](docs/数据库设计文档.md)
- [业务逻辑文档](docs/业务逻辑文档.md)

## License

MIT
