#!/usr/bin/env bash
# Restore the production database from an automated backup, GCS export, or PITR clone.
#
# Usage:
#   ./scripts/backup/restore-from-backup.sh --from-backup <BACKUP_ID>
#   ./scripts/backup/restore-from-backup.sh --from-gcs <GCS_URI>
#   ./scripts/backup/restore-from-backup.sh --pitr <TIMESTAMP>
#
# Examples:
#   # Restore from automated backup (overwrites current data):
#   ./scripts/backup/restore-from-backup.sh --from-backup 1708000000000
#
#   # Import from GCS SQL dump (overwrites current data):
#   ./scripts/backup/restore-from-backup.sh --from-gcs gs://emai-dev-01-db-backups/manual/emai-20260215-143022.sql.gz
#
#   # Clone instance to a point in time (creates NEW instance):
#   ./scripts/backup/restore-from-backup.sh --pitr "2026-02-15T10:00:00Z"
#
# To list available automated backups:
#   gcloud sql backups list --instance=emai-db --project=emai-dev-01
#
# To list GCS exports:
#   gsutil ls -l gs://emai-dev-01-db-backups/manual/

set -euo pipefail

# ---------- Configuration ----------
PROJECT_ID="emai-dev-01"
REGION="us-central1"
INSTANCE="emai-db"
DATABASE="emai"

echo "=== ClassBridge: Database Restore ==="
gcloud config set project "${PROJECT_ID}"

# ---------- Parse arguments ----------
MODE=""
VALUE=""

case "${1:-}" in
  --from-backup)
    MODE="backup"
    VALUE="${2:?Error: provide BACKUP_ID. List with: gcloud sql backups list --instance=${INSTANCE}}"
    ;;
  --from-gcs)
    MODE="gcs"
    VALUE="${2:?Error: provide GCS_URI (e.g. gs://emai-dev-01-db-backups/manual/emai-....sql.gz)}"
    ;;
  --pitr)
    MODE="pitr"
    VALUE="${2:?Error: provide TIMESTAMP in RFC 3339 format (e.g. 2026-02-15T10:00:00Z)}"
    ;;
  *)
    echo "Usage:"
    echo "  $0 --from-backup <BACKUP_ID>    Restore from automated backup"
    echo "  $0 --from-gcs <GCS_URI>         Import from GCS SQL dump"
    echo "  $0 --pitr <TIMESTAMP>            Clone to point-in-time (new instance)"
    echo ""
    echo "List automated backups:"
    echo "  gcloud sql backups list --instance=${INSTANCE}"
    echo ""
    echo "List GCS exports:"
    echo "  gsutil ls -l gs://${PROJECT_ID}-db-backups/manual/"
    exit 1
    ;;
esac

# ---------- Restore ----------
case "${MODE}" in
  backup)
    echo ""
    echo "Mode:      Restore from automated backup"
    echo "Backup ID: ${VALUE}"
    echo "Instance:  ${INSTANCE}"
    echo ""
    echo "WARNING: This will overwrite all current data in ${INSTANCE}."
    read -rp "Type 'yes' to confirm: " CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then
      echo "Aborted."
      exit 0
    fi

    echo "Restoring..."
    gcloud sql backups restore "${VALUE}" \
      --restore-instance="${INSTANCE}" \
      --quiet

    echo ""
    echo "=== Restore from backup complete ==="
    echo "Verify: gcloud sql instances describe ${INSTANCE} --format='value(state)'"
    ;;

  gcs)
    echo ""
    echo "Mode:     Import from GCS"
    echo "GCS URI:  ${VALUE}"
    echo "Instance: ${INSTANCE}"
    echo "Database: ${DATABASE}"
    echo ""
    echo "WARNING: This will import SQL into ${DATABASE}, which may overwrite existing data."
    read -rp "Type 'yes' to confirm: " CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then
      echo "Aborted."
      exit 0
    fi

    echo "Importing..."
    gcloud sql import sql "${INSTANCE}" "${VALUE}" \
      --database="${DATABASE}" \
      --quiet

    echo ""
    echo "=== Import from GCS complete ==="
    echo "Verify: gcloud sql instances describe ${INSTANCE} --format='value(state)'"
    ;;

  pitr)
    CLONE_INSTANCE="${INSTANCE}-pitr-$(date -u +%Y%m%d%H%M%S)"
    echo ""
    echo "Mode:           Point-in-time recovery (clone)"
    echo "Source:         ${INSTANCE}"
    echo "Timestamp:      ${VALUE}"
    echo "Clone instance: ${CLONE_INSTANCE}"
    echo ""
    echo "This creates a NEW Cloud SQL instance restored to the specified time."
    echo "After verification, you can promote it or migrate data manually."
    read -rp "Type 'yes' to confirm: " CONFIRM
    if [ "${CONFIRM}" != "yes" ]; then
      echo "Aborted."
      exit 0
    fi

    echo "Cloning (this may take several minutes)..."
    gcloud sql instances clone "${INSTANCE}" "${CLONE_INSTANCE}" \
      --point-in-time="${VALUE}" \
      --quiet

    echo ""
    echo "=== PITR clone complete ==="
    echo "Clone instance: ${CLONE_INSTANCE}"
    echo ""
    echo "Next steps:"
    echo "  1. Verify data: gcloud sql connect ${CLONE_INSTANCE} --user=emai-user --database=emai"
    echo "  2. If good, update DATABASE_URL secret to point to ${CLONE_INSTANCE}"
    echo "  3. Delete old instance when ready: gcloud sql instances delete ${INSTANCE}"
    echo "  4. Or export from clone and import to original instance"
    ;;
esac
