# Launch Day: Monitoring & Incident Response Plan

ClassBridge March 6, 2026 pilot launch.

## Quick Reference

| Resource | URL / Command |
|----------|---------------|
| **App** | https://classbridge-924827764032.us-central1.run.app |
| **Health** | https://classbridge-924827764032.us-central1.run.app/health |
| **GCP Console** | https://console.cloud.google.com/run/detail/us-central1/classbridge?project=emai-dev-01 |
| **Logs** | See "Log Commands" below |
| **Alerts** | GCP Monitoring → Alerting (5xx, latency, uptime policies active) |
| **DB Backups** | See `docs/DISASTER_RECOVERY.md` |

## Active Alert Policies

| Alert | Trigger | Notification |
|-------|---------|--------------|
| 5xx Error Rate | Any 5xx in 5-min window | Email (notification channel) |
| High Latency | p99 > 5s for 5 min | Email |
| Uptime Check | Health endpoint fails | Email |
| Backup Failure | Cloud SQL backup fails | Email |

Deploy alert policies (if not already done):
```bash
for f in scripts/monitoring/*.json; do
  gcloud alpha monitoring policies create --policy-from-file="$f" --project=emai-dev-01
done
```

## Log Commands

```bash
# Recent errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=classbridge AND severity>=ERROR" \
  --project=emai-dev-01 --limit=20 --format="table(timestamp,severity,textPayload)"

# All recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=classbridge" \
  --project=emai-dev-01 --limit=50

# Filter by time window (e.g. last 30 minutes)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=classbridge AND severity>=WARNING AND timestamp>=\"$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%SZ)\"" \
  --project=emai-dev-01 --limit=50

# Database connection errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=classbridge AND textPayload=~\"database|connection|sqlalchemy\"" \
  --project=emai-dev-01 --limit=20
```

Windows (PowerShell):
```powershell
& 'C:\apps\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' logging read "resource.type=cloud_run_revision AND resource.labels.service_name=classbridge AND severity>=ERROR" --project=emai-dev-01 --limit=20
```

## Monitoring Dashboard Checklist (Launch Day)

Open these tabs and check every 15-30 minutes:

- [ ] **Cloud Run metrics:** Request count, latency, error rate, instance count
      → GCP Console → Cloud Run → classbridge → Metrics tab
- [ ] **Cloud SQL metrics:** Connections, CPU, memory, disk
      → GCP Console → SQL → emai-db → Overview
- [ ] **Alerts:** Check for any triggered alerts
      → GCP Console → Monitoring → Alerting
- [ ] **Health endpoint:** `curl -s https://classbridge-924827764032.us-central1.run.app/health`

## Incident Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| **P1 — Critical** | Service is down or data loss | Immediate | App returns 500, DB unreachable |
| **P2 — High** | Major feature broken | < 30 min | Login fails, messages not sending |
| **P3 — Medium** | Minor feature broken | < 2 hours | Notification badge wrong, UI glitch |
| **P4 — Low** | Cosmetic / non-blocking | Next day | Typo, alignment issue |

## Incident Response Procedures

### P1: Service Down

1. **Verify:** `curl -s https://classbridge-924827764032.us-central1.run.app/health`
2. **Check logs:** Run the error log command above
3. **Check Cloud Run:** Is the instance running? Check GCP Console
4. **Rollback** if a recent deploy caused it:
   ```bash
   # List revisions
   gcloud run revisions list --service=classbridge --region=us-central1 --project=emai-dev-01

   # Route 100% traffic to previous working revision
   gcloud run services update-traffic classbridge \
     --to-revisions=REVISION_NAME=100 \
     --region=us-central1 --project=emai-dev-01
   ```
5. **DB down?** Check Cloud SQL instance status:
   ```bash
   gcloud sql instances describe emai-db --project=emai-dev-01 --format="value(state)"
   ```
6. **Notify stakeholders** immediately

### P2: Major Feature Broken

1. Check error logs for the affected endpoint
2. Attempt a fix → test locally → push (CI will test + deploy)
3. If fix is not quick, rollback to previous revision
4. Notify affected users if needed

### P3/P4: Minor Issues

1. Log the issue in GitHub Issues
2. Fix in next deploy cycle
3. No rollback needed

## Rollback Procedure

```bash
# 1. List recent revisions (most recent first)
gcloud run revisions list --service=classbridge \
  --region=us-central1 --project=emai-dev-01 --limit=5

# 2. Route all traffic to the last known good revision
gcloud run services update-traffic classbridge \
  --to-revisions=<GOOD_REVISION>=100 \
  --region=us-central1 --project=emai-dev-01

# 3. Verify
curl -s https://classbridge-924827764032.us-central1.run.app/health
```

To restore normal deployment after fixing the issue:
```bash
# Push the fix, let CI deploy, then route traffic to latest
gcloud run services update-traffic classbridge \
  --to-latest --region=us-central1 --project=emai-dev-01
```

## Pre-Launch Manual Backup

Run before launch day to ensure a clean restore point:
```bash
./scripts/backup/manual-backup.sh pre-launch
```

## Communication Plan

| Channel | Use For |
|---------|---------|
| **Email** | Alert notifications (auto via GCP Monitoring) |
| **GitHub Issues** | Bug tracking and incident post-mortems |
| **Direct contact** | P1/P2 escalation to project owner |

## Post-Incident

After resolving any P1/P2 incident:
1. Create a GitHub Issue with label `incident` documenting what happened
2. Root cause analysis (what failed, why, how it was fixed)
3. Action items to prevent recurrence
4. Update this runbook if procedures need adjustment
