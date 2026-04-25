# Bridge (My Kids redesign) — Decision-Ready Plan

**Status:** Plan only. Prototype at [my-bridge-to-bridge-prototype.html](./my-bridge-to-bridge-prototype.html). To be picked up as part of the broader app-wide cleanup pass.

**Date:** 2026-04-24

---

## Summary

The redesign and the rename are **independently shippable** and should not be bundled. Recommended order:

1. **Phase 1 — Re-skin under "My Kids" label** (6 PRs, see below). Gather user-comprehension and engagement telemetry.
2. **Phase 2 — Decide on rename** based on telemetry + 5-parent qualitative test.
3. **Phase 3 — Rename in a single coordinated PR** (frontend + backend + mobile + tests + copy). Behind a flag, gradient release.

Bundling rename + redesign in the same release makes regression triage impossible.

---

## Phase 1 — Re-skin (6 PRs)

| # | Scope | Net new files | Risk |
|---|---|---|---|
| 1 | Shell only: `BridgeHeader` + `KidRail` rendered above existing markup; CSS tokens; route-scoped font loader | `components/bridge/BridgeHeader.tsx`, `KidRail.tsx`, `SectionHead.tsx`, `pages/BridgePage.css`, `hooks/useBridgeFonts.ts` | Low — existing markup untouched |
| 2 | `KidHero` + `KidActionsMenu` (kebab); wires to existing handlers (edit/reset pw/resend invite/remove/export). Keep `AddActionButton` for now. | `KidHero.tsx`, `KidActionsMenu.tsx` | Med — kebab gating on `invite_id` & linked-account state |
| 3 | Management grid: replace 4 `SectionPanel` blocks (Email Digest, Classes, Teachers, Materials) with `ListCard` + `EmailDigestCard`. Drop `showCourses`/`showTeachers`/`showMaterials` state. | `ListCard.tsx`, `EmailDigestCard.tsx`, `Toggle.tsx` | Med — Email Digest toggles must be read-only until per-channel PATCH exists |
| 4 | Insights: re-skin `GradesSummaryCard` + `StudyTimeSuggestions` into muted-card shell with heatmap layout. | optional `BridgeGradesCard.tsx`, `StudyTimesHeatmap.tsx` | Low — presentation only, same data hooks |
| 5 | All-kids overview cards; remove legacy unassigned panels; decide fate of `AddActionButton` FAB. | `AllBridgesOverview.tsx` | Med — global "+ Course Material / + Task / Export Data" need a home if FAB goes |
| 6 | A11y polish, kebab keyboard nav, responsive breakpoints, JourneyNudgeBanner placement, tests | — | Low |

**Each PR is independently shippable.** PRs 1-2 leave existing markup intact below the new shell, so the page works mid-migration.

## Code debt impact (Stream A)

After full re-skin completes:

- **Imports dropped (2):** `StudyRequestModal`, `AddActionButton` (latter only if FAB is fully replaced — open question).
- **State vars become unused (~13):** Reset PW, Add Teacher, Study Request, Award XP modal flags. Modals themselves stay, just get new triggers.
- **Handlers orphaned:** none. Every callback has a new home in kebab or per-card head-action.
- **`EmailDigestSetupWizard` stays** — re-triggered from "Edit setup" on the digest card.

## Open design decisions (lock before PR 1)

1. **Email Digest toggles.** Cosmetic read-only summary of wizard state, or wait for per-channel PATCH endpoint? **Lean: cosmetic for now.**
2. **`AddActionButton` FAB fate.** Fold into kebab + per-card actions and delete, or keep? **Lean: delete; fold "Export Data" into kebab; "+ Course Material" → Materials card head; "+ Task" needs a home (TBD).**
3. **Conditional kebab items.** "Reset password" requires linked account; "Resend invite" requires `invite_id`; both must be conditionally rendered.
4. **Header stat aggregation.** "Classes tracked" sums across kids — currently only fetched in all-kids view. Need to fetch all child overviews up front for header stats in single-kid mode.
5. **Section collapse.** Drop the always-collapsed `SectionPanel` model entirely (always-show), or hide collapse UI but keep state vars? **Lean: drop entirely.**

---

## Phase 2 — Rename evaluation criteria

Before triggering Phase 3, confirm:

- [ ] Phase 1 has been live ≥ 2 weeks
- [ ] Nav-click rate on "My Kids" has not dropped post-redesign (baseline established)
- [ ] 5 parents tested with the new label "Bridge" — ≥ 4 click it without prompting when asked "where would you set up your child's email digest?"
- [ ] Help docs + onboarding copy drafts ready
- [ ] Decision logged: full rename, partial ("My Kids → Bridges"), or hold

---

## Phase 3 — Rename cost ledger (Stream B)

**45 files, 54 occurrences.** Single coordinated PR behind a feature flag.

| Category | Files | Notes |
|---|---|---|
| Routes | 6 | `App.tsx`, `MyKidsPage.tsx`, mobile nav, 3 backend files |
| Nav labels | 5 | DashboardLayout, Mobile AppNavigator (×2), test |
| Page titles & breadcrumbs | 2 | DashboardLayout title map, MyKidsPage breadcrumb |
| User-facing copy | 11 | journeyData, EmailDigestPage, ParentAITools, ReportCardAnalysis, HelpPage, mobile HelpScreen |
| Tests | 2 + 1 | ReportCardAnalysis.test, ParentDashboard.test, DashboardLayout.test |
| Mobile | 5 | `MyKidsScreen` → `BridgeScreen`, 6 React Navigation type/function symbol renames |
| Backend | 5 | `search.py`, `study_requests.py`, `journey_hint_service.py`, `search_service.py` deep-link generation |
| Quick actions | 2 | DashboardLayout `?action=` URL navigations |
| Journey & onboarding | 3 | `GettingStartedWidget`, `SetupChecklist`, `HelpChatbot/SuggestionChips` |
| Nav redirects | 4 | `TodaysFocusHeader`, `EmailDigestPage` (×2), `HelpStudyMenu` |

**Critical:** rename is **not** frontend-only. Backend deep-link generation (4 files) and mobile React Navigation symbols (6 references) make this a coordinated cross-stack PR. Keep `/my-kids` route as a 60-day redirect to `/bridge` for muscle memory + bookmarks.

---

## Files to touch (reference)

- `c:\dev\emai\emai-dev-03\frontend\src\pages\MyKidsPage.tsx` (1562 lines)
- `c:\dev\emai\emai-dev-03\frontend\src\pages\MyKidsPage.css`
- `c:\dev\emai\emai-dev-03\frontend\index.html` (only if fonts go global)
- `c:\dev\emai\emai-dev-03\frontend\src\components\EmailDigestSetupWizard.tsx` (no changes; trigger moves)
- `c:\dev\emai\emai-dev-03\frontend\src\components\GradesSummaryCard.tsx` (re-skin)
- `c:\dev\emai\emai-dev-03\frontend\src\components\StudyTimeSuggestions.tsx` (re-skin)
- `c:\dev\emai\emai-dev-03\frontend\src\components\bridge/` (new directory, 11 components)
