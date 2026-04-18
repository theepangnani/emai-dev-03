# WhatsApp Integration Setup Guide — ClassBridge

This document captures the complete setup process for WhatsApp Business integration via Twilio, as performed on April 17-18, 2026.

---

## Table of Contents

1. [Overview](#overview)
2. [Twilio Account Setup](#twilio-account-setup)
3. [WhatsApp Sandbox (Testing)](#whatsapp-sandbox-testing)
4. [Production Setup](#production-setup)
5. [Meta WhatsApp Business Registration](#meta-whatsapp-business-registration)
6. [Domain Verification](#domain-verification)
7. [Meta Business Verification](#meta-business-verification)
8. [Message Templates](#message-templates)
9. [Cloud Run Configuration](#cloud-run-configuration)
10. [Deploy Workflow](#deploy-workflow)
11. [Code Architecture](#code-architecture)
12. [Testing](#testing)
13. [Maintenance & Troubleshooting](#maintenance--troubleshooting)
14. [Related GitHub Issues](#related-github-issues)

---

## Overview

ClassBridge uses Twilio's WhatsApp Business API to deliver parent email digest summaries via WhatsApp. The integration supports two modes:

- **Content API (production):** Uses Twilio Content SID + variables for proper template invocation outside the 24-hour session window
- **Body-text fallback:** Sends freeform messages matching the template text (works in sandbox and within session windows)

### Key Credentials

| Item | Value |
|------|-------|
| Twilio Account SID | `ACbf7497fc27cd1d588cb30a6aba30d748` |
| WhatsApp Production Number | +1 647-800-8533 |
| WhatsApp Sandbox Number | +1 415-523-8886 |
| Sandbox Join Code | `join toward-master` |
| Daily Digest Content SID | `HX5fb1ebf94a75f33d1f88a2955f5f7234` |
| Meta Business Account | Class Bridge Inc. |
| Facebook Admin | Theepan Gnani (personal account) |

---

## Twilio Account Setup

### Step 1: Create Twilio Account

1. Go to [twilio.com](https://www.twilio.com) and sign up
2. Account details:
   - **Account friendly name:** `classbridge`
   - **Account type:** Twilio (SMS, Voice, Verify, Lookup)
3. Onboarding selections:
   - **Business type:** Business
   - **Kind of business:** Direct brand
   - **Role:** Business owner or director
   - **Build approach:** With code
   - **Use case:** Notifications
   - **Channel:** WhatsApp

### Step 2: Upgrade from Trial

1. Go to Twilio Console -> click **Upgrade** (top bar shows "Trial: $15.50 Upgrade")
2. Enter your legal name (as on government ID) — this is for account verification, not branding
3. Add payment method (credit card)
4. Trial vs. Production differences:

| Feature | Trial (Free) | Production (Paid) |
|---------|-------------|-------------------|
| Sandbox duration | 72 hours, must re-join | Permanent |
| Recipients | Only sandbox participants | Anyone |
| Sender number | Shared (+14155238886) | Your own branded number |
| Message prefix | "Sent from Twilio trial" | None |
| Cost | Free (trial credit) | ~$0.005-0.08/message |

### Step 3: Buy a Phone Number

1. Go to **Phone Numbers** -> **Buy a number**
2. Search for a Canadian (+1) number (~$1.15/month)
3. Ensure the number has **SMS** and **Voice** capabilities
4. ClassBridge number: **(647) 800-8533**

---

## WhatsApp Sandbox (Testing)

The sandbox is useful for development testing without needing Meta approval.

### Setup

1. Go to Twilio Console -> **Messaging** -> **Try it out** -> **Send a WhatsApp message**
2. Note the sandbox number and join code (e.g., `join toward-master`)
3. On your phone, open WhatsApp and send the join code to the sandbox number (+1 415-523-8886)
4. Wait for confirmation: "You are all set! The sandbox can now send/receive messages"

### Local Environment

Add to `.env`:
```
TWILIO_ACCOUNT_SID=ACbf7497fc27cd1d588cb30a6aba30d748
TWILIO_AUTH_TOKEN=<your-auth-token>
TWILIO_WHATSAPP_FROM=+14155238886   # sandbox number
```

### Test Script

Use `scripts/test_whatsapp.py` to verify the connection:
```bash
python scripts/test_whatsapp.py +1YOURNUMBER
```

### Important Notes

- Sandbox membership lasts **72 hours** — re-send the join code to reconnect
- Only users who have sent the join code can receive messages
- The sandbox number is shared across all Twilio users

---

## Production Setup

### Phone Number Configuration

After buying a number, configure it for WhatsApp:

1. Go to **Phone Numbers** -> **Active Numbers** -> click your number
2. **Voice Configuration:**
   - Clear the "A call comes in" webhook URL (remove `demo.twilio.com` default)
   - Optionally set up call forwarding via TwiML Bin for verification calls
3. **Messaging Configuration:**
   - Clear the "A message comes in" webhook URL (remove `demo.twilio.com` default)
   - Optionally set up SMS forwarding via TwiML Bin

### Call/SMS Forwarding (for verification)

To receive Meta verification calls/SMS on your personal phone:

1. Go to **TwiML Bins** (search in "Jump to..." bar)
2. Create a new TwiML Bin:
   - **Name:** `Forward to my phone`
   - **Body (for voice):**
     ```xml
     <?xml version="1.0" encoding="UTF-8"?>
     <Response><Dial>+1YOURPERSONALNUMBER</Dial></Response>
     ```
   - **Body (for SMS):**
     ```xml
     <?xml version="1.0" encoding="UTF-8"?>
     <Response><Message to="+1YOURPERSONALNUMBER">{{Body}}</Message></Response>
     ```
3. Assign TwiML Bins to the phone number's Voice/Messaging configuration

---

## Meta WhatsApp Business Registration

### Step 1: Register WhatsApp Sender

1. Go to Twilio Console -> **Messaging** -> **WhatsApp senders**
2. Click **Create new sender**
3. Click **Continue with Facebook** (opens Meta popup)
4. Log in with your **personal Facebook account** (required by Meta, won't post anything)
5. Create or select a **WhatsApp Business Account**:
   - Business name: `Class Bridge Inc.`
   - Display name: `Class Bridge`
   - Category: `Education`
   - Website: `https://www.classbridge.ca/`
6. Register your phone number (+1 647-800-8533)
7. Verify via **Phone call** or **Text message**
   - Verification code appears in Twilio's **Calls Log** or **Messages Log** for your number
   - If using TwiML Bin forwarding, the code forwards to your personal phone

### Verification Troubleshooting

- **SMS not arriving:** Check Messages Log tab, ensure webhook URL isn't pointing to `demo.twilio.com`
- **Rate limited ("requested too many times"):** Wait 15-30 minutes before retrying
- **Phone call verification:** Better success rate than SMS for Twilio virtual numbers
- **Set up TwiML Bin forwarding** to receive codes on your personal phone

---

## Domain Verification

### Step 1: Add Meta Tag

Add the Facebook domain verification meta tag to `frontend/index.html`:

```html
<meta name="facebook-domain-verification" content="q2p3bt82xxvwygqtiq97y4afrovhgi" />
```

Place it inside the `<head>` section, before `<title>`.

### Step 2: Deploy

Merge the change to master and deploy to Cloud Run. Verify the tag is live:

```bash
curl -sL https://www.classbridge.ca/ | grep "facebook-domain-verification"
```

### Step 3: Verify in Meta

1. Go to Meta Business Suite -> **Settings** -> **Brand safety** -> **Domains**
2. Click **+ Add** -> **Create a domain** -> enter `classbridge.ca`
3. Click **Verify domain**

### Traffic Routing

After deploy, ensure Cloud Run serves the latest revision:
```bash
gcloud run services update-traffic classbridge --to-latest --project=emai-dev-01 --region=us-central1
```

---

## Meta Business Verification

Required for: sending to any WhatsApp user (not just sandbox), creating authentication templates, higher messaging limits.

### Step 1: Submit Verification

1. Go to Meta Business Suite -> **Settings** -> **Security Center** -> **Business Verification**
2. Provide:
   - **Legal business name:** Class Bridge Inc.
   - **Alternative name:** ClassBridge
   - **Address:** (as on incorporation documents)
   - **Phone:** Your personal phone (must receive confirmation code)
   - **Website:** https://www.classbridge.ca/
3. Upload **Certificate/Articles of Incorporation** (PDF)
4. If document doesn't include phone number, select "No" and provide additional verification

### Step 2: Wait for Approval

- Typical timeline: **1-3 business days**
- Status visible at: Settings -> Business info -> Business verification status
- You'll receive an email notification when approved

### After Approval

1. Create OTP authentication template
2. Messaging limits unlocked (250+ business-initiated messages/day)
3. Can send to any WhatsApp user without prior opt-in message

---

## Message Templates

WhatsApp requires pre-approved templates for business-initiated outbound messages.

### Creating Templates in Meta

1. Go to Meta Business -> **WhatsApp Manager** -> **Message templates** -> **Manage templates**
2. Click **Create template**
3. Select category (**Utility** for digest, **Authentication** for OTP)
4. Fill in template name, language, and body with variables (`{{1}}`, `{{2}}`)
5. Add sample data for variables (for Meta review)
6. Set **Message validity period** (12-24 hours for digests, 10 minutes for OTP)
7. Click **Submit for review**

### Creating Templates in Twilio

Templates must also exist in Twilio's Content Template Builder:

1. Go to Twilio Console -> **Messaging** -> **Content Template Builder**
2. Click **Create new**
3. Match the template exactly to the Meta-approved version
4. Add sample data for variables
5. Click **Save and submit for WhatsApp approval**

### Current Templates

#### daily_digest (Utility)
- **Meta status:** Approved
- **Twilio Content SID:** `HX5fb1ebf94a75f33d1f88a2955f5f7234`
- **Variables:** `{{1}}` = parent name, `{{2}}` = digest content
- **Body:**
  ```
  Hi {{1}}, here's your child's daily school email summary:

  {{2}}

  View full digest at https://www.classbridge.ca/email-digest
  ```

#### otp_verification (Authentication)
- **Status:** Blocked until Meta business verification approved
- **Body:** `Your ClassBridge verification code is: {{1}}. This code expires in 10 minutes.`

---

## Cloud Run Configuration

### Environment Variables

Set via `gcloud run services update` or in the deploy workflow. Values marked "GitHub Actions secret" are injected by the deploy workflow from repo-level secrets — they are NOT hardcoded in the YAML.

| Variable | Type | Source | Value |
|----------|------|--------|-------|
| `TWILIO_WHATSAPP_FROM` | env var | GitHub Actions secret | `+16478008533` |
| `TWILIO_WHATSAPP_DIGEST_CONTENT_SID` | env var | GitHub Actions secret | `HX5fb1ebf94a75f33d1f88a2955f5f7234` |
| `TWILIO_ACCOUNT_SID` | secret | GCP Secret Manager | `ACbf7497fc27cd1d588cb30a6aba30d748` |
| `TWILIO_AUTH_TOKEN` | secret | GCP Secret Manager | (stored in GCP Secret Manager) |

### Setting Secrets

```bash
# Create secrets in GCP Secret Manager
echo -n "AC..." | gcloud secrets create TWILIO_ACCOUNT_SID --project=emai-dev-01 --data-file=-
echo -n "..." | gcloud secrets create TWILIO_AUTH_TOKEN --project=emai-dev-01 --data-file=-

# Apply to Cloud Run
gcloud run services update classbridge \
  --project=emai-dev-01 --region=us-central1 \
  --update-secrets='TWILIO_ACCOUNT_SID=TWILIO_ACCOUNT_SID:latest,TWILIO_AUTH_TOKEN=TWILIO_AUTH_TOKEN:latest' \
  --update-env-vars='TWILIO_WHATSAPP_FROM=+16478008533,TWILIO_WHATSAPP_DIGEST_CONTENT_SID=HX5fb1ebf94a75f33d1f88a2955f5f7234'
```

### Important: Use `--update-*` Not `--set-*`

- `--set-secrets` **replaces** all existing secrets (dangerous!)
- `--update-secrets` **adds/updates** without removing existing ones
- The deploy workflow uses `--set-secrets` with ALL secrets listed to be explicit

---

## Deploy Workflow

The deploy workflow (`.github/workflows/deploy.yml`) must include all Twilio variables. Twilio env var values are injected from GitHub Actions secrets rather than hardcoded in the YAML, which makes rotation easier and keeps production config out of the repo.

```yaml
--set-env-vars "...,TWILIO_WHATSAPP_FROM=${{ secrets.TWILIO_WHATSAPP_FROM }},TWILIO_WHATSAPP_DIGEST_CONTENT_SID=${{ secrets.TWILIO_WHATSAPP_DIGEST_CONTENT_SID }}" \
--set-secrets "...,TWILIO_ACCOUNT_SID=TWILIO_ACCOUNT_SID:latest,TWILIO_AUTH_TOKEN=TWILIO_AUTH_TOKEN:latest" \
```

If a new env var or secret is added manually to Cloud Run but NOT to the deploy workflow, it will be wiped on the next deploy.

### Required GitHub Actions Secrets (Twilio)

The following repo-level GitHub Actions secrets MUST exist before the deploy workflow runs. If they are missing, the `gcloud run deploy` step will inject empty values for `TWILIO_WHATSAPP_FROM` and `TWILIO_WHATSAPP_DIGEST_CONTENT_SID`, which will break WhatsApp delivery in production.

> WARNING: Create these secrets BEFORE merging any PR that references them, otherwise the next deploy will wipe the existing Cloud Run env vars and WhatsApp digests will stop working.

Run these commands once (repo admin only) to set them:

```bash
gh secret set TWILIO_WHATSAPP_FROM --body "+16478008533"
gh secret set TWILIO_WHATSAPP_DIGEST_CONTENT_SID --body "HX5fb1ebf94a75f33d1f88a2955f5f7234"
```

Verify they exist:

```bash
gh secret list | grep TWILIO_WHATSAPP
```

To rotate a value (e.g., new Content SID after template update), re-run `gh secret set` with the new value and trigger a deploy — no code change needed.

---

## Code Architecture

### Key Files

| File | Purpose |
|------|---------|
| `app/services/whatsapp_service.py` | Core WhatsApp sending (freeform + template) |
| `app/services/twilio_service.py` | Lower-level Twilio SMS/WhatsApp client |
| `app/jobs/parent_email_digest_job.py` | Digest delivery (includes WhatsApp channel) |
| `app/api/routes/parent_email_digest.py` | OTP send/verify endpoints |
| `app/models/parent_gmail_integration.py` | DB model (whatsapp_phone, whatsapp_verified) |
| `app/core/config.py` | Twilio settings (SID, token, from, content_sid) |
| `scripts/test_whatsapp.py` | Sandbox test script |

### Message Delivery Flow

1. Scheduled digest job runs (`parent_email_digest_job.py`)
2. Checks if `"whatsapp"` is in parent's `delivery_channels`
3. Checks `integration.whatsapp_verified` and `integration.whatsapp_phone`
4. Generates brief digest content via AI
5. Strips HTML tags to plain text
6. Truncates content BEFORE wrapping in template (preserves header/footer within 1600 char limit)
7. If `TWILIO_WHATSAPP_DIGEST_CONTENT_SID` is set:
   - Calls `send_whatsapp_template()` with `content_sid` + `content_variables`
8. Otherwise:
   - Calls `send_whatsapp_message()` with body text matching template pattern

### OTP Verification Flow

1. Parent enters phone number on Email Digest settings page
2. `POST /api/parent/email-digest/integrations/{id}/whatsapp/send-otp` sends 6-digit OTP
3. Parent receives OTP on WhatsApp
4. `POST /api/parent/email-digest/integrations/{id}/whatsapp/verify-otp` verifies code
5. On success: `whatsapp_verified = True`, `whatsapp` added to `delivery_channels`

---

## Testing

### Local Test (Sandbox)

```bash
# Ensure .env has Twilio credentials
python scripts/test_whatsapp.py +1YOURNUMBER
```

### Template Test (Content API)

```python
from app.services.whatsapp_service import send_whatsapp_template

send_whatsapp_template(
    '+1YOURNUMBER',
    'HX5fb1ebf94a75f33d1f88a2955f5f7234',
    {'1': 'Theepan', '2': 'Your child received 3 emails today...'}
)
```

### Production Verification

```bash
# Check if WhatsApp is configured
curl -s https://www.classbridge.ca/api/health | python -m json.tool

# Check Cloud Run env vars
gcloud run services describe classbridge \
  --project=emai-dev-01 --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)'
```

---

## Maintenance & Troubleshooting

### Sandbox Expired

If the sandbox stops working (72-hour limit):
1. Open WhatsApp on your phone
2. Send `join toward-master` to +1 415-523-8886
3. Wait for confirmation

### Messages Not Delivering

1. **Check WhatsApp is enabled:** Verify all 3 env vars are set (SID, token, from number)
2. **Check template status:** Ensure `daily_digest` is approved in both Meta and Twilio
3. **Check session window:** Business-initiated messages outside 24h require template invocation (Content SID)
4. **Check number format:** Must be E.164 format (e.g., `+16472936854`)
5. **Check Twilio logs:** Console -> Monitor -> Messaging -> Message Log

### Meta Business Verification Rejected

1. Check email from Meta for rejection reason
2. Resubmit with correct documents
3. Ensure business name matches exactly between documents and Meta account

### Rotating Twilio Auth Token

1. Generate new token in Twilio Console
2. Update GCP Secret Manager:
   ```bash
   echo -n "new-token" | gcloud secrets versions add TWILIO_AUTH_TOKEN --data-file=-
   ```
3. Redeploy Cloud Run to pick up new secret version

### Cost Monitoring

- WhatsApp Business API: ~$0.005-0.08 per message (varies by country)
- Twilio phone number: ~$1.15/month
- Monitor usage at: Twilio Console -> Account Dashboard -> Usage

---

## Related GitHub Issues

| Issue | Title | Status |
|-------|-------|--------|
| [#2967](https://github.com/theepangnani/emai-dev-03/issues/2967) | WhatsApp notification channel for parent email digest | Open (main epic) |
| [#3471](https://github.com/theepangnani/emai-dev-03/issues/3471) | Email sender identity enrichment | Open |
| [#3472](https://github.com/theepangnani/emai-dev-03/issues/3472) | Noreply/automated email detection | Open |
| [#3585](https://github.com/theepangnani/emai-dev-03/issues/3585) | WhatsApp template invocation fix | Closed |
| [#3586](https://github.com/theepangnani/emai-dev-03/issues/3586) | WhatsApp truncation fix | Closed |
| [#3591](https://github.com/theepangnani/emai-dev-03/issues/3591) | OTP authentication template | Open (blocked) |
| [#3592](https://github.com/theepangnani/emai-dev-03/issues/3592) | E2E WhatsApp digest UI testing | Open |
| [#3593](https://github.com/theepangnani/emai-dev-03/issues/3593) | Meta business verification follow-up | Open |

### PRs Merged (Apr 17-18, 2026)

| PR | Title |
|----|-------|
| [#3494](https://github.com/theepangnani/emai-dev-03/pull/3494) | db.rollback() fix + WhatsApp test script |
| [#3578](https://github.com/theepangnani/emai-dev-03/pull/3578) | Meta domain verification meta tag |
| [#3579](https://github.com/theepangnani/emai-dev-03/pull/3579) | WhatsApp template formatting + deploy workflow |
| [#3587](https://github.com/theepangnani/emai-dev-03/pull/3587) | Content API template invocation + truncation fix |
| [#3589](https://github.com/theepangnani/emai-dev-03/pull/3589) | Persist Content SID in deploy workflow |
| [#3595](https://github.com/theepangnani/emai-dev-03/pull/3595) | WhatsApp integration tracking update |
