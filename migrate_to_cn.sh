#!/bin/bash
# ============================================================
# Skyeye - Global → China data migration (DynamoDB + S3)
#
# Copies all data from the Global deployment (source) into the
# China deployment (target): every DynamoDB item and every S3
# attachment object. The frontend/backend stacks must already be
# deployed on BOTH sides (this moves DATA only, not infrastructure).
#
# Safe by design:
#   - read-only preflight on both accounts before anything is written
#   - --dry-run shows exactly what would move, changes nothing
#   - explicit typed confirmation before any write
#   - idempotent: re-running overwrites with the same data (no dup)
#   - never deletes anything on source or target
#
# s3_key values in DynamoDB are RELATIVE paths (entity/id/file),
# not bucket-qualified, so items copy as-is and objects copy
# key-for-key — no rewriting needed.
#
# Usage:
#   ./migrate_to_cn.sh                 # migrate (asks for confirmation)
#   ./migrate_to_cn.sh --dry-run       # preview only, no writes
#   SRC_PROFILE=global_prod DST_PROFILE=skyeye ./migrate_to_cn.sh
# ============================================================
set -euo pipefail

# ---- Configuration (override via env vars) ----
SRC_PROFILE="${SRC_PROFILE:-global_prod}"
SRC_REGION="${SRC_REGION:-us-east-1}"
DST_PROFILE="${DST_PROFILE:-skyeye}"
DST_REGION="${DST_REGION:-cn-northwest-1}"
TABLE_NAME="${TABLE_NAME:-skyeye-dev}"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

WORK_DIR="$(mktemp -d -t skyeye-migrate-XXXXXX)"
trap 'rm -rf "${WORK_DIR}"' EXIT

echo "============================================================"
echo "  👁 Skyeye - Global → China 数据迁移"
echo "============================================================"
echo "  源 (source):  profile=${SRC_PROFILE}  region=${SRC_REGION}"
echo "  目标 (target): profile=${DST_PROFILE}  region=${DST_REGION}"
echo "  表: ${TABLE_NAME}"
[ "${DRY_RUN}" = "1" ] && echo "  模式: DRY-RUN (只预览，不写入)"
echo "============================================================"

# ============================================================
# Step 1: Read-only preflight — verify both accounts & resources
# ============================================================
echo ""
echo "📋 Step 1: 校验双方账号与资源 (只读)..."

SRC_ACCOUNT=$(aws sts get-caller-identity --profile "${SRC_PROFILE}" --region "${SRC_REGION}" --query 'Account' --output text)
DST_ACCOUNT=$(aws sts get-caller-identity --profile "${DST_PROFILE}" --region "${DST_REGION}" --query 'Account' --output text)
echo "  源账号:   ${SRC_ACCOUNT}"
echo "  目标账号: ${DST_ACCOUNT}"

if [ "${SRC_ACCOUNT}" = "${DST_ACCOUNT}" ]; then
  echo "❌ 源和目标是同一个账号 (${SRC_ACCOUNT})。请检查 profile 配置，避免误操作。"
  exit 1
fi

# Attachment buckets follow the convention skyeye-attachments-<account>
SRC_BUCKET="skyeye-attachments-${SRC_ACCOUNT}"
DST_BUCKET="skyeye-attachments-${DST_ACCOUNT}"

SRC_ITEMS=$(aws dynamodb describe-table --table-name "${TABLE_NAME}" --profile "${SRC_PROFILE}" --region "${SRC_REGION}" --query 'Table.ItemCount' --output text)
DST_STATUS=$(aws dynamodb describe-table --table-name "${TABLE_NAME}" --profile "${DST_PROFILE}" --region "${DST_REGION}" --query 'Table.TableStatus' --output text 2>/dev/null || echo "MISSING")
DST_ITEMS=$(aws dynamodb describe-table --table-name "${TABLE_NAME}" --profile "${DST_PROFILE}" --region "${DST_REGION}" --query 'Table.ItemCount' --output text 2>/dev/null || echo "0")

if [ "${DST_STATUS}" = "MISSING" ]; then
  echo "❌ 目标表 ${TABLE_NAME} 不存在 (region ${DST_REGION})。请先在 CN 账号部署后端栈。"
  exit 1
fi

echo "  源表约 ${SRC_ITEMS} 项  |  目标表约 ${DST_ITEMS} 项 (${DST_STATUS})"
echo "  源桶:   ${SRC_BUCKET}"
echo "  目标桶: ${DST_BUCKET}"

# Confirm target attachment bucket exists (list is read-only)
if ! aws s3api head-bucket --bucket "${DST_BUCKET}" --profile "${DST_PROFILE}" --region "${DST_REGION}" >/dev/null 2>&1; then
  echo "❌ 目标桶 ${DST_BUCKET} 不存在或无权访问。请先在 CN 账号部署后端栈。"
  exit 1
fi

if [ "${DST_ITEMS}" != "0" ]; then
  echo "⚠️  目标表已有约 ${DST_ITEMS} 项数据。迁移会按主键覆盖同名项 (不会删除目标独有数据)。"
fi
echo "✅ 校验通过。"

# ============================================================
# Step 2: Confirmation gate
# ============================================================
if [ "${DRY_RUN}" != "1" ]; then
  echo ""
  echo "⚠️  即将把 ${SRC_ACCOUNT} 的数据写入 ${DST_ACCOUNT}。此操作会写入目标账号。"
  printf "  确认请输入大写 MIGRATE 回车: "
  read -r CONFIRM
  if [ "${CONFIRM}" != "MIGRATE" ]; then
    echo "已取消。"
    exit 0
  fi
fi

# ============================================================
# Step 3: Migrate DynamoDB items (scan source → batch-write target)
# ============================================================
echo ""
echo "📋 Step 3: 迁移 DynamoDB 数据..."
ITEMS_FILE="${WORK_DIR}/items.json"

# Scan all items (paginated automatically by the CLI), collect raw item maps.
aws dynamodb scan \
  --table-name "${TABLE_NAME}" \
  --profile "${SRC_PROFILE}" --region "${SRC_REGION}" \
  --output json \
  --query 'Items' > "${ITEMS_FILE}"

TOTAL_ITEMS=$(python3 -c "import json;print(len(json.load(open('${ITEMS_FILE}'))))")
echo "  已从源表读取 ${TOTAL_ITEMS} 项。"

if [ "${DRY_RUN}" = "1" ]; then
  echo "  [dry-run] 将写入 ${TOTAL_ITEMS} 项到目标表 (跳过)。"
else
  # Chunk into batch-write requests of 25 (DynamoDB limit), one request file each.
  python3 - "${ITEMS_FILE}" "${WORK_DIR}" "${TABLE_NAME}" <<'PY'
import json, sys, os
items_file, work_dir, table = sys.argv[1], sys.argv[2], sys.argv[3]
items = json.load(open(items_file))
n = 0
for i in range(0, len(items), 25):
    chunk = items[i:i+25]
    req = {table: [{"PutRequest": {"Item": it}} for it in chunk]}
    with open(os.path.join(work_dir, f"batch_{n:04d}.json"), "w") as f:
        json.dump(req, f)
    n += 1
print(n)
PY
  WRITTEN=0
  for bf in "${WORK_DIR}"/batch_*.json; do
    [ -e "${bf}" ] || continue
    # batch-write-item may return UnprocessedItems under throttling; retry those.
    UNPROCESSED=$(aws dynamodb batch-write-item \
      --request-items "file://${bf}" \
      --profile "${DST_PROFILE}" --region "${DST_REGION}" \
      --output json --query 'UnprocessedItems' 2>/dev/null || echo '{}')
    RETRY=0
    while [ "${UNPROCESSED}" != "{}" ] && [ "${UNPROCESSED}" != "null" ] && [ "${RETRY}" -lt 5 ]; do
      sleep 1
      echo "${UNPROCESSED}" > "${bf}.retry"
      UNPROCESSED=$(aws dynamodb batch-write-item \
        --request-items "file://${bf}.retry" \
        --profile "${DST_PROFILE}" --region "${DST_REGION}" \
        --output json --query 'UnprocessedItems' 2>/dev/null || echo '{}')
      RETRY=$((RETRY+1))
    done
    WRITTEN=$((WRITTEN+1))
  done
  echo "  ✅ DynamoDB 迁移完成 (${WRITTEN} 批, 约 ${TOTAL_ITEMS} 项)。"
fi

# ============================================================
# Step 4: Migrate S3 attachments (cross-partition: download → upload)
# ============================================================
echo ""
echo "📋 Step 4: 迁移 S3 附件 (${SRC_BUCKET} → ${DST_BUCKET})..."

# aws-cn is a different partition than aws, so `s3 sync` bucket-to-bucket
# won't work across them. Mirror to a local temp dir, then push up.
LOCAL_MIRROR="${WORK_DIR}/s3"
mkdir -p "${LOCAL_MIRROR}"

OBJ_COUNT=$(aws s3 ls "s3://${SRC_BUCKET}/" --recursive --profile "${SRC_PROFILE}" --region "${SRC_REGION}" 2>/dev/null | grep -c . || echo 0)
echo "  源桶约 ${OBJ_COUNT} 个对象。"

if [ "${DRY_RUN}" = "1" ]; then
  echo "  [dry-run] 将下载并上传 ${OBJ_COUNT} 个对象 (跳过)。"
else
  echo "  下载源桶到本地临时目录..."
  aws s3 sync "s3://${SRC_BUCKET}/" "${LOCAL_MIRROR}/" \
    --profile "${SRC_PROFILE}" --region "${SRC_REGION}" --only-show-errors
  echo "  上传到目标桶..."
  aws s3 sync "${LOCAL_MIRROR}/" "s3://${DST_BUCKET}/" \
    --profile "${DST_PROFILE}" --region "${DST_REGION}" --only-show-errors
  echo "  ✅ S3 附件迁移完成。"
fi

# ============================================================
# Step 5: Post-migration verification (read-only)
# ============================================================
echo ""
echo "📋 Step 5: 迁移后核对 (只读)..."
if [ "${DRY_RUN}" = "1" ]; then
  echo "  [dry-run] 跳过核对。"
else
  # ItemCount in describe-table is eventually consistent (~6h lag), so count live.
  DST_ITEMS_NOW=$(aws dynamodb scan --table-name "${TABLE_NAME}" \
    --profile "${DST_PROFILE}" --region "${DST_REGION}" \
    --select COUNT --output text --query 'Count')
  DST_OBJ_NOW=$(aws s3 ls "s3://${DST_BUCKET}/" --recursive \
    --profile "${DST_PROFILE}" --region "${DST_REGION}" 2>/dev/null | grep -c . || echo 0)
  echo "  目标表实时项数: ${DST_ITEMS_NOW} (源 ${TOTAL_ITEMS})"
  echo "  目标桶对象数:   ${DST_OBJ_NOW} (源 ${OBJ_COUNT})"
fi

echo ""
echo "============================================================"
echo "  🎉 迁移${DRY_RUN:+预览}完成！"
echo "============================================================"
echo "  提示: 附件的 s3_key 是相对路径，CN 后端的 S3_BUCKET_NAME"
echo "        已指向 ${DST_BUCKET}，无需改数据。"
echo "  验证: 打开 CN 站点登录后应能看到迁移过来的合同/报销/库存数据。"
echo "============================================================"
