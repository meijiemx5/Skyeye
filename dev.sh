#!/bin/bash
# ============================================================
# Skyeye - 本地开发一键启动脚本
# Usage: ./dev.sh [aws_profile] [region]
# Example: ./dev.sh global_prod us-east-1
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_PROFILE="${1:-global_prod}"
AWS_REGION="${2:-us-east-1}"

echo "============================================================"
echo "  👁 Skyeye - 本地开发环境"
echo "============================================================"
echo "  AWS Profile: ${AWS_PROFILE}"
echo "  AWS Region:  ${AWS_REGION}"
echo "============================================================"

# Get AWS account ID for S3 bucket name
ACCOUNT_ID=$(aws sts get-caller-identity --profile "${AWS_PROFILE}" --region "${AWS_REGION}" --query 'Account' --output text 2>/dev/null || echo "")
S3_BUCKET="skyeye-attachments-${ACCOUNT_ID}"

if [ -z "$ACCOUNT_ID" ]; then
    echo "⚠️ 无法获取AWS账号ID，S3上传功能可能不可用"
    S3_BUCKET="skyeye-attachments"
else
    echo "  AWS Account: ${ACCOUNT_ID}"
    echo "  S3 Bucket:   ${S3_BUCKET}"
fi
echo "============================================================"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 正在关闭服务..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "✅ 服务已关闭"
}
trap cleanup EXIT INT TERM

# Step 1: Setup backend virtual environment (if needed)
if [ ! -d "${SCRIPT_DIR}/backend/.venv" ]; then
    echo "📋 首次运行：创建Python虚拟环境..."
    cd "${SCRIPT_DIR}/backend"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt -q
    echo "✅ 虚拟环境创建完成"
else
    cd "${SCRIPT_DIR}/backend"
    source .venv/bin/activate
fi

# Step 2: Setup frontend (if needed)
if [ ! -d "${SCRIPT_DIR}/frontend/node_modules" ]; then
    echo "📋 首次运行：安装前端依赖..."
    cd "${SCRIPT_DIR}/frontend"
    npm install --silent
    echo "✅ 前端依赖安装完成"
fi

# Step 3: Start backend
echo ""
echo "🚀 启动后端 (http://localhost:8000)..."
cd "${SCRIPT_DIR}/backend"
source .venv/bin/activate
export AWS_PROFILE="${AWS_PROFILE}"
export AWS_REGION="${AWS_REGION}"
export DYNAMODB_TABLE_NAME="skyeye-dev"
export S3_BUCKET_NAME="${S3_BUCKET}"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Step 4: Start frontend
echo "🚀 启动前端 (http://localhost:5173)..."
cd "${SCRIPT_DIR}/frontend"
npm run dev &
FRONTEND_PID=$!

# Wait for frontend
sleep 2

echo ""
echo "============================================================"
echo "  ✅ 本地开发环境已启动！"
echo "============================================================"
echo "  前端: http://localhost:5173"
echo "  后端: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo ""
echo "  默认登录: admin / admin123"
echo ""
echo "  按 Ctrl+C 关闭所有服务"
echo "============================================================"

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
