# Product Requirements Document: Email Digest Dashboard

**Working name:** CB-EDIGEST-002
**Version:** 1.0
**Date:** 2026-04-29
**Author:** Sarah (Product Owner) via interactive PRD discovery
**Quality Score:** 100/100 (4 rounds: Q1-Q10 + G1-G5)
**Tracking Issue:** #4487
**Status:** PRD complete — awaiting MVP stripe planning

---

## Executive Summary

Today, ClassBridge's parent-facing email surface ends at the email itself. Clicking "View in ClassBridge" lands users on `/email-digest`, a static list of past digest deliveries — no daily-action surface, no drilldown, no patterns. The page exists but doesn't earn the visit.

CB-EDIGEST-002 promotes `/email-digest` to a **real dashboard**: the post-login destination for every digest CTA, the first-5-second view of "what's urgent today, by kid, with a clear next action," and the gravitational center of the parent surface. Strategically, this enables the company to **shrink email volume from ~6/day per integration (the current `*/4` cron) to 1 daily + 1 weekly + security carve-outs only** — email becomes a thin teaser; dashboard owns the depth.

This is a **bet on parent retention via habit formation.** Successful implementation converts the dashboard into a Parent Daily Check-In Ritual; failure means the dashboard becomes another underused page and the email cap reduces engagement. User-stated as the **#1 feature.**

---

## Problem Statement

### Current Situation

- `/email-digest` is a list of past digest deliveries — no charts, no drilldown, no daily-action surface.
- Parents click "View in ClassBridge" and land on a static history feed; clicking a digest expands it to its source HTML but there's no further drill.
- Email-digest cadence is `*/4` (up to 6 emails/day per integration) — high volume + currently unreliable due to APScheduler scale-to-zero on Cloud Run (#4482).
- Multi-kid parents see one combined digest but no per-kid view, no "what's most urgent today across all my kids" answer.
- Parents who miss a digest have no UI to catch up — they have to scroll past emails and parse HTML.

### Proposed Solution

A purpose-built parent dashboard at `/email-digest` with three core surfaces:

1. **Today view** — "Urgent today, by kid, with next action," vertical-stack ordered by urgency.
2. **Week view** — Mon-Sun grid of this-week's deadlines per kid.
3. **Drilldown modal** — click any item → email body + extracted task + "Mark done" + "Snooze."

Email volume shrinks to **1 daily digest at parent-picked time + 1 weekly summary**, with non-digest product notifications routed to in-app / WhatsApp / push only. Email becomes a teaser that earns the click; dashboard earns the visit.

### Business Impact

The dashboard's reason-to-exist is **parent ritual formation** — a habit that drives retention by making ClassBridge a daily tool rather than a periodic email sender. Tied to the broader Parent Hub re-skin (CB-BRIDGE-001 shipped 2026-04-25), this is the centerpiece of the parent product surface. User-stated #1 feature.

---

## Success Metrics

### Primary KPI

- **50% Weekly Active Parents on the dashboard at 30 days post-launch.**
  - Definition: Parent visits `/email-digest` at least once during a rolling 7-day window.
  - Source: telemetry `dashboard.page_view` event on the dashboard route (instrumented in MVP).

### Activation event ("ritual formed")

- Parent visits dashboard **≥ 4 days in a 7-day window for 2 consecutive weeks.**
- Tracked via cohort dashboard.

### Counter-metrics (rollback signals)

- "I missed something at school" complaints **going UP** post-launch (support tickets, parent emails, in-app feedback).
- General complaint volume **going UP** post-launch.
- Trigger: any sustained month-over-month increase > 20% on either signal → flag-rollback.

### Validation horizon

- 30-day window post-launch: measure WAU% + activation cohort.
- 90-day window: confirm 50% WAU is sustainable, not novelty bump.
- Counter-metric monitoring: weekly check during ramp + monthly thereafter.

---

## User Personas

### Primary: Multi-Kid Parent

- **Role:** Working parent of 2-3 school-age kids.
- **Goals:** Know what's urgent today across kids, take next action without context-switching across N emails.
- **Pain Points:** Email overload (6/day per kid currently); important items buried in long-form prose; missing context when a teacher emails one kid only.
- **Technical Level:** Intermediate web; uses email + WhatsApp + Google Classroom daily.

### Secondary: Single-Kid Parent

- **Role:** Same as above, 1 kid.
- **Goals:** Lower email volume; cleaner dashboard.
- **Layout difference:** No sibling section; full-width "Today + week" for the one kid (no "All clear ✓" panel for a non-existent sibling).

### Edge: First-Run Parent (no digests yet)

- **Role:** Just connected Gmail; first digest hasn't fired.
- **Goals:** Validate that something will happen; not feel like the product is broken.
- **Layout:** Empty state with "Refresh" affordance to load fresh state on demand.

---

## User Stories & Acceptance Criteria

### Story 1: Glance at urgent items by kid

**As a** multi-kid parent
**I want to** open the dashboard and see what's urgent today across all my kids
**So that** I can act on the most important item without reading multiple emails.

**Acceptance Criteria:**
- [ ] Dashboard renders within 1s p95 (page-load SLO).
- [ ] Items grouped vertically per kid; kid with most urgent items appears first.
- [ ] Each kid section shows ≤ 3 items + "And N more →" CTA on overflow (matches sectioned email contract).
- [ ] When all kids have 0 urgent, "Calm" hero shows green check + "Nothing urgent today" + week grid below.
- [ ] When kid 1 has urgent + kid 2 has 0, kid 1 section first; kid 2 shows "All clear ✓" panel below.

### Story 2: Drill into a specific item

**As a** parent looking at an urgent item
**I want to** click it and see the original email + extracted task
**So that** I can take action (mark done / snooze / read full context) without leaving the dashboard.

**Acceptance Criteria:**
- [ ] Click any item → modal/drawer opens.
- [ ] Modal shows: email subject, body (full HTML or sanitized text), extracted task + due date, "Mark done" button, "Snooze" button.
- [ ] Mark done → dashboard refreshes; item removed from urgent list (Task.status = 'done').
- [ ] Snooze → item hidden from today view until snooze date passes.
- [ ] Modal closes back to dashboard (no full-page navigation).

### Story 3: Week-ahead glance

**As a** parent planning the week
**I want to** see this week's deadlines per kid
**So that** I can plan ahead without opening individual digest emails.

**Acceptance Criteria:**
- [ ] Mon-Sun grid renders below today section.
- [ ] Each cell shows count of deadlines per kid per day; click a cell → list of items for that day.
- [ ] Past-week days within the 7-day window show greyed; deadlines that already passed show as "missed" or completed.
- [ ] Mobile (< 768px): grid collapses to vertical day list.

### Story 4: Refresh on demand

**As a** parent who suspects new mail since the last digest
**I want to** trigger a refresh from the dashboard
**So that** I see the latest state without waiting for the next scheduled digest.

**Acceptance Criteria:**
- [ ] "Refresh" button visible in dashboard header.
- [ ] Click → backend re-fetches Gmail since last sync; spinner ≤ 5s p95; abort + error toast at 10s.
- [ ] Successful refresh → dashboard re-renders with fresh data.
- [ ] Rate-limited 10/min per user (matches existing /sync endpoint).

### Story 5: First-run + edge states

**As a** parent who's just connected Gmail / has paused all integrations / has 0 kids
**I want to** see a clear next action, not a generic empty state
**So that** I'm not confused about whether the product is working.

**Acceptance Criteria:**
- [ ] **0 kids registered** → onboarding banner "Add your kids to start" with link to `/my-kids`.
- [ ] **All integrations paused** → full-screen "Digests paused — resume to see today's view" with "Resume" CTA.
- [ ] **Gmail token expired** → auth-error banner "Reconnect Gmail" with reconnect CTA.
- [ ] **First-run (Gmail connected, no digest sent yet)** → empty state + "Refresh" button available to load fresh on demand.
- [ ] **Sectioned digest fell back to legacy_blob** (AI parse error) → dashboard shows the legacy HTML below.

---

## Functional Requirements

### Core Features (MVP)

**F1: Today view**
- Description: "Urgent today, by kid, with next action" — top of dashboard.
- User flow: Land on `/email-digest` → see today section first → vertical kid stack ordered by urgency → click item → modal drilldown.
- Data source: latest `digest_delivery_log` row per parent (snapshot of last digest send) + `tasks` (urgent + due_today) + `parent_child_profiles` (kid identity & ordering).
- Edge cases: covered in Story 5.

**F2: Week view (Mon-Sun grid)**
- Description: Below today section. Mon-Sun grid showing this-week deadlines per kid.
- User flow: Scroll past today → see week grid → click cell → list of items for that day.
- Data source: `tasks` filtered to current Mon-Sun + grouped by kid + day.
- Edge cases: Past-week deadlines show greyed/struck-through; future-week deadlines normal.

**F3: Drilldown modal**
- Description: Modal/drawer overlaying dashboard. Shows email + task + actions.
- User flow: Click any item from today/week → modal opens → Mark done / Snooze / Close.
- Data source: existing email parser output + `tasks` row.
- Phase 2 hook: "Ask Arc about this email" button (placeholder slot in MVP modal markup, deferred behavior).

**F4: Refresh button**
- Description: Top-right of dashboard. Triggers manual Gmail re-fetch.
- User flow: Click → spinner → fresh data renders OR error toast.
- Data source: existing `POST /api/parent/email-digest/integrations/{id}/sync` endpoint, called per active integration.
- Rate limit: 10/min per user.

**F5: Empty/quiet states**
- Description: "Calm" hero ("Nothing urgent today" + green check) + week grid below when zero urgent across kids.
- User flow: Same dashboard, just calm content above week grid.
- Decided NOT to A/B test (calm hero is MVP; if WAU < 30% at 30 days, revisit).

**F6: Per-kid stack ordering**
- Description: Kid sections vertically ordered by urgency (count of urgent items DESC).
- "All clear ✓" panels for kids with 0 urgent items (multi-kid parent only — single-kid parent's dashboard has no sibling slot).

### Out of Scope (Phase 2+)

Explicitly excluded from this PRD to prevent scope creep:

- **In-dashboard chat with Arc** ("Ask Arc about this email" Q&A) — Phase 2 of the ritual mechanic.
- **Streak counter + freeze tokens** (CB-DCI-001 parent-side analog) — Phase 3 of the ritual mechanic.
- **Smart nudges** (push / WhatsApp / in-app prompt if parent hasn't checked in by end-of-day) — Phase 2 of the ritual mechanic.
- **Patterns / charts** (cross-kid comparison, deadline density, etc.) — Phase 3+.
- **History view** (browse past digests beyond today's snapshot) — kept out of MVP per Q6 (c) cut.
- **Mobile app parity** — web-only for MVP; ClassBridgeMobile follow-up.
- **Email digest content/format changes** — covered by D4a/D5 already shipped (PR #4548).
- **Digest send cadence changes (`*/4` → 1 daily + 1 weekly)** — covered by D1 (#4482) Cloud Scheduler migration, separate effort.

This PRD assumes the following are already in place:
- `parent.unified_digest_v2` flag is `on_100` (default).
- `digest_format = 'sectioned'` is the default for new integrations (D4a shipped).
- `digest_delivery_log` model carries the daily snapshot.

---

## Technical Constraints

### Performance

- **Page-load p95 < 1s** (snapshot view reading from `digest_delivery_log` row already in DB — no AI calls in the page-load path).
- **Refresh-button SLO < 5s p95**, abort + error toast at 10s.
- **Mobile responsive:** full layout ≥ 768px; below 768px, vertical-stack of today (no week grid columns) + collapsed kid sections.

### Security

- All routes parent-RBAC gated (`require_role(UserRole.PARENT)`).
- Parent can only see own kids' data (existing scoping enforced at query layer).
- Gmail token auth state checked at dashboard load; expired → "Reconnect Gmail" banner (no leakage of stale data).
- Email-volume cap (Q4 (c)): non-digest product emails routed to in-app / WhatsApp / push only. Security carve-outs (auth, password reset, account changes) keep email channel.

### Integration Dependencies

**Existing systems used as-is:**
- `digest_delivery_log` (latest row per parent → dashboard's "today" snapshot)
- `tasks` (urgent items + due dates) from CB-TASKSYNC-001 I3/I6
- `parent_child_profiles` (kid identity + ordering) from CB-PEDI-002
- `parent_gmail_integrations` (refresh button targets per-integration sync)

**Existing flag enforced:** `parent.unified_digest_v2 = on_100` (default).
**Existing default enforced:** `digest_format = 'sectioned'` (D4a shipped).

**No new tables needed** for MVP. May need 1 new `GET` endpoint to aggregate the day's structured view (TBD during stripe planning):

```
GET /api/parent/email-digest/dashboard?since=today
→ {
    "kids": [{"id", "first_name", "urgent_items": [...], "weekly_deadlines": [...]}],
    "empty_state": "calm" | "no_kids" | "paused" | "auth_expired" | "first_run" | null,
    "refreshed_at": "ISO timestamp",
  }
```

### Technology Stack

- **Frontend:** React 19 + TypeScript + Vite, TanStack React Query, React Router 7. Bridge skin CSS variables (CB-BRIDGE-001).
- **Backend:** FastAPI + SQLAlchemy 2.0 + Pydantic 2.x (no new dependencies for MVP).

---

## MVP Scope & Phasing

### Phase 1 (MVP) — target ship in 2-3 weeks

- F1: Today view (urgent by kid, vertical stack)
- F2: Week view (Mon-Sun grid)
- F3: Drilldown modal (email + task + Mark done + Snooze)
- F4: Refresh button (calls existing /sync)
- F5: Empty/quiet states ("Calm" hero + edge states)
- F6: Per-kid stack ordering

**MVP Definition:** Parent can answer "what's urgent today, across all my kids" + drill into any item to act, all within `/email-digest`, in < 1s page load. Compelling enough content that the visit earns itself.

### Phase 2 — post-launch ritual reinforcement

- "Ask Arc about this email" Q&A in drilldown modal.
- Smart nudges (push if not checked in by end-of-day).
- History view (last 30 days collapsed).
- Telemetry expansion: `dashboard.item_click`, `dashboard.refresh_click`, `dashboard.mark_done`, `dashboard.snooze`, `dashboard.week_grid_click`.

### Phase 3 — habit gamification

- Streak counter + freeze tokens (parent-side analog of CB-DCI-001).
- Patterns / charts dashboard (cross-kid comparison, deadline density).
- Mobile app parity in ClassBridgeMobile.

### Future Considerations

- AI-generated weekly summary inside the dashboard (synthesis across kids).
- Integration with `tasks` for assignment-tracker views (ties into CB-TASKSYNC-001).
- Cross-board / multi-school comparison for parents with kids in different boards.

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Email-volume cap drops engagement** — parents miss the daily 7am rhythm and don't visit dashboard | Med | High | Activation event tracked; counter-metrics watched weekly. Flag-ramp `email_digest_dashboard_v1` at on_5 → on_25 → on_100 over 4 weeks. Roll back if "I missed something" complaints rise > 20% MoM. |
| **Refresh button burns Gmail API quota** — parents click as a habit | Med | Med | Rate-limit 10/min per user (existing pattern). Add quota monitor alert at 70% of daily Gmail quota. |
| **MVP feels too thin** — content-only must earn the visit (no chat, no streak yet) | Med | Med | Phase 2 (nudges + Arc Q&A) within 4 weeks of MVP. If WAU < 30% at 30 days, prioritize Phase 2 over Phase 3. |
| **Multi-kid layout breaks for 4+ kids** | Low | Low | Vertical-stack scales arbitrarily; tested with 3-kid synthetic data; >3 kids is rare per current cohort. |
| **Gmail token-expired state proliferates** — parents don't reconnect | Med | Med | Existing reconnect flow + dashboard banner. If > 10% of users hit expired state weekly, file as separate issue. |
| **Dashboard becomes ad-hoc settings page** — scope creep | High | Med | "Out of scope" guardrails section in this PRD; review weekly during MVP build. |
| **APScheduler unreliability (#4482) corrupts the snapshot** — `digest_delivery_log` may be 24+ hours stale on quiet traffic | Med | Med | Surface "Last updated: X ago" on dashboard. Refresh button reliably triggers fresh fetch. D1 Cloud Scheduler migration deferred but tracked. |

---

## Dependencies & Blockers

### Dependencies (must be in place — all already shipped)

- **D6** (#4486 — login redirect preserves intended path) — **SHIPPED** in master (cddaf8af). Without this, deep-link from email → /email-digest is broken.
- **D4a** (#4484 — sectioned digest default) — **SHIPPED** in master (cddaf8af). Provides the data shape (sectioned sections + overflow) the dashboard renders.
- **D2/D3** (#4483 — parent-scoped Send-Now) — **SHIPPED** in master (cddaf8af). Refresh-button-equivalent surface for backend re-fetch.
- `digest_delivery_log` model — **EXISTS**, no schema change needed for MVP.
- `tasks` model — **EXISTS** (CB-TASKSYNC-001 I3/I6 shipped).
- `parent_child_profiles` model — **EXISTS** (CB-PEDI-002 shipped).

### Known Blockers

- **D1** (#4482 — APScheduler scale-to-zero) — **NOT a hard blocker for MVP** because the dashboard reads from existing `digest_delivery_log` rows (no new cron). However, until D1 ships, the "1 daily + 1 weekly" cadence model can't be enforced — the cron may fire 0× per day on quiet traffic. **Recommend D1 land before Phase 2 nudges.**

### Coordination needed

- **Telemetry sink:** confirm `page_view` event endpoint (Mixpanel? GA4? in-house?) — currently ambiguous. Ops alignment needed before MVP build kickoff.
- **Counter-metric instrumentation:** how do we reliably tag "I missed something" complaints? Likely via support inbox tagging — needs ops alignment.
- **Email-volume cap enforcement (Q4 (c)):** non-digest product emails currently CAN fire from `notification_service.send_multi_channel_notification` with email channel. Audit + reroute decision needed during MVP build (file as sub-stripe).

---

## Validation Plan

### Beta cohort gate

- **Feature flag:** `email_digest_dashboard_v1` (NEW — to be created during MVP build).
- **Ramp:** on_5 (5% — week 1) → on_25 (week 2) → on_100 (week 3-4).
- **Pre-ramp:** internal team only (theepang@gmail.com + dogfooding accounts).

### Empty-state UX

**Calm hero — confirmed in Q4-Q9 round.** NOT A/B tested. Will measure DAU directly; A/B is overkill for MVP. If WAU < 30% at 30 days, revisit empty-state UX as part of Phase 2 reassessment.

### Telemetry events (MVP)

- `dashboard.page_view` (instrumented in MVP).
- **Phase 2 expansion:** `dashboard.item_click`, `dashboard.refresh_click`, `dashboard.mark_done`, `dashboard.snooze`, `dashboard.week_grid_click`.

### Pre-ramp checklist

- [ ] WAU monitoring dashboard live (Mixpanel/GA4 or chosen sink).
- [ ] Counter-metric tracking: support inbox "I missed something" tag.
- [ ] Rollback procedure documented (flag → off, no migration to revert).
- [ ] Empty-state UX reviewed with founder/Sarah after first dogfood week.

---

## Locked Decisions (from PRD discovery)

For traceability, these are the decisions we explicitly locked during the 4-round Sarah dialogue (2026-04-29). Numbered Q1-Q10 + G1-G5.

| # | Question | Locked answer |
|---|---|---|
| Q1 | Parent's job-to-be-done | (f) all jobs apply; email = teaser, dashboard = destination + (g) 1 daily + 1 weekly only |
| Q2 | First-5-second feeling | "Urgent today, by kid, with clear next action" |
| Q3 | North-star metric | DAU/WAU as Parent Daily Check-In Ritual |
| Q4 | Email-volume scope | (c) hard cap on product emails, security carve-outs only |
| Q5 | Ritual mechanic | (e) phased: MVP = compelling content; Phase 2 += nudges; Phase 3 += streak |
| Q6 | MVP cut | (c) Today + week view (no history, no charts) |
| Q7 | Drilldown depth | (b) modal/drawer for MVP; (d) Arc Q&A is Phase 2 |
| Q8 | Empty/quiet state | (a) "Calm" hero + week grid below |
| Q9 | Multi-kid layout | (a) vertical stack; "All clear ✓" panels |
| Q10 | Data freshness | (c) snapshot + parent-pulled "Refresh" button |
| G1 | Performance SLOs | page < 1s p95, refresh < 5s p95, mobile ≥ 768px breakpoint |
| G2 | Edge cases | 0 kids → onboarding banner; paused → full-screen banner; single-kid → no sibling section; auth-expired → "Reconnect Gmail"; first-run → empty + Refresh; legacy_blob → show legacy HTML |
| G3 | Adoption target | 50% WAU at 30 days; activation = ≥4 days/7 for 2 weeks; counter-metric = "I missed something" + complaint volume |
| G4 | Validation plan | Calm hero (no A/B); flag-ramp on_5 → on_25 → on_100 over 4 weeks; `dashboard.page_view` MVP telemetry only |
| G5 | Out-of-scope guardrails | See "Out of Scope" section above |

---

## Appendix

### Glossary

- **Sectioned digest** — 3×3 format: Urgent / Announcements / Action Items, ≤ 3 items per section, "And N more →" CTA on overflow. Implemented in `app/services/notification_service.py:319-395`.
- **DigestDeliveryLog** — DB row per parent per send; carries `digest_content` HTML + delivery status. Source of truth for "today's snapshot."
- **Parent Daily Check-In Ritual** — habit-formation hypothesis: parent visits dashboard ≥ 4 days in a 7-day window for 2 consecutive weeks.
- **Bridge skin** — visual language established by CB-BRIDGE-001 (2026-04-25); dashboard inherits this.
- **Calm hero** — empty-state visual: green check + "Nothing urgent today" + week grid below.

### References

- Tracking issue: #4487 (CB-EDIGEST-002 epic)
- Sibling shipped work: #4483, #4484, #4485, #4486, #4538 — squashed in PR #4548 (master cddaf8af)
- Adjacent epics: CB-PEDI-002 (unified digest), CB-TASKSYNC-001 (task sync), CB-BRIDGE-001 (re-skin), CB-DCI-001 (kid daily check-in — Phase 3 analog)
- Defect register origin: 2026-04-28 user-reported defects D1-D7
- Discovery dialog: 4 rounds (Q1-Q10 + G1-G5) between user and Sarah, 2026-04-29.
- Project memory snapshot when discovery occurred: 2026-04-28 (post CB-CMCP-001 M0 engineering complete)

### Changelog

- **v1.0 (2026-04-29)** — initial PRD authored after 4 rounds of interactive discovery.

---

*This PRD was created through interactive requirements gathering with quality scoring (final score 100/100). Living doc — edits in-place welcome.*
