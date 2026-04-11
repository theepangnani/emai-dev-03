#!/bin/bash
# ============================================================
# ClassBridge Database Switch Script
# Switch between Cloud SQL and GCE self-hosted Postgres
# ============================================================
#
# Usage:
#   ./scripts/switch-db.sh cloudsql    # Switch to Cloud SQL
#   ./scripts/switch-db.sh gce         # Switch to GCE Postgres
#   ./scripts/switch-db.sh status      # Show current config
#
# What it does:
#   1. Updates DATABASE_URL secret in Secret Manager
#   2. Updates Cloud Run service (adds/removes Cloud SQL proxy)
#   3. Redeploys with the new config
#
# Prerequisites:
#   - gcloud CLI authenticated
#   - Appropriate secrets already created in Secret Manager
# ============================================================

set -euo pipefail

PROJECT="emai-dev-01"
REGION="us-central1"
SERVICE="classbridge"
CLOUD_SQL_INSTANCE="${PROJECT}:${REGION}:emai-db"

# Secret names in Secret Manager
# DATABASE_URL contains the active connection string
# DATABASE_URL_CLOUDSQL contains the Cloud SQL connection string (backup)
# DATABASE_URL_GCE contains the GCE Postgres connection string (backup)
SECRET_ACTIVE="DATABASE_URL"
SECRET_CLOUDSQL="DATABASE_URL_CLOUDSQL"
SECRET_GCE="DATABASE_URL_GCE"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

show_status() {
    echo "=== ClassBridge Database Status ==="
    echo ""

    # Get current DATABASE_URL (masked)
    CURRENT_URL=$(gcloud secrets versions access latest --secret="$SECRET_ACTIVE" --project="$PROJECT" 2>/dev/null || echo "NOT SET")
    if [[ "$CURRENT_URL" == *"cloudsql"* ]] || [[ "$CURRENT_URL" == *"/cloudsql/"* ]]; then
        echo -e "Active database: ${GREEN}Cloud SQL${NC}"
        echo "  Connection: via Cloud SQL Auth Proxy (Unix socket)"
    elif [[ "$CURRENT_URL" == *"NOT SET"* ]]; then
        echo -e "Active database: ${RED}NOT CONFIGURED${NC}"
    else
        echo -e "Active database: ${YELLOW}GCE Self-Hosted Postgres${NC}"
        # Extract host (mask password)
        HOST=$(echo "$CURRENT_URL" | sed -E 's|.*@([^:/]+).*|\1|')
        echo "  Host: $HOST"
    fi
    echo ""

    # Check Cloud SQL instance status
    echo "--- Cloud SQL Instance ---"
    SQL_STATUS=$(gcloud sql instances describe emai-db --project="$PROJECT" --format="value(state)" 2>/dev/null || echo "NOT FOUND")
    ACTIVATION=$(gcloud sql instances describe emai-db --project="$PROJECT" --format="value(settings.activationPolicy)" 2>/dev/null || echo "N/A")
    echo "  Status: $SQL_STATUS"
    echo "  Activation policy: $ACTIVATION"
    echo ""

    # Check GCE VM status
    echo "--- GCE VM (classbridge-db) ---"
    VM_STATUS=$(gcloud compute instances describe classbridge-db --zone="${REGION}-c" --project="$PROJECT" --format="value(status)" 2>/dev/null || echo "NOT FOUND")
    if [[ "$VM_STATUS" != "NOT FOUND" ]]; then
        VM_IP=$(gcloud compute instances describe classbridge-db --zone="${REGION}-c" --project="$PROJECT" --format="value(networkInterfaces[0].networkIP)" 2>/dev/null || echo "N/A")
        echo "  Status: $VM_STATUS"
        echo "  Internal IP: $VM_IP"
    else
        echo "  Status: NOT PROVISIONED"
    fi
    echo ""

    # Check Cloud Run config
    echo "--- Cloud Run Service ---"
    CLOUDSQL_ANNOTATION=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" \
        --format="value(spec.template.metadata.annotations['run.googleapis.com/cloudsql-instances'])" 2>/dev/null || echo "NONE")
    MIN_INSTANCES=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT" \
        --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>/dev/null || echo "N/A")
    echo "  Cloud SQL proxy: ${CLOUDSQL_ANNOTATION:-NONE}"
    echo "  Min instances: $MIN_INSTANCES"
}

switch_to_cloudsql() {
    echo "=== Switching to Cloud SQL ==="
    echo ""

    # Verify Cloud SQL instance exists and is running
    SQL_STATUS=$(gcloud sql instances describe emai-db --project="$PROJECT" --format="value(state)" 2>/dev/null || echo "NOT FOUND")
    if [[ "$SQL_STATUS" == "NOT FOUND" ]]; then
        error "Cloud SQL instance 'emai-db' not found. Create it first."
    fi

    # Start Cloud SQL if stopped
    ACTIVATION=$(gcloud sql instances describe emai-db --project="$PROJECT" --format="value(settings.activationPolicy)" 2>/dev/null)
    if [[ "$ACTIVATION" == "NEVER" ]]; then
        warn "Cloud SQL instance is stopped. Starting it..."
        gcloud sql instances patch emai-db --activation-policy=ALWAYS --project="$PROJECT" --quiet
        log "Cloud SQL instance starting (may take 1-2 minutes)"
        echo "  Waiting for instance to be ready..."
        sleep 30
    fi

    # Get the Cloud SQL DATABASE_URL
    CLOUDSQL_URL=$(gcloud secrets versions access latest --secret="$SECRET_CLOUDSQL" --project="$PROJECT" 2>/dev/null || echo "")
    if [[ -z "$CLOUDSQL_URL" ]]; then
        error "Secret '$SECRET_CLOUDSQL' not found. Create it with the Cloud SQL connection string first:\n  gcloud secrets create $SECRET_CLOUDSQL --data-file=- --project=$PROJECT <<< 'postgresql+psycopg2://user:pass@/dbname?host=/cloudsql/$CLOUD_SQL_INSTANCE'"
    fi

    # Update active DATABASE_URL
    echo "$CLOUDSQL_URL" | gcloud secrets versions add "$SECRET_ACTIVE" --data-file=- --project="$PROJECT" --quiet
    log "Updated DATABASE_URL secret to Cloud SQL connection string"

    # Update Cloud Run: add Cloud SQL proxy
    gcloud run services update "$SERVICE" \
        --add-cloudsql-instances="$CLOUD_SQL_INSTANCE" \
        --region="$REGION" \
        --project="$PROJECT" \
        --quiet
    log "Cloud Run updated with Cloud SQL proxy annotation"

    echo ""
    log "Switched to Cloud SQL successfully!"
    warn "Next deploy will use Cloud SQL. If you need immediate effect, redeploy:\n  gcloud run services update $SERVICE --region=$REGION --project=$PROJECT --image=\$(gcloud run services describe $SERVICE --region=$REGION --project=$PROJECT --format='value(spec.template.spec.containers[0].image)')"
}

switch_to_gce() {
    echo "=== Switching to GCE Self-Hosted Postgres ==="
    echo ""

    # Verify GCE VM exists and is running
    VM_STATUS=$(gcloud compute instances describe classbridge-db --zone="${REGION}-c" --project="$PROJECT" --format="value(status)" 2>/dev/null || echo "NOT FOUND")
    if [[ "$VM_STATUS" == "NOT FOUND" ]]; then
        error "GCE VM 'classbridge-db' not found. Provision it first (see GitHub issue #3097)."
    fi
    if [[ "$VM_STATUS" != "RUNNING" ]]; then
        warn "GCE VM is $VM_STATUS. Starting it..."
        gcloud compute instances start classbridge-db --zone="${REGION}-c" --project="$PROJECT" --quiet
        log "GCE VM starting..."
        sleep 15
    fi

    # Get the GCE DATABASE_URL
    GCE_URL=$(gcloud secrets versions access latest --secret="$SECRET_GCE" --project="$PROJECT" 2>/dev/null || echo "")
    if [[ -z "$GCE_URL" ]]; then
        VM_IP=$(gcloud compute instances describe classbridge-db --zone="${REGION}-c" --project="$PROJECT" --format="value(networkInterfaces[0].networkIP)" 2>/dev/null)
        error "Secret '$SECRET_GCE' not found. Create it with the GCE connection string first:\n  gcloud secrets create $SECRET_GCE --data-file=- --project=$PROJECT <<< 'postgresql+psycopg2://classbridge:PASSWORD@${VM_IP}:5432/classbridge_db'"
    fi

    # Update active DATABASE_URL
    echo "$GCE_URL" | gcloud secrets versions add "$SECRET_ACTIVE" --data-file=- --project="$PROJECT" --quiet
    log "Updated DATABASE_URL secret to GCE Postgres connection string"

    # Update Cloud Run: remove Cloud SQL proxy (saves a tiny bit of overhead)
    gcloud run services update "$SERVICE" \
        --remove-cloudsql-instances \
        --region="$REGION" \
        --project="$PROJECT" \
        --quiet
    log "Cloud Run updated — Cloud SQL proxy removed"

    # Optionally stop Cloud SQL to save money
    echo ""
    read -p "Stop Cloud SQL instance to save ~\$15/month? (y/N): " STOP_SQL
    if [[ "$STOP_SQL" =~ ^[Yy]$ ]]; then
        gcloud sql instances patch emai-db --activation-policy=NEVER --project="$PROJECT" --quiet
        log "Cloud SQL instance stopped"
    else
        warn "Cloud SQL instance left running. Stop it manually when ready:\n  gcloud sql instances patch emai-db --activation-policy=NEVER --project=$PROJECT"
    fi

    echo ""
    log "Switched to GCE Postgres successfully!"
    warn "Next deploy will use GCE Postgres. If you need immediate effect, redeploy:\n  gcloud run services update $SERVICE --region=$REGION --project=$PROJECT --image=\$(gcloud run services describe $SERVICE --region=$REGION --project='$PROJECT' --format='value(spec.template.spec.containers[0].image)')"
}

# --- Main ---
case "${1:-}" in
    cloudsql|cloud-sql|sql)
        switch_to_cloudsql
        ;;
    gce|vm|self-hosted)
        switch_to_gce
        ;;
    status|info)
        show_status
        ;;
    *)
        echo "ClassBridge Database Switch"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  cloudsql    Switch to Cloud SQL (managed, ~\$15/month)"
        echo "  gce         Switch to GCE self-hosted Postgres (~\$0-3/month)"
        echo "  status      Show current database configuration"
        echo ""
        echo "Secrets required in Secret Manager:"
        echo "  DATABASE_URL          — active connection string (updated by this script)"
        echo "  DATABASE_URL_CLOUDSQL — Cloud SQL connection string (reference copy)"
        echo "  DATABASE_URL_GCE      — GCE Postgres connection string (reference copy)"
        exit 1
        ;;
esac
