# M2 Parent Email Digest — Test Plan

**Feature:** CB-PEDI-001 M2 (Core Engine)
**PR:** #2985
**Date:** 2026-04-10

---

## 1. Email Digest Page (Frontend)

Go to **https://www.classbridge.ca/email-digest** while logged in as a parent.

- Empty state: "No Email Digest Set Up" message + "Go to My Kids" button
- If Gmail integration exists from M1: settings card + digest history

## 2. Gmail OAuth Flow (Existing M1)

1. Go to **My Kids** page
2. Use the email digest setup wizard to connect your Gmail
3. As GCP project owner, you can consent without test mode restrictions
4. Enter your child's school email address (the one that forwards to your Gmail)

## 3. Forwarding Verification

After connecting Gmail:

```
POST /api/parent/email-digest/integrations/{id}/verify-forwarding
```

Or use the **Sync Now** button on the Email Digest page.

To test this, you need at least 1 email from the child's school email in your Gmail inbox (last 30 days).

## 4. Manual Sync + AI Digest

1. Make sure your Gmail has some forwarded school emails
2. Click **Sync Now** on `/email-digest`
3. This calls `fetch_child_emails` -> polls Gmail -> returns count
4. The scheduled job (every 4 hours) handles the full flow: poll -> AI summarize -> notify

**To trigger a full digest manually (API call):**

```bash
# Get your integration ID first
curl -H "Authorization: Bearer <token>" https://www.classbridge.ca/api/parent/email-digest/integrations

# Trigger sync
curl -X POST -H "Authorization: Bearer <token>" https://www.classbridge.ca/api/parent/email-digest/integrations/<id>/sync
```

## 5. WhatsApp (Requires Twilio Setup)

WhatsApp won't work until you add Twilio credentials to the environment:

```env
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=+14155238886   # Twilio sandbox number
```

**To test with Twilio Sandbox (free):**

1. Go to https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
2. Join the sandbox by sending "join <word>" to the sandbox number from your WhatsApp
3. Add the 3 env vars to your Cloud Run service
4. Then test OTP flow:
   - Send OTP: `POST /api/parent/email-digest/integrations/{id}/whatsapp/send-otp` with `{"phone": "+1XXXXXXXXXX"}`
   - You'll receive the OTP on WhatsApp
   - Verify: `POST /api/parent/email-digest/integrations/{id}/whatsapp/verify-otp` with `{"otp_code": "123456"}`

## 6. Quickest Smoke Test (No School Emails Needed)

1. Log in as parent at classbridge.ca
2. Visit `/email-digest` -> verify empty state renders
3. Connect Gmail via My Kids setup wizard
4. Visit `/email-digest` again -> verify settings card appears
5. Toggle digest enabled on/off
6. Change delivery time
7. Click Sync Now -> should show "Synced 0 emails" (if no matching emails)

## 7. Scheduled Job Verification

The digest job runs every 4 hours via APScheduler. To verify it's registered:

```bash
# Check Cloud Run logs for the job
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="classbridge" AND textPayload=~"parent email digest"' --project=emai-dev-01 --limit=10 --format=json --freshness=1d
```

## 8. API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/parent/email-digest/integrations` | List all integrations |
| GET | `/api/parent/email-digest/integrations/{id}` | Get integration |
| PATCH | `/api/parent/email-digest/integrations/{id}` | Update integration |
| DELETE | `/api/parent/email-digest/integrations/{id}` | Delete integration |
| POST | `/api/parent/email-digest/integrations/{id}/pause` | Pause digest |
| POST | `/api/parent/email-digest/integrations/{id}/resume` | Resume digest |
| POST | `/api/parent/email-digest/integrations/{id}/sync` | Manual sync |
| POST | `/api/parent/email-digest/integrations/{id}/verify-forwarding` | Verify forwarding |
| GET | `/api/parent/email-digest/settings/{id}` | Get digest settings |
| PUT | `/api/parent/email-digest/settings/{id}` | Update settings |
| GET | `/api/parent/email-digest/logs` | List delivery logs |
| GET | `/api/parent/email-digest/logs/{id}` | Get delivery log |
| POST | `/api/parent/email-digest/integrations/{id}/whatsapp/send-otp` | Send WhatsApp OTP |
| POST | `/api/parent/email-digest/integrations/{id}/whatsapp/verify-otp` | Verify WhatsApp OTP |
| DELETE | `/api/parent/email-digest/integrations/{id}/whatsapp` | Disconnect WhatsApp |
