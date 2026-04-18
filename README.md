# 👁 Skyeye - 信息化弱电公司管理系统

面向20人规模弱电工程公司的内部管理系统，基于 AWS Serverless 架构构建。

## 功能模块

| 模块 | 说明 |
|------|------|
| **合同管理** | 甲方合同、供应商采购合同、施工人员施工合同的CRUD、附件管理、付款流程跟踪 |
| **报销流程** | 报销申请 → 主管审核 → 财务审核 → 付款，全流程线上化 |
| **验收资料** | 项目验收全流程资料归档、分类查询，支持多种文档类型 |
| **项目分析** | 成本分析、利润分析、项目进度、可视化图表 |
| **库存管理** | 物料入库/出库、库存预警、盘点调整、库存统计 |
| **用户权限** | 6种角色（管理员、财务、项目负责人、采购、施工、仓库），分级权限管理 |

## 技术栈

- **前端**: React + TypeScript + Ant Design + Vite + Recharts
- **后端**: Python FastAPI + PynamoDB + Mangum (Lambda adapter)
- **数据库**: DynamoDB (单表设计, PAY_PER_REQUEST)
- **存储**: S3 (附件存储, Presigned URL上传)
- **部署**: AWS CDK (TypeScript) + Lambda + API Gateway + CloudFront
- **认证**: JWT Token

## 项目结构

```
Skyeye/
├── backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── models/       # PynamoDB 数据模型
│   │   ├── schemas/      # Pydantic 请求/响应模型
│   │   ├── routers/      # API 路由
│   │   ├── utils/        # 工具函数 (认证等)
│   │   ├── config.py     # 配置
│   │   └── main.py       # FastAPI 应用入口
│   ├── lambda_handler.py # Lambda 入口
│   └── requirements.txt
├── frontend/             # React 前端
│   ├── src/
│   │   ├── api/          # API 客户端
│   │   ├── components/   # 公共组件
│   │   └── pages/        # 页面组件
│   └── package.json
├── infrastructure/       # AWS CDK 基础设施 (TypeScript)
│   ├── bin/
│   │   └── app.ts             # CDK 入口
│   ├── lib/
│   │   ├── backend-stack.ts   # DynamoDB + Lambda + API GW + S3
│   │   └── frontend-stack.ts  # S3 + CloudFront
│   ├── package.json
│   ├── tsconfig.json
│   └── cdk.json
├── deploy.sh             # 一键部署脚本
└── docs/                 # 需求文档
```

## 一键部署

### 前提条件

1. **AWS CLI** 已安装并配置了 Profile
2. **Node.js** >= 18
3. **Python** >= 3.9
4. **Docker** 已安装（CDK Lambda bundling 需要）

### 部署步骤

```bash
# 使用默认 profile 部署到 us-east-1
./deploy.sh

# 指定 profile 和 region
./deploy.sh my-profile us-west-2
```

部署完成后会输出:
- **Frontend URL**: CloudFront 分发地址
- **API URL**: API Gateway 地址
- **默认登录**: admin / admin123

## 本地开发

### 环境要求

- **Python** >= 3.10（推荐 3.12，可用 `brew install python@3.12` 安装）
- **Node.js** >= 18
- **AWS CLI** 已配置 Profile（用于连接 DynamoDB 和 S3）

---

### 🚀 首次启动（完整流程）

#### 1. 启动后端

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（首次需要）
python3.12 -m venv .venv

# 激活虚拟环境
source .venv/bin/activate

# 安装依赖（首次需要）
pip install -r requirements.txt

# 设置环境变量
export AWS_PROFILE=your-profile        # 替换为你的 AWS Profile 名称
export AWS_REGION=us-east-1            # AWS 区域
export DYNAMODB_TABLE_NAME=skyeye-dev  # DynamoDB 表名

# 启动后端开发服务器（带热重载）
uvicorn app.main:app --reload --port 8000
```

后端启动后：
- API 地址：http://localhost:8000
- Swagger 文档：http://localhost:8000/docs
- 默认管理员：admin / admin123

#### 2. 启动前端（新开一个终端窗口）

```bash
# 进入前端目录
cd frontend

# 安装依赖（首次需要）
npm install

# 启动前端开发服务器
npm run dev
```

前端启动后：
- 访问地址：http://localhost:5173
- 前端会自动连接 http://localhost:8000 的后端 API

---

### 🔄 日常启动（非首次）

#### 启动后端

```bash
cd backend
source .venv/bin/activate
export AWS_PROFILE=global_prod
export AWS_REGION=us-east-1
export DYNAMODB_TABLE_NAME=skyeye-dev
uvicorn app.main:app --reload --port 8000
```

#### 启动前端（另一个终端）

```bash
cd frontend
npm run dev
```

---

### 🛑 关闭服务

#### 关闭后端

在后端运行的终端中按 `Ctrl + C`，然后退出虚拟环境：

```bash
# 按 Ctrl + C 停止 uvicorn 服务器
# 退出 Python 虚拟环境
deactivate
```

#### 关闭前端

在前端运行的终端中按 `Ctrl + C`：

```bash
# 按 Ctrl + C 停止 Vite 开发服务器
```

---

### 🔧 常用命令速查

| 操作 | 命令 |
|------|------|
| 激活后端虚拟环境 | `cd backend && source .venv/bin/activate` |
| 启动后端 | `uvicorn app.main:app --reload --port 8000` |
| 启动前端 | `cd frontend && npm run dev` |
| 构建前端 | `cd frontend && npm run build` |
| 停止后端/前端 | 在对应终端按 `Ctrl + C` |
| 退出虚拟环境 | `deactivate` |
| 查看 API 文档 | 浏览器打开 http://localhost:8000/docs |
| 一键部署到 AWS | `./deploy.sh your-profile us-east-1` |

## 角色权限

| 角色 | 合同 | 报销 | 验收 | 库存 | 分析 | 用户管理 |
|------|------|------|------|------|------|---------|
| 管理员 | 全部 | 全部 | 全部 | 全部 | 全部 | ✅ |
| 财务人员 | 查看付款 | 审核/付款 | ❌ | ❌ | 查看 | ❌ |
| 项目负责人 | 甲方合同 | 审核 | 上传 | ❌ | 查看 | ❌ |
| 采购专员 | 供应商合同 | ❌ | ❌ | 入出库 | ❌ | ❌ |
| 施工人员 | 查看自己 | 提交 | ❌ | ❌ | ❌ | ❌ |
| 仓库管理员 | ❌ | ❌ | ❌ | 盘点 | ❌ | ❌ |

## API 文档

部署后访问 `{API_URL}/docs` 查看 Swagger 文档。
