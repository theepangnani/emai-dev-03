# Email Digest — Unified Multi-Kid V2 (Design Proposal)

**Status:** Design review
**Related issue:** #4007 (routing bug, fixed in PR #4010)
**Date:** 2026-04-23
**Author:** Theepan (with Claude)

## Problem

Today, Email Digest is modeled as **one integration per child**, with monitored senders locked to a single integration. A parent with two kids sees two separate pages, two separate monitored-sender lists, and two digests in their inbox. They must add the same teacher email twice if both kids share a class.

What we want: **one page**, **one digest**, with per-sender attribution to the right kid — correctly handling the "same sender, multiple kids" and "generic `noreply@`" cases.

## Locked-in decisions (v1)

1. **One daily digest per parent** — all kids combined into a single email. Per-kid sections inside.
2. **"All kids" is the default** for a newly added sender (incl. future-added kids auto-inherit). Parent can opt out per sender.
3. **School email is a first-class attribution key**, stored separately from the student's ClassBridge login email.
4. **No email-based verification** for school emails in v1 — external email to school inboxes is blocked by boards until DTAP approval lands.
5. **"Forwarding detected" indicator** replaces verification — a functional check based on messages observed in the parent's Gmail with matching `To:` headers.

## Constraints

| # | Constraint | How the design handles it |
| - | --- | --- |
| 1 | Same school, same teachers — `bill.hogarth.ss@yrdsb.ca` emails both kids | Sender stored once, assigned to both kids via join table |
| 2 | Common `noreply@` senders (Google Classroom, board announcements) | "All kids" default; attribution resolved at email-ingest time via `To:` header |
| 3 | External email to student school inboxes is blocked by board firewalls (pre-DTAP) | No verification email; forwarding-detected indicator only |
| 4 | Student's ClassBridge login email ≠ school email | Separate table; attribution never looks up `users.email` |
| 5 | Parents may have separate Gmails per kid (rare, joint custody) | Not supported in v1; parent picks one Gmail during migration |

## Data model

### Current (problematic)

```
ParentGmailIntegration(parent_id, gmail_address, child_school_email, child_first_name)   [ONE per (parent, child)]
  └── ParentDigestMonitoredEmail(integration_id, email_address, sender_name, label)      [bound to ONE child]
```

### Proposed

```
ParentGmailIntegration(parent_id, gmail_address, ...)                           [ONE per parent — the Gmail inbox]
ParentChildProfile(parent_id, student_id, first_name)                           [one per kid]
ParentChildSchoolEmail(child_profile_id, email_address, forwarding_seen_at)     [NEW: N per kid — school inboxes they own]
ParentDigestMonitoredSender(parent_id, email_address, sender_name, label, applies_to_all)
SenderChildAssignment(sender_id, child_profile_id)                              [explicit per-kid overrides]
```

### Key rules

- `ParentChildSchoolEmail.email_address` is the **only** field consulted for header-based attribution. Never `users.email`.
- `ParentDigestMonitoredSender` deduplicates on `(parent_id, email_address)` — adding the same sender twice with different kid tags merges into one row with both assignments.
- `applies_to_all = true` overrides individual assignments (sender applies to every current and future kid).

## UX — single management page

Replaces today's per-kid `/email-digest?kid=…` flow. The child-switcher chip from PR #4010 becomes unnecessary and is removed.

### Layout sketch

```
┌────────────────────────────────────────────────────────┐
│  Email Digest                                          │
│  One daily summary of everything for all your kids.    │
├────────────────────────────────────────────────────────┤
│  [ Gmail connected: parent@gmail.com  Reconnect ]      │
│  [ Delivery: 7:00 AM   Enabled ●   WhatsApp: +1… ]     │
├────────────────────────────────────────────────────────┤
│  Your kids                                             │
│  ┌──────────────────────────────────────────────┐     │
│  │ Thanushan · Grade 10                         │     │
│  │   School emails (for smart filtering)        │     │
│  │   ℹ️ Board-issued address where teachers     │     │
│  │     email your kid (e.g., @ocdsb.ca).        │     │
│  │     Different from ClassBridge login.        │     │
│  │   ● thanushan@ocdsb.ca  ✓ Forwarding active  │     │
│  │     (12 messages seen in last 7 days)        │     │
│  │   [ + Add another school email ]              │     │
│  ├──────────────────────────────────────────────┤     │
│  │ Haashini · Grade 8                           │     │
│  │   School emails                              │     │
│  │   ● haashini@frankln.ca  ⚠ No forwarded      │     │
│  │     messages yet — check forwarding rule →   │     │
│  └──────────────────────────────────────────────┘     │
├────────────────────────────────────────────────────────┤
│  Monitored senders                                     │
│  ┌─────────────────────────────────────────────────┐   │
│  │ bill.hogarth.ss@yrdsb.ca    [Thanushan][Haashini]│  │
│  │ Bill Hogarth SS · school                    [×] │   │
│  ├─────────────────────────────────────────────────┤   │
│  │ no-reply@classroom.google.com     [All kids]    │   │
│  │ Google Classroom                            [×] │   │
│  ├─────────────────────────────────────────────────┤   │
│  │ counselor@frankln.ca              [Haashini]    │   │
│  │ Varun Kunar · counselor                     [×] │   │
│  └─────────────────────────────────────────────────┘   │
│  [ + Add sender ]                                      │
└────────────────────────────────────────────────────────┘
```

### Add-sender flow

```
┌─────────────────────────────────────┐
│  Add sender                         │
│  Email:      [sender@school.ca   ]  │
│  Name:       [Mrs. Smith         ]  │
│  Label:      [Math teacher       ]  │
│  Applies to: ☑ Thanushan             │
│              ☑ Haashini              │
│              ☐ All kids (incl. future) │
│  [ Cancel ] [ Add ]                 │
└─────────────────────────────────────┘
```

Default state: **"All kids (incl. future)"** pre-selected. Parent can deselect and choose specific kids. At least one selection required.

### Onboarding

Setup wizard gains one step:

> "What are your kids' school email addresses?
> We use these to route forwarded messages to the right kid. External email to school inboxes is blocked until we get board access, so please set up a Gmail forwarding rule in each school inbox → your Gmail. [How?]
> (Optional — you can add these later.)"

The [How?] link opens a short help article with per-provider (Google Workspace, O365) step-by-step instructions.

## Attribution algorithm

When the digest worker ingests each email from the parent's Gmail:

1. **Read `Delivered-To:` and `To:` headers** from the message. Gmail preserves these on forwarded mail.
2. **Match against `ParentChildSchoolEmail.email_address`:**
   - Exactly one match → attribute to that kid. Stamp `forwarding_seen_at = now()` on the matching school-email row.
   - Multiple matches (rare — same message cc'd to both kids) → attribute to all matched kids.
   - No match → proceed to step 3.
3. **Fall back to sender-level assignment:**
   - Sender tagged to specific kid(s) → use that.
   - Sender tagged "All kids" → put in the **"For both kids"** section at the top of the digest.
4. **No tag, no header match** → sender is new to this parent; surface in UI as "Unattributed senders — tag them" with one-click assign.

### Why `Delivered-To:` / `To:` header matching is safe

- Gmail forwarding preserves the original envelope headers. The parent's Gmail copy of a message that was forwarded from `thanushan@ocdsb.ca` has `Delivered-To: thanushan@ocdsb.ca` intact.
- The Gmail API exposes these headers directly — no body parsing, no AI, no fragility.
- The algorithm is deterministic, explainable, and easy to QA.

## "Forwarding detected" indicator (replaces verification)

Each `ParentChildSchoolEmail` row stores `forwarding_seen_at` (last time the digest worker saw a message with a matching `To:` header).

UI rendering:

| State | Badge |
| --- | --- |
| `forwarding_seen_at` within last 14 days + ≥1 message | ✓ Forwarding active (N messages seen in last 7 days) |
| `forwarding_seen_at` older than 14 days | ⚠ Forwarding may have stopped — last seen N days ago |
| Never seen (`forwarding_seen_at` NULL) | ⚠ No forwarded messages yet — check forwarding rule → |

The "check forwarding rule" link opens the help article with fix-it instructions.

## Migration plan

### Data migration (online, backwards-compatible, dual-write for one release)

1. Create new tables: `parent_child_profiles`, `parent_child_school_emails`, `parent_digest_monitored_senders`, `sender_child_assignments`.
2. For each existing `ParentGmailIntegration`:
   - Create a `parent_child_profiles` row. Try to link `student_id` by matching `child_first_name` against the parent's children list; leave NULL if no match.
   - Seed `parent_child_school_emails` with `integration.child_school_email` — but **flag as unconfirmed** (since some parents may have entered the ClassBridge login rather than the school address).
3. For each existing `ParentDigestMonitoredEmail`:
   - Find or create a `parent_digest_monitored_senders` row (dedupe on `(parent_id, email_address)`).
   - Create a `sender_child_assignments` row linking it to the migrated child profile.
4. **Dual-write for one release:** digest worker reads from new tables; all writes update both old and new. After one release with no regressions, drop old tables.

### Post-migration one-time confirmation banner

On first visit to the unified page, for each auto-seeded school email:

> "We're setting up smart filtering for Thanushan. Is `thanushan@ocdsb.ca` his board-issued school email?
> [Yes, it's his school email] [No, change it] [Skip — set it up later]"

Parents who skip still get the unified digest, just without auto-attribution.

### Multi-Gmail parents (rare, joint custody)

On migration, if a parent has `ParentGmailIntegration` rows with different `gmail_address` values:

- Show a one-time modal: "You had two Gmail accounts connected (one per kid). We now support one per parent. Pick which to keep — you can re-connect the other as a secondary later."
- Default to the most-recently-synced one.
- Re-connect flow for the second Gmail is out of scope for v1.

## API changes

### New endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/parent/email-digest/monitored-senders` | List all senders for this parent with assignments |
| POST | `/api/parent/email-digest/monitored-senders` | `{ email, sender_name, label, child_profile_ids: [...] | "all" }` |
| DELETE | `/api/parent/email-digest/monitored-senders/{id}` | Remove a sender |
| PATCH | `/api/parent/email-digest/monitored-senders/{id}/assignments` | `{ child_profile_ids }` |
| GET | `/api/parent/child-profiles` | List kids with their school emails + forwarding status |
| POST | `/api/parent/child-profiles/{id}/school-emails` | `{ email_address }` |
| DELETE | `/api/parent/child-profiles/{id}/school-emails/{email_id}` | Remove a school email |

### Deprecated (kept for one release)

- `/api/parent/email-digest/integrations/{id}/monitored-emails` — continues to work, reads via new tables, writes go to both. Removed in the release after.

## Rollout

- Feature flag: `parent.unified_digest_v2` — OFF by default.
- Dark-ship the UI first — migration happens server-side, old UI stays active.
- Flip flag for internal testers (myself + 1-2 parent testers).
- Ramp: 10% → 50% → 100% over 1 week.
- Keep old UI reachable via `?legacy=1` query param during ramp as fallback.

## Effort estimate

| Area | Effort |
| --- | --- |
| Data-model migration + new tables | 1.5 days |
| Attribution algorithm in digest worker (`To:`/`Delivered-To:` lookup) | 1 day |
| Backend API | 1 day |
| Frontend (management page + school-email block + forwarding-detected badges) | 2 days |
| Onboarding step — "add school emails for smart filtering" | 0.5 day |
| QA + rollout flag | 1 day |
| **Total** | **~1 week** |

## Out of scope for v1 (captured for later)

- **DTAP-backed direct school-inbox ingestion** — future enhancement once board approval lands. Keeps the same data model; only the ingestion source changes.
- **Per-sender body keyword tagging** (e.g., distinguish messages within a single `principal@` sender by student name in the body) — fragile, not needed if school-email attribution covers the common cases.
- **Multiple Gmail accounts per parent** — complex auth state, rare use case.
- **School-email ownership verification** — blocked by board firewalls pre-DTAP; not possible in v1.
- **Parent-to-parent sharing of digest** (co-parent scenarios) — separate feature.

## Open questions

None remaining. Decisions locked:

- ~~Single digest vs multiple?~~ → **One digest** ✅
- ~~"All kids" default?~~ → **Yes, default "All kids"** ✅
- ~~Different Gmail per kid — block or auto-pick?~~ → **Auto-pick most-recent; let them reconnect later** ✅
- ~~Verify school-email ownership?~~ → **No — not possible (board firewalls); use forwarding-detected indicator instead** ✅
- ~~School email vs ClassBridge login email — same field or separate?~~ → **Separate tables; attribution never touches `users.email`** ✅
