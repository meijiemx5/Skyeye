#!/bin/bash
set -e

# ============================================================
# Skyeye - One-Click Deployment Script
# Usage: ./deploy.sh [profile_name] [region]
# Example: ./deploy.sh my-aws-profile us-east-1
#
# China deployment (custom domains) needs these values, because the default
# execute-api endpoint is blocked there and the SPA must call a custom-domain
# API instead:
#
#   SKYEYE_SITE_DOMAIN        frontend domain on CloudFront   (e.g. ruianwy.site)
#   SKYEYE_SITE_IAM_CERT_ID   IAM server-cert id for the above (CloudFront/CN)
#   SKYEYE_API_DOMAIN         API domain on API Gateway        (e.g. www.ruianwy.site)
#   SKYEYE_API_CERT_ARN       ACM cert ARN (same region as API) for the API domain
#
# They are read from a config file automatically (see below): put them in
# deploy.cn.env (any cn-* region) or deploy.<region>.env. So the command is
# just:  ./deploy.sh skyeye cn-northwest-1
# You can still override any value inline: SKYEYE_API_DOMAIN=x ./deploy.sh ...
#
# When SKYEYE_API_DOMAIN is set, the frontend is built to call it directly
# (VITE_API_URL=https://<api-domain>); otherwise it calls the API Gateway URL.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_PROFILE="${1:-default}"
AWS_REGION="${2:-us-east-1}"

# Auto-load a per-region config file if present, e.g. deploy.cn-northwest-1.env
# or deploy.cn.env for any cn-* region. It just sets the SKYEYE_* vars below.
# Values already set in the environment take precedence (we don't overwrite).
for ENV_FILE in "${SCRIPT_DIR}/deploy.${AWS_REGION}.env" \
                $([ "${AWS_REGION#cn-}" != "${AWS_REGION}" ] && echo "${SCRIPT_DIR}/deploy.cn.env"); do
  if [ -f "${ENV_FILE}" ]; then
    echo "📄 Loading deploy config: ${ENV_FILE}"
    set -a; . "${ENV_FILE}"; set +a
    break
  fi
done

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

# Decide the API base the frontend will call.
# - With SKYEYE_API_DOMAIN set (China): call the API's custom domain directly,
#   e.g. https://www.ruianwy.site. The client appends /api/... itself, so the
#   base is the bare origin (no /api/ suffix). This avoids the blocked
#   execute-api endpoint; cross-origin from the site domain is allowed by CORS.
# - Without it (Global): call the API Gateway URL directly (already ends in /api/).
if [ -n "${SKYEYE_API_DOMAIN}" ]; then
  FRONTEND_API_BASE="https://${SKYEYE_API_DOMAIN#https://}"
  FRONTEND_API_BASE="${FRONTEND_API_BASE%/}"
else
  FRONTEND_API_BASE="${API_URL}"
fi

# Build frontend with the resolved API base.
# Inject VITE_API_URL inline (not via a committed .env.production) and wipe any stale
# dist/ from a previous region so this region's site can only ever embed its own API URL.
echo ""
echo "📋 Step 5: Building frontend (API base: ${FRONTEND_API_BASE})..."
cd "${SCRIPT_DIR}/frontend"
rm -rf dist
npm install --silent
VITE_API_URL="${FRONTEND_API_BASE}" npm run build

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
