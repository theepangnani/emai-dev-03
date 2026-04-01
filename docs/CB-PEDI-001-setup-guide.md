# Parent Email Digest (CB-PEDI-001) — Setup & Testing Guide

**Feature:** Parent Email Digest Integration
**PRD Reference:** CB-PEDI-001, §6.127
**PR:** #2780 (merged 2026-03-31)
**Milestone:** M1 — Foundation

---

## Overview

Parents connect their personal Gmail via OAuth (`gmail.readonly`). Their child's school email (e.g., YRDSB `student@gapps.yrdsb.ca`) is forwarded to the parent's Gmail. ClassBridge polls Gmail every 4 hours, and Claude AI summarizes emails into a daily digest delivered as a ClassBridge notification. No DTAP/MFIPPA required since it uses the parent's personal Gmail, not the school's systems.

---

## M1 Deliverables (Implemented — PR #2780)

| Component | Status | Details |
|-----------|--------|---------|
| DB Models | Done | `parent_gmail_integrations`, `parent_digest_settings`, `digest_delivery_log` — created via `create_all()` on startup |
| Pydantic Schemas | Done | `ParentGmailIntegrationResponse`, `ParentDigestSettingsResponse`, `DigestDeliveryLogResponse` + Create/Update variants |
| Gmail OAuth Flow | Done | JWT-based state tokens (stateless, Cloud Run safe), redirect_uri validation against allowlist |
| CRUD API Routes | Done | 10 endpoints under `/api/parent/email-digest/` — integrations, settings, delivery logs |
| Notification Type | Done | `PARENT_EMAIL_DIGEST` added to backend enum + frontend notification preferences |
| Setup Wizard UI | Done | 4-step modal on My Kids page — Connect Gmail → Child Info → Settings → Confirm |
| OAuth Callback Page | **Not built** | Frontend route at `/oauth/gmail/callback` needed to handle popup redirect |

## M2 Deliverables (Not Built — Target: May 2026)

| Component | Issue | Description |
|-----------|-------|-------------|
| Gmail polling service | #2648 | Poll parent Gmail every 4 hours for school emails |
| Forwarding verification | #2649 | Verify child's school email is forwarding to parent Gmail |
| Claude AI summarization | #2650 | Summarize polled emails into daily digest |
| Scheduled digest job | #2651 | Timezone-aware cron job, delivers via ClassBridge notifications |
| Branded email template | #2652 | HTML email template for digest delivery |
| Digest page + log UI | #2653 | Frontend page to view past digests and delivery log |
| Backend test suite | #2654 | Full pytest coverage for M1+M2 |

---

## Google Cloud Console Setup

**Project:** `emai-dev-01`
**Console URL:** https://console.cloud.google.com/auth/overview?project=emai-dev-01

### Step 1: Enable Gmail API

1. Go to **APIs & Services → Library**
2. Search for **"Gmail API"**
3. Click **Enable** (if not already enabled)

### Step 2: Add gmail.readonly Scope

1. Go to **Google Auth Platform → Data Access**
   URL: https://console.cloud.google.com/auth/scopes?project=emai-dev-01
2. Click **Add or remove scopes**
3. Search for `gmail.readonly` or paste: `https://www.googleapis.com/auth/gmail.readonly`
4. This scope is classified as **"Restricted"** — appears under "Your restricted scopes" with a warning triangle
5. Under **"What features will you use?"**, select: **"Email reporting and monitoring"**
6. Under **"How will the scopes be used?"**, enter justification:
   > ClassBridge reads school-related emails forwarded from a child's school email to the parent's personal Gmail. The app polls for new emails every 4 hours and generates an AI-summarized daily digest delivered as an in-app notification, helping parents stay informed about their child's school communications.
7. Save

### Step 3: Add Redirect URI

1. Go to **Google Auth Platform → Clients**
   URL: https://console.cloud.google.com/auth/clients?project=emai-dev-01
2. Click on the OAuth 2.0 Client ID
3. Under **Authorized redirect URIs**, add:
   ```
   https://www.classbridge.ca/oauth/gmail/callback
   ```
4. For local development, also add:
   ```
   http://localhost:5173/oauth/gmail/callback
   ```
5. Save

### Step 4: Test Users (if in Testing mode)

1. Go to **Google Auth Platform → Audience**
2. If app is in **Testing mode**, add test users' Gmail addresses
3. Up to 100 test users allowed without Google verification

---

## Google OAuth Scope Tiers

| Tier | Examples | Requirement | Cost |
|------|----------|-------------|------|
| **Basic** | openid, email, profile | None | Free |
| **Sensitive** | calendar.readonly | Privacy policy URL + basic verification | Free |
| **Restricted** | **gmail.readonly**, drive | Full security review (CASA Tier 2 audit) | ~$4,500-15,000 |

### When Verification Is Required

- **Testing mode (up to 100 users):** No verification needed. Restricted scopes work freely with added test users.
- **Production mode (unverified):** Any user can consent, but sees a **"Google hasn't verified this app"** warning. Users must click "Advanced" → "Go to ClassBridge (unsafe)" to proceed. Fine for pilot.
- **Production mode (verified):** Clean consent screen, no warnings. Required for public launch.

### Verification Timeline & Roadmap

| Phase | Timeline | Verification needed? | User experience |
|-------|----------|---------------------|-----------------|
| Developer testing | Now | No — app owner can always consent | Normal |
| YRDSB pilot (5-10 families) | June 2026 | No — users click through warning | "Unverified app" warning screen |
| Start verification process | **July 2026** | Submit application | — |
| Full public launch | September 2026 | **Yes — must be verified** | Clean consent screen, no warnings |

### What Pilot Parents Will See (Unverified)

1. "Google hasn't verified this app" warning screen
2. Click **"Advanced"** at bottom-left
3. Click **"Go to classbridge.ca (unsafe)"**
4. Normal Gmail consent screen appears — approve `gmail.readonly`

This looks alarming but is fully functional. Brief pilot parents to expect it.

### Verification Requirements (for public launch)

| Requirement | Cost | Time | Action |
|-------------|------|------|--------|
| Privacy policy URL | Free | 1 day | Publish at classbridge.ca/privacy |
| Homepage URL | Free | Done | classbridge.ca already live |
| Justification text | Free | 10 min | Already drafted (see Step 2 above) |
| **CASA Tier 2 security assessment** | **~$4,500-15,000 USD** | **4-8 weeks** | Engage assessor by July 2026 |

### Google-Approved CASA Assessors

- **Leviathan Security** — https://www.leviathansecurity.com
- **Bishop Fox** — https://bishopfox.com
- **NCC Group** — https://www.nccgroup.com
- Full directory: https://appdefensealliance.dev/casa/directory

### Recommended Action Items

1. **Now (April 2026):** Test with your own Gmail, no verification needed
2. **June 2026:** Pilot with 5-10 YRDSB families using unverified mode
3. **July 1, 2026:** Publish privacy policy at classbridge.ca/privacy
4. **July 1, 2026:** Submit Google OAuth verification application
5. **July 1, 2026:** Engage CASA Tier 2 assessor (budget ~$4,500-15,000)
6. **August 2026:** Complete CASA assessment + Google review
7. **September 2026:** Verified app — public launch with clean consent screen

---

## Environment Variables

The OAuth flow reuses existing Google OAuth credentials. No new env vars needed for M1.

| Variable | Used For | Where Set |
|----------|----------|-----------|
| `GOOGLE_CLIENT_ID` | OAuth client ID | Cloud Run env, `.env` local |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret | Cloud Run secret |

Verified present in Cloud Run production config (2026-03-31).

---

## API Endpoints

All endpoints require `PARENT` role authentication.

### OAuth

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/parent/email-digest/gmail/auth-url?redirect_uri=...` | Get Google OAuth URL |
| POST | `/api/parent/email-digest/gmail/callback` | Exchange OAuth code for tokens, create integration |

### Integrations

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/parent/email-digest/integrations` | List parent's integrations |
| GET | `/api/parent/email-digest/integrations/{id}` | Get single integration |
| PATCH | `/api/parent/email-digest/integrations/{id}` | Update child info, etc. |
| DELETE | `/api/parent/email-digest/integrations/{id}` | Disconnect integration |
| POST | `/api/parent/email-digest/integrations/{id}/pause` | Pause digest |
| POST | `/api/parent/email-digest/integrations/{id}/resume` | Resume digest |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/parent/email-digest/settings/{integration_id}` | Get digest settings |
| PUT | `/api/parent/email-digest/settings/{integration_id}` | Update settings |

### Delivery Logs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/parent/email-digest/logs?integration_id=&skip=&limit=` | List logs (paginated) |
| GET | `/api/parent/email-digest/logs/{log_id}` | Get single log with content |

---

## Security Notes

- **JWT-based OAuth state:** Stateless CSRF protection using signed JWT tokens with 10-minute expiry. Works across Cloud Run instances (no in-memory state).
- **Redirect URI validation:** Backend validates `redirect_uri` against allowlist: `classbridge.ca`, `www.classbridge.ca`, `localhost`.
- **Ownership verification:** All CRUD endpoints verify the authenticated parent owns the integration via `_get_owned_integration()` helper.
- **Token storage:** OAuth tokens (`access_token`, `refresh_token`) stored as plaintext in DB. **Follow-up issue #2781** to encrypt at rest before pilot.
- **Minimal scope:** Only `gmail.readonly` is requested — no write/send/delete access to Gmail.

---

## Known Gaps & Follow-up Issues

| Issue | Title | Priority |
|-------|-------|----------|
| #2781 | Encrypt Gmail OAuth tokens at rest | Security — before pilot |
| #2782 | CSS `--color-on-primary` token for text on colored buttons | Design — low |
| #2783 | Digest format mismatch between wizard and model | Bug — low |
| — | OAuth callback page (`/oauth/gmail/callback`) | **Needed for end-to-end flow** |

---

## Testing Checklist

### What's Testable Now (M1)

- [ ] Parent logs in → My Kids page → "Email Digest" action visible
- [ ] Wizard opens with 4 steps, renders correctly
- [ ] Step 1: "Connect Gmail" button triggers OAuth popup (requires Google Console setup complete)
- [ ] OAuth popup redirects to Google consent → user approves → callback page posts code to wizard (requires callback page)
- [ ] Step 2: Enter child school email + name → saved via PATCH endpoint
- [ ] Step 3: Configure delivery time, timezone, format, channels
- [ ] Step 4: Review + "Complete Setup" → settings saved
- [ ] `GET /api/parent/email-digest/integrations` returns the created integration
- [ ] `GET /api/parent/email-digest/settings/{id}` returns default settings
- [ ] Pause/resume endpoints toggle `paused_until`
- [ ] Delete endpoint removes integration + settings (CASCADE)
- [ ] Notification Preferences page shows "Parent Email Digest" category
- [ ] DB tables created on startup: `parent_gmail_integrations`, `parent_digest_settings`, `digest_delivery_log`

### What's NOT Testable Yet (M2)

- Gmail polling (not built — #2648)
- Email forwarding verification (not built — #2649)
- AI digest summarization (not built — #2650)
- Scheduled digest delivery (not built — #2651)
- Digest viewing page (not built — #2653)

---

## Architecture

```
Parent Gmail (personal)                ClassBridge
========================               ==========================

Child's school email                   M1 (Done):
  forwards to parent Gmail   ──►       ┌─ Gmail OAuth connect
                                       ├─ Integration CRUD
                                       ├─ Settings management
                                       ├─ Setup wizard UI
                                       └─ Notification type

                                       M2 (May 2026):
                                       ┌─ Gmail polling service
                                       ├─ Email extraction
                              ──►      ├─ Claude AI summarization
                                       ├─ Digest delivery job
                                       └─ Digest viewing UI
```

---

*Last updated: 2026-03-31 — PR #2780 merged, deployment successful*
