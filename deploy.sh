#!/bin/bash
set -e

# ============================================================
# Skyeye - One-Click Deployment Script
# Usage: ./deploy.sh [profile_name] [region]
# Example: ./deploy.sh my-aws-profile us-east-1
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_PROFILE="${1:-default}"
AWS_REGION="${2:-us-east-1}"

echo "============================================================"
echo "  👁 Skyeye - 信息化弱电公司管理系统"
echo "  One-Click Deployment"
echo "============================================================"
echo "  AWS Profile: ${AWS_PROFILE}"
echo "  AWS Region:  ${AWS_REGION}"
echo "============================================================"

# Verify AWS credentials
echo ""
echo "📋 Step 1: Verifying AWS credentials..."
aws sts get-caller-identity --profile "${AWS_PROFILE}" --region "${AWS_REGION}" || {
    echo "❌ AWS credentials verification failed. Please check your profile: ${AWS_PROFILE}"
    exit 1
}
echo "✅ AWS credentials verified."

# Set up CDK environment (TypeScript)
echo ""
echo "📋 Step 2: Setting up CDK environment..."
cd "${SCRIPT_DIR}/infrastructure"
npm install --silent

# Check CDK is available
if ! command -v cdk &> /dev/null; then
    echo "Installing AWS CDK CLI..."
    npm install -g aws-cdk
fi

# Bootstrap CDK (if needed)
echo ""
echo "📋 Step 3: Bootstrapping CDK..."
export CDK_DEFAULT_REGION="${AWS_REGION}"
npx cdk bootstrap --profile "${AWS_PROFILE}" 2>/dev/null || true

# Deploy backend stack first
echo ""
echo "📋 Step 4: Deploying backend (DynamoDB + Lambda + API Gateway + S3)..."
npx cdk deploy SkyeyeBackend --profile "${AWS_PROFILE}" --require-approval never --outputs-file "${SCRIPT_DIR}/cdk-outputs.json"

# Extract API URL from outputs
API_URL=$(node -e "
const fs = require('fs');
const outputs = JSON.parse(fs.readFileSync('${SCRIPT_DIR}/cdk-outputs.json', 'utf8'));
console.log(outputs['SkyeyeBackend']?.ApiUrl || '');
" 2>/dev/null || echo "")

echo "✅ Backend deployed. API URL: ${API_URL}"

# Build frontend with API URL
echo ""
echo "📋 Step 5: Building frontend..."
cd "${SCRIPT_DIR}/frontend"
echo "VITE_API_URL=${API_URL}" > .env.production
npm install --silent
npm run build

# Deploy frontend stack
echo ""
echo "📋 Step 6: Deploying frontend (S3 + CloudFront)..."
cd "${SCRIPT_DIR}/infrastructure"
npx cdk deploy SkyeyeFrontend --profile "${AWS_PROFILE}" --require-approval never --outputs-file "${SCRIPT_DIR}/cdk-outputs.json"

# Extract frontend URL
SITE_URL=$(node -e "
const fs = require('fs');
const outputs = JSON.parse(fs.readFileSync('${SCRIPT_DIR}/cdk-outputs.json', 'utf8'));
console.log(outputs['SkyeyeFrontend']?.SiteUrl || '');
" 2>/dev/null || echo "")

echo ""
echo "============================================================"
echo "  🎉 Deployment Complete!"
echo "============================================================"
echo "  Frontend URL: ${SITE_URL}"
echo "  API URL:      ${API_URL}"
echo ""
echo "  Default Login: admin / admin123"
echo "  (Please change the admin password after first login)"
echo "============================================================"
