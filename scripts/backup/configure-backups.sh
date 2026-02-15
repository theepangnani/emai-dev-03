#!/usr/bin/env bash
# One-time setup: enable Cloud SQL automated backups, PITR, and GCS export bucket.
# Usage: ./scripts/backup/configure-backups.sh
#
# Prerequisites:
#   - gcloud CLI authenticated with project owner/editor role
#   - APIs enabled: sqladmin.googleapis.com, storage.googleapis.com

set -euo pipefail

# ---------- Configuration ----------
PROJECT_ID="emai-dev-01"
REGION="us-central1"
INSTANCE="emai-db"
BUCKET_NAME="${PROJECT_ID}-db-backups"
BACKUP_START_TIME="02:00"          # UTC
RETAINED_BACKUPS=7                 # daily backups to keep
TRANSACTION_LOG_DAYS=7             # PITR window (days)
LIFECYCLE_DELETE_DAYS=90           # GCS export retention (days)

echo "=== ClassBridge: Configure Database Backups ==="
echo "Project:   ${PROJECT_ID}"
echo "Instance:  ${INSTANCE}"
echo "Region:    ${REGION}"
echo "Bucket:    gs://${BUCKET_NAME}"
echo ""

# Ensure correct project
gcloud config set project "${PROJECT_ID}"

# ---------- 1. Enable automated daily backups ----------
echo "1/5  Enabling automated backups (daily at ${BACKUP_START_TIME} UTC)..."
gcloud sql instances patch "${INSTANCE}" \
  --backup-start-time="${BACKUP_START_TIME}" \
  --quiet

# ---------- 2. Set backup retention ----------
echo "2/5  Setting backup retention to ${RETAINED_BACKUPS} days..."
gcloud sql instances patch "${INSTANCE}" \
  --retained-backups-count="${RETAINED_BACKUPS}" \
  --enable-bin-log \
  --quiet

# ---------- 3. Enable point-in-time recovery ----------
echo "3/5  Enabling PITR with ${TRANSACTION_LOG_DAYS}-day transaction log retention..."
gcloud sql instances patch "${INSTANCE}" \
  --enable-point-in-time-recovery \
  --retained-transaction-log-days="${TRANSACTION_LOG_DAYS}" \
  --quiet

# ---------- 4. Create GCS bucket for manual exports ----------
echo "4/5  Creating GCS bucket gs://${BUCKET_NAME}..."
if gsutil ls -b "gs://${BUCKET_NAME}" &>/dev/null; then
  echo "     Bucket already exists, skipping creation."
else
  gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${BUCKET_NAME}"
fi

# Set lifecycle rule: delete exports older than N days
echo "     Setting lifecycle rule (delete after ${LIFECYCLE_DELETE_DAYS} days)..."
cat <<EOF | gsutil lifecycle set /dev/stdin "gs://${BUCKET_NAME}"
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": ${LIFECYCLE_DELETE_DAYS}}
    }
  ]
}
EOF

# ---------- 5. Grant Cloud SQL service account access to bucket ----------
echo "5/5  Granting Cloud SQL service account access to bucket..."
SA_EMAIL=$(gcloud sql instances describe "${INSTANCE}" \
  --format='value(serviceAccountEmailAddress)')
gsutil iam ch "serviceAccount:${SA_EMAIL}:objectAdmin" "gs://${BUCKET_NAME}"

# ---------- Verify ----------
echo ""
echo "=== Verification ==="
gcloud sql instances describe "${INSTANCE}" \
  --format="table(settings.backupConfiguration.enabled,settings.backupConfiguration.startTime,settings.backupConfiguration.backupRetentionSettings.retainedBackups,settings.backupConfiguration.pointInTimeRecoveryEnabled,settings.backupConfiguration.transactionLogRetentionDays)"

echo ""
echo "=== Done ==="
echo "Automated backups: daily at ${BACKUP_START_TIME} UTC, ${RETAINED_BACKUPS} retained"
echo "Point-in-time recovery: ${TRANSACTION_LOG_DAYS}-day window"
echo "Manual exports: gs://${BUCKET_NAME} (${LIFECYCLE_DELETE_DAYS}-day retention)"
