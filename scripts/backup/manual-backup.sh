#!/usr/bin/env bash
# Export the production database to a GCS SQL dump on demand.
# Usage: ./scripts/backup/manual-backup.sh [label]
#
# Examples:
#   ./scripts/backup/manual-backup.sh                  # emai-20260215-143022.sql.gz
#   ./scripts/backup/manual-backup.sh pre-migration     # emai-pre-migration-20260215-143022.sql.gz

set -euo pipefail

# ---------- Configuration ----------
PROJECT_ID="emai-dev-01"
INSTANCE="emai-db"
DATABASE="emai"
BUCKET_NAME="${PROJECT_ID}-db-backups"

# ---------- Build filename ----------
LABEL="${1:-}"
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
if [ -n "${LABEL}" ]; then
  FILENAME="${DATABASE}-${LABEL}-${TIMESTAMP}.sql.gz"
else
  FILENAME="${DATABASE}-${TIMESTAMP}.sql.gz"
fi
GCS_URI="gs://${BUCKET_NAME}/manual/${FILENAME}"

echo "=== ClassBridge: Manual Database Export ==="
echo "Instance:  ${INSTANCE}"
echo "Database:  ${DATABASE}"
echo "Export to: ${GCS_URI}"
echo ""

gcloud config set project "${PROJECT_ID}"

# Run export
echo "Exporting (this may take a few minutes)..."
gcloud sql export sql "${INSTANCE}" "${GCS_URI}" \
  --database="${DATABASE}" \
  --quiet

echo ""
echo "=== Export complete ==="
echo "File: ${GCS_URI}"
echo ""
echo "To list recent exports:"
echo "  gsutil ls -l gs://${BUCKET_NAME}/manual/"
echo ""
echo "To restore from this export:"
echo "  ./scripts/backup/restore-from-backup.sh --from-gcs ${GCS_URI}"
