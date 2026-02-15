# Disaster Recovery Runbook

ClassBridge production database backup and recovery procedures.

## Recovery Targets

| Metric | Target | How |
|--------|--------|-----|
| **RPO** (Recovery Point Objective) | < 24 hours | Automated daily backups at 2 AM UTC |
| **RPO with PITR** | < 5 minutes | Point-in-time recovery from transaction logs (7-day window) |
| **RTO** (Recovery Time Objective) | < 1 hour | Restore from automated backup or PITR clone |

## Backup Inventory

| Type | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| Automated backup | Daily at 2 AM UTC | 7 days | Cloud SQL internal |
| Transaction logs (PITR) | Continuous | 7 days | Cloud SQL internal |
| Manual GCS export | On demand | 90 days | `gs://emai-dev-01-db-backups/manual/` |

## Infrastructure

- **Project:** `emai-dev-01`
- **Region:** `us-central1`
- **Instance:** `emai-db` (PostgreSQL 15)
- **Database:** `emai`
- **User:** `emai-user`
- **GCS bucket:** `gs://emai-dev-01-db-backups`
- **Cloud Run service:** `classbridge`

## Encryption

- **At rest:** Enabled by default (Google-managed encryption keys)
- **In transit:** Cloud SQL Proxy via `--add-cloudsql-instances` (no public IP exposed)

---

## Initial Setup

Run once to enable backups and create the GCS bucket:

```bash
./scripts/backup/configure-backups.sh
```

Deploy the backup failure alert:

```bash
gcloud alpha monitoring policies create \
  --policy-from-file=scripts/monitoring/backup-alert-policy.json \
  --project=emai-dev-01
```

## Verify Backups Are Working

```bash
# Check backup configuration
gcloud sql instances describe emai-db --project=emai-dev-01 \
  --format="yaml(settings.backupConfiguration)"

# List recent automated backups
gcloud sql backups list --instance=emai-db --project=emai-dev-01 --limit=10

# List manual GCS exports
gsutil ls -l gs://emai-dev-01-db-backups/manual/
```

---

## Recovery Scenarios

### Scenario 1: Accidental Data Deletion (single table/rows)

**Best approach:** PITR clone to just before the deletion, then export the affected data.

```bash
# 1. Clone to a point in time before the deletion
./scripts/backup/restore-from-backup.sh --pitr "2026-02-15T10:00:00Z"

# 2. Connect to the clone and export the needed data
gcloud sql connect emai-db-pitr-20260215143022 --user=emai-user --database=emai

# 3. Copy the data back to production (via pg_dump/pg_restore or application-level)

# 4. Delete the clone when done
gcloud sql instances delete emai-db-pitr-20260215143022 --quiet
```

### Scenario 2: Instance Failure / Corruption

**Best approach:** Restore from the most recent automated backup.

```bash
# 1. List available backups
gcloud sql backups list --instance=emai-db --project=emai-dev-01

# 2. Restore (note the backup ID from step 1)
./scripts/backup/restore-from-backup.sh --from-backup <BACKUP_ID>

# 3. Verify the instance is running
gcloud sql instances describe emai-db --format='value(state)'

# 4. Verify the application works
curl -s https://classbridge-924827764032.us-central1.run.app/health
```

### Scenario 3: Restore from GCS Export

**Use when:** Automated backups are unavailable or you need to restore a specific labeled export.

```bash
# 1. List available exports
gsutil ls -l gs://emai-dev-01-db-backups/manual/

# 2. Import the export
./scripts/backup/restore-from-backup.sh --from-gcs gs://emai-dev-01-db-backups/manual/emai-20260215-143022.sql.gz

# 3. Verify
curl -s https://classbridge-924827764032.us-central1.run.app/health
```

### Scenario 4: Full Disaster (instance deleted)

```bash
# 1. Recreate the Cloud SQL instance
gcloud sql instances create emai-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --project=emai-dev-01

# 2. Create the database and user
gcloud sql databases create emai --instance=emai-db
gcloud sql users create emai-user --instance=emai-db --password=<PASSWORD>

# 3. Import from the most recent GCS export
./scripts/backup/restore-from-backup.sh --from-gcs gs://emai-dev-01-db-backups/manual/<LATEST_EXPORT>

# 4. Update DATABASE_URL secret if the connection string changed
gcloud secrets versions add DATABASE_URL --data-file=-

# 5. Redeploy Cloud Run to pick up the new instance
gcloud run deploy classbridge --image us-central1-docker.pkg.dev/emai-dev-01/classbridge/classbridge:latest \
  --region=us-central1 --add-cloudsql-instances=emai-dev-01:us-central1:emai-db

# 6. Re-run backup configuration
./scripts/backup/configure-backups.sh
```

---

## Pre-Deployment Backup

Before major migrations or deployments, create a labeled manual backup:

```bash
./scripts/backup/manual-backup.sh pre-migration
```

## Monthly Verification Checklist

- [ ] Confirm automated backups are running: `gcloud sql backups list --instance=emai-db --limit=7`
- [ ] Verify PITR is enabled: `gcloud sql instances describe emai-db --format="value(settings.backupConfiguration.pointInTimeRecoveryEnabled)"`
- [ ] Check GCS bucket has recent exports (if manual exports are being taken)
- [ ] Test a PITR clone to verify data integrity, then delete the clone
- [ ] Review backup alert policy is still active

## Contacts

- **GCP Project Owner:** Check `gcloud projects get-iam-policy emai-dev-01`
- **Notification Channel:** Configured in GCP Monitoring (channel ID: `6195366348465449860`)
