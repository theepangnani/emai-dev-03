# March 6 Pilot Launch: Go-Live Checklist

ClassBridge March 6, 2026 pilot launch day procedures.

## Pre-Launch (Mar 5 Evening)

- [ ] Final web smoke test on production URL — all four roles log in
- [ ] Final mobile test on ClassBridge app (iOS + Android) — parent login and navigation
- [ ] All pilot user accounts verified (see [deploy-freeze.md](deploy-freeze.md#pilot-account-verification-mar-4-5))
- [ ] Demo data in place (assignments, messages, notifications)
- [ ] Pre-launch backup taken: `./scripts/backup/manual-backup.sh pre-launch`
- [ ] Alert policies active (see [INCIDENT_RESPONSE.md](../INCIDENT_RESPONSE.md#active-alert-policies))
- [ ] Welcome emails drafted and ready to send
- [ ] Mobile app download links ready to share (from EAS dashboard)

## Launch Morning (Mar 6)

### Verify Services

- [ ] Health check passes: `curl -s https://www.classbridge.ca/health`
- [ ] Web app loads at https://www.classbridge.ca
- [ ] Cloud SQL is RUNNABLE: `gcloud sql instances describe emai-db --project=emai-dev-01 --format="value(state)"`
- [ ] No errors in logs:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=classbridge AND severity>=ERROR" \
    --project=emai-dev-01 --limit=10
  ```

### Verify All Roles

- [ ] **Parent** — log in on web, see dashboard with children and assignments
- [ ] **Student** — log in on web, see courses and study tools
- [ ] **Teacher** — log in on web, see courses and messages
- [ ] **Admin** — log in on web, see system overview
- [ ] **Parent (mobile)** — log in via ClassBridge app, navigate all tabs

### Send Communications

- [ ] Send welcome emails to pilot parents (see [welcome-email.md](welcome-email.md))
- [ ] Send welcome emails to pilot teachers and students
- [ ] Share mobile app download links with pilot parents (see [mobile-setup-instructions.md](mobile-setup-instructions.md))

### Monitor

- [ ] Open Cloud Run metrics dashboard (request count, latency, error rate)
- [ ] Open Cloud SQL metrics dashboard (connections, CPU, memory)
- [ ] Check alerts page for any triggered alerts
- [ ] Support contact designated and available

See [INCIDENT_RESPONSE.md](../INCIDENT_RESPONSE.md#monitoring-dashboard-checklist-launch-day) for full monitoring procedures.

## What Goes Live

### Web — Full ClassBridge

| Feature | Status |
|---------|--------|
| All roles (parent, student, teacher, admin) | Active |
| Google Classroom sync | Active |
| AI study tools (guides, quizzes, flashcards) | Active |
| Parent-teacher messaging | Active |
| Assignment tracking and notifications | Active |
| Cloud SQL with automated backups | Active |
| Monitoring and alerting | Active |

### Mobile — Parent-Only App (EAS Development Build)

| Feature | Status |
|---------|--------|
| Login, Dashboard, Child Overview | Available |
| Calendar, Messages, Chat | Available |
| Notifications, Profile | Available |
| OTA updates via EAS Update | Available |
| Push notifications | Not available (in-app polling only) |
| File upload, Google OAuth, course management | Not available (use web) |

## Known Limitations to Communicate

Share these with pilot participants in welcome emails and setup instructions:

- [ ] Mobile app is **parent-only** — students and teachers use the web app
- [ ] Mobile app is distributed via **direct download link** (not on App Store / Google Play yet)
- [ ] **No push notifications** — open the app to check for updates (auto-refreshes every 30s)
- [ ] Account setup, child management, starting new conversations, study materials — **use the web app**

## If Something Goes Wrong

| Severity | Action |
|----------|--------|
| **P1 — Service down** | Follow [Incident Response](../INCIDENT_RESPONSE.md#p1-service-down) procedures immediately |
| **P2 — Major feature broken** | Fix and push, or rollback. See [Incident Response](../INCIDENT_RESPONSE.md#p2-major-feature-broken) |
| **P3/P4 — Minor issue** | Log in GitHub Issues, fix after launch |

Hotfix procedure: [deploy-freeze.md](deploy-freeze.md#hotfix-plan)

## Post-Launch (Mar 6 Afternoon)

- [ ] Confirm all pilot participants received welcome emails
- [ ] Confirm at least one parent successfully logged in via mobile
- [ ] Review Cloud Run metrics — no elevated error rates
- [ ] Review Cloud SQL metrics — no connection issues
- [ ] Check GitHub Issues for any reported bugs
- [ ] Send "launch successful" status update to stakeholders

## Dependencies

All `#march-6-pilot` issues must be complete before launch. Verify:

```bash
gh issue list --label march-6-pilot --state open
```

If any remain open, assess whether they are blockers or can be deferred.

## Related Documents

- [Deploy Freeze](deploy-freeze.md) — Freeze rules, dress rehearsal, hotfix plan
- [Incident Response](../INCIDENT_RESPONSE.md) — Monitoring and incident handling
- [Disaster Recovery](../DISASTER_RECOVERY.md) — Backup and restore procedures
- [Quick-Start Guide](quick-start-guide.md) — Parent-facing setup instructions
- [Mobile Setup Instructions](mobile-setup-instructions.md) — App download and setup for parents
- [Welcome Email](welcome-email.md) — Email templates for pilot participants
- [Device Testing Checklist](device-testing-checklist.md) — iOS and Android testing procedures
