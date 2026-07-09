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
export SKYEYE_REGION="${AWS_REGION}"
npx cdk bootstrap --profile "${AWS_PROFILE}" 2>/dev/null || true

# Region-scoped output files so Global and China deploys never overwrite each other
BACKEND_OUTPUTS="${SCRIPT_DIR}/cdk-backend-outputs.${AWS_REGION}.json"
FRONTEND_OUTPUTS="${SCRIPT_DIR}/cdk-frontend-outputs.${AWS_REGION}.json"

# Deploy backend stack first
echo ""
echo "📋 Step 4: Deploying backend (DynamoDB + Lambda + API Gateway + S3)..."
npx cdk deploy SkyeyeBackend --profile "${AWS_PROFILE}" --require-approval never --outputs-file "${BACKEND_OUTPUTS}"

# Extract API URL from outputs (fallback to CloudFormation query if outputs file is empty/missing)
API_URL=$(node -p "JSON.parse(require('fs').readFileSync('${BACKEND_OUTPUTS}','utf8'))['SkyeyeBackend']['ApiUrl']" 2>/dev/null || echo "")
if [ -z "${API_URL}" ]; then
  API_URL=$(aws cloudformation describe-stacks --stack-name SkyeyeBackend --profile "${AWS_PROFILE}" --region "${AWS_REGION}" --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text 2>/dev/null || echo "")
fi

# Fail fast: never build the frontend against an empty/wrong API URL. A blank URL
# would silently fall back to localhost and (with a shared secret) point one region's
# site at another region's backend — the exact cross-region data leak we are fixing.
if [ -z "${API_URL}" ]; then
  echo "❌ Could not resolve backend API URL for region ${AWS_REGION}. Aborting before frontend build."
  exit 1
fi

echo "✅ Backend deployed. API URL: ${API_URL}"

# Initialize admin user
echo ""
echo "📋 Step 4.1: Initializing admin user..."
sleep 5  # Wait for Lambda cold start
INIT_RESULT=$(curl -s -X POST "${API_URL}api/auth/init-admin" 2>/dev/null || echo '{"message":"init failed"}')
echo "  ${INIT_RESULT}"

# Build frontend with API URL.
# Inject VITE_API_URL inline (not via a committed .env.production) and wipe any stale
# dist/ from a previous region so this region's site can only ever embed its own API URL.
echo ""
echo "📋 Step 5: Building frontend (API: ${API_URL})..."
cd "${SCRIPT_DIR}/frontend"
rm -rf dist
npm install --silent
VITE_API_URL="${API_URL}" npm run build

# Deploy frontend stack
echo ""
echo "📋 Step 6: Deploying frontend (S3 + CloudFront)..."
cd "${SCRIPT_DIR}/infrastructure"
npx cdk deploy SkyeyeFrontend --profile "${AWS_PROFILE}" --require-approval never --outputs-file "${FRONTEND_OUTPUTS}"

# Extract frontend URL (fallback to CloudFormation query if outputs file is empty/missing)
SITE_URL=$(node -p "JSON.parse(require('fs').readFileSync('${FRONTEND_OUTPUTS}','utf8'))['SkyeyeFrontend']['SiteUrl']" 2>/dev/null || echo "")
if [ -z "${SITE_URL}" ]; then
  SITE_URL=$(aws cloudformation describe-stacks --stack-name SkyeyeFrontend --profile "${AWS_PROFILE}" --region "${AWS_REGION}" --query "Stacks[0].Outputs[?OutputKey=='SiteUrl'].OutputValue" --output text 2>/dev/null || echo "")
fi

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
