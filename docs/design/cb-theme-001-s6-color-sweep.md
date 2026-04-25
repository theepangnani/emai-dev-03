# CB-THEME-001 · S6 — Hardcoded color sweep coverage report

**Issue:** [#4162](https://github.com/theepangnani/emai-dev-03/issues/4162)
**Epic:** [#4155](https://github.com/theepangnani/emai-dev-03/issues/4155)
**Branch:** `feature/#4162-cb-theme-001-s6-color-sweep`
**Base:** `integrate/cb-theme-001` (rebased onto post-S3/S4/S5/S8 head)

## Summary

| Metric | Count |
|---|---:|
| Eligible CSS files (excluding `index.css`, `components/landing/**`, `*.test.*`, `LandingPageV2.css`) | 188 |
| **Active literals before** (excluding `var()` fallbacks, comments, `[data-landing="v2"]` blocks) | **1,235** |
| **Active literals after** | **1,045** |
| **Replaced this PR** | **190** |
| Reduction | 15.4% |
| CSS files modified | 68 |
| `npm run build` | clean |
| `npm run lint` | 0 errors (302 pre-existing warnings unchanged) |

> Note: a literal hex/rgba inside the second argument of `var(--name, #fallback)` is intentionally **not** swept — it serves as a graceful-degradation fallback if the custom property is undefined. Likewise, hex strings inside `/* ... */` comments (e.g., issue references like `#4133`) and inside the `[data-landing="v2"]` marketing-site block (CB-LAND-001 owned) are excluded.

## Mapping table — what was swept

Only **exact value-equivalence** swaps were applied to ensure `light` mode renders identically. The token system carries dark/focus/bridge variants for these tokens, so the swap also corrects literals that previously broke in non-light themes.

### Surfaces / ink
| Literal | → | Token |
|---|---|---|
| `#fff`, `#ffffff` (and uppercase) | → | `var(--color-surface)` |
| `#1b1e2b` | → | `var(--color-ink)` |
| `#5b6274` | → | `var(--color-ink-muted)` |
| `#f5f6f9` | → | `var(--color-surface-alt)` |
| `#eef1f5` | → | `var(--color-surface-bg)` |
| `#e3e6ee` | → | `var(--color-border)` |
| `rgba(255, 255, 255, 0.9)` | → | `var(--color-surface-header)` |

### Accents
| Literal | → | Token |
|---|---|---|
| `#4a90d9` | → | `var(--color-accent)` |
| `#2d6eb5` | → | `var(--color-accent-strong)` |
| `#f4801f` | → | `var(--color-accent-warm)` |
| `#1c5a9c` | → | `var(--color-accent-dark)` |
| `#d97745` | → | `var(--color-accent-warm-strong)` |
| `rgba(74, 144, 217, 0.12)` | → | `var(--color-accent-light)` |
| `rgba(74, 144, 217, 0.08)` | → | `var(--color-accent-subtle)` |

### Status
| Literal | → | Token |
|---|---|---|
| `#d64545` | → | `var(--color-danger)` |
| `rgba(214, 69, 69, 0.1)` | → | `var(--color-danger-light)` |
| `#f3b04c` | → | `var(--color-warning)` |
| `rgba(243, 176, 76, 0.15)` | → | `var(--color-warning-light)` |
| `#8a5a12` | → | `var(--color-warning-text)` |
| `#fff3e0` | → | `var(--color-warning-bg)` |
| `#ffe0b2` | → | `var(--color-warning-border)` |
| `#2e7d32` | → | `var(--color-success)` |
| `rgba(46, 125, 50, 0.12)` | → | `var(--color-success-light)` |
| `#246c2c` | → | `var(--color-success-dark)` |
| `#e8f5e9` | → | `var(--color-success-bg)` |
| `#c8e6c9` | → | `var(--color-success-border)` |
| `#1565c0` | → | `var(--color-info)` |
| `#e3f2fd` | → | `var(--color-info-bg)` |
| `#bbdefb` | → | `var(--color-info-border)` |

### Purple / blue families
| Literal | → | Token |
|---|---|---|
| `#7c3aed` | → | `var(--color-purple)` |
| `#6d28d9` | → | `var(--color-purple-strong)` |
| `#f5f3ff` | → | `var(--color-purple-light)` |
| `#ede9fe` | → | `var(--color-purple-bg)` |
| `#0d65b3` | → | `var(--color-blue)` |
| `#074b92` | → | `var(--color-blue-dark)` |

### Neutrals / overlays
| Literal | → | Token |
|---|---|---|
| `#888` | → | `var(--color-muted)` |
| `#aaa` | → | `var(--color-muted-light)` |
| `#d1d5db` | → | `var(--color-muted-border)` |
| `#c1c6d1` | → | `var(--color-inactive)` |
| `rgba(0, 0, 0, 0.5)` | → | `var(--color-overlay)` |
| `rgba(0, 0, 0, 0.3)` | → | `var(--color-overlay-light)` |
| `rgba(12, 18, 34, 0.05)` | → | `var(--bg-dot-color)` |
| `rgba(230, 233, 240, 0.9)` | → | `var(--skeleton-from)` |
| `rgba(245, 247, 251, 0.9)` | → | `var(--skeleton-mid)` |

## Mappings intentionally **not** applied

The following literals match a token by value but the matching tokens carry **narrowly-scoped semantic meaning** (priority levels, specific badges, role colors, brand colors). Auto-mapping a generic literal to one of these tokens would silently couple unrelated styles to that semantic. Page owners can opt in per-stream during S1–S5.

- `#ef5350`, `#ff9800`, `#66bb6a` (priority high/medium/low)
- `#9c27b0`, `#f57c00`, `#1976d2`, `#388e3c`, `#d32f2f` (badge syllabus/labs/readings/resources/assignments)
- `#b1571e`, `#a85f13` (role parent/admin)
- `#4285f4` (Google brand)
- `rgba(239, 83, 80, 0.12)`, `rgba(255, 152, 0, 0.12)`, `rgba(102, 187, 106, 0.12)`, `rgba(66, 133, 244, 0.12)`

Shadow-component rgbas (`rgba(19, 27, 46, 0.06|0.08|0.10|0.12|0.15|0.18)`) were not auto-substituted because they appear as pieces of larger composite shadows, not as standalone color values.

## Top 30 unmapped literals (followup candidates)

These literals do **not** match any existing token in the S0 palette and were left alone to avoid visual regression. Per the epic charter, S6 is **not** allowed to introduce new tokens — they should be added in a future stream and then bulk-swept.

| Count | Literal | Reason unmapped |
|---|---|---|
| 25 | `#fca5a5` | no exact-match token in S0 palette (Tailwind red-300) |
| 24 | `rgba(0, 0, 0, 0.06)` | shadow component or transient overlay; needs purpose-specific token |
| 23 | `rgba(0, 0, 0, 0.08)` | shadow component or transient overlay; needs purpose-specific token |
| 19 | `#f59e0b` | no exact-match token in S0 palette (Tailwind amber-500) |
| 16 | `#ef4444` | no exact-match token in S0 palette (Tailwind red-500) |
| 16 | `#fde68a` | no exact-match token in S0 palette (Tailwind amber-200) |
| 15 | `#92400e` | no exact-match token in S0 palette (Tailwind amber-800) |
| 15 | `#dc2626` | no exact-match token in S0 palette (Tailwind red-600) |
| 14 | `rgba(0, 0, 0, 0.12)` | shadow component or transient overlay; needs purpose-specific token |
| 13 | `#991b1b` | no exact-match token in S0 palette (Tailwind red-800) |
| 12 | `rgba(0, 0, 0, 0.2)` | shadow component or transient overlay; needs purpose-specific token |
| 12 | `#fee2e2` | no exact-match token in S0 palette (Tailwind red-100) |
| 12 | `#fef3c7` | no exact-match token in S0 palette (Tailwind amber-100) |
| 11 | `rgba(0, 0, 0, 0.15)` | shadow component or transient overlay; needs purpose-specific token |
| 11 | `#fef2f2` | no exact-match token in S0 palette (Tailwind red-50) |
| 10 | `#34d399` | no exact-match token in S0 palette (Tailwind emerald-400) |
| 10 | `#d97706` | no exact-match token in S0 palette (Tailwind amber-600) |
| 10 | `#fbbf24` | no exact-match token in S0 palette (Tailwind amber-400) |
| 10 | `#065f46` | no exact-match token in S0 palette (Tailwind emerald-800) |
| 9 | `rgba(255, 255, 255, 0.25)` | translucent white overlay; needs purpose-specific token |
| 9 | `#9ca3af` | no exact-match token in S0 palette (Tailwind gray-400) |
| 9 | `#e2e8f0` | no exact-match token in S0 palette (Tailwind slate-200) |
| 9 | `#3b82f6` | no exact-match token in S0 palette (Tailwind blue-500) |
| 8 | `rgba(0, 0, 0, 0.18)` | shadow component or transient overlay; needs purpose-specific token |
| 8 | `rgba(253, 230, 138, 0.14)` | dark-theme palette literal; should bind to a warning-bg variant |
| 8 | `#6b7280` | no exact-match token in S0 palette (Tailwind gray-500) |
| 8 | `rgba(0, 0, 0, 0.1)` | shadow component or transient overlay; needs purpose-specific token |
| 8 | `#e5e7eb` | no exact-match token in S0 palette (Tailwind gray-200) |
| 7 | `#b91c1c` | no exact-match token in S0 palette (Tailwind red-700) |
| 7 | `#dcfce7` | no exact-match token in S0 palette (Tailwind green-100) |

(Full list — 95+ distinct literal values across 108 files — captured in script output `c:/tmp/after_remaining.json`)

## Followup issues

The unmapped literals fall into a small number of color clusters that could be cleanly mapped if we add ~12 new tokens. Per the epic charter, S6 is forbidden from introducing tokens, so the following followups are opened:

1. **Followup A — Tailwind-style palette tokens** — [#4235](https://github.com/theepangnani/emai-dev-03/issues/4235)
   Many shipped CSS files import Tailwind-style hexes (`#6b7280`, `#e5e7eb`, `#fca5a5`, `#ef4444`, `#f59e0b`, `#fde68a`, etc.). Add a `--color-neutral-{50..900}`, `--color-red-{50..900}`, `--color-amber-{50..900}` token family aligned with the bridge palette and re-run the sweep.

2. **Followup B — Standalone shadow-strength rgbas** — [#4236](https://github.com/theepangnani/emai-dev-03/issues/4236)
   `rgba(0, 0, 0, 0.06|0.08|0.10|0.12|0.15|0.18|0.2|0.25|0.3|0.4|0.5)` are composed into ad-hoc `box-shadow` declarations across ~80 files. Add `--shadow-color-low|med|high` (or move all card shadows behind `--shadow-{xs..xl}` which already exist) and sweep.

3. **Followup C — Inline `style={{ ... }}` in `.tsx`** — [#4237](https://github.com/theepangnani/emai-dev-03/issues/4237)
   ~73 inline-style hex usages in `.tsx` files (most under `pages/parent/`, `pages/Account*`, `pages/Admin*`). Sweep separately because the AST handling differs from CSS regex; can be batched with stream S5 chrome work.

4. **Followup D — Translucent surface tokens** — [#4238](https://github.com/theepangnani/emai-dev-03/issues/4238)
   `rgba(255, 255, 255, 0.25|0.5|0.08|0.2)` appear as overlay treatments across modals and FABs. Add `--color-surface-translucent-{light,med,strong}` and sweep.

## Files modified — replacement counts (68 files)

| File | Replaced | Remaining (raw, includes fallbacks) |
|---|---:|---:|
| `frontend/src/components/asgf/ASGFComprehensionSignal.css` | 11 | 21 |
| `frontend/src/components/asgf/ASGFAssignment.css` | 9 | 38 |
| `frontend/src/components/asgf/ASGFResumePrompt.css` | 7 | 13 |
| `frontend/src/components/HelpChatbot/HelpChatbot.css` | 7 | 23 |
| `frontend/src/components/NotesPanel.css` | 6 | 89 |
| `frontend/src/components/QuizOfTheDay.css` | 6 | 13 |
| `frontend/src/pages/parent/EmailDigestPage.css` | 6 | 139 |
| `frontend/src/pages/AdminContactsPage.css` | 5 | 20 |
| `frontend/src/pages/CourseMaterialDetailPage.css` | 5 | 46 |
| `frontend/src/components/ile/AhaMomentCelebration.css` | 4 | 9 |
| `frontend/src/components/StudyGuideSuggestionChips.css` | 4 | 19 |
| `frontend/src/pages/BridgePage.css` | 4 | 45 |
| `frontend/src/pages/CsvImportPage.css` | 4 | 48 |
| `frontend/src/pages/MyKidsPage.css` | 4 | 18 |
| `frontend/src/pages/parent/ReportCardAnalysis.css` | 4 | 61 |
| `frontend/src/pages/StudyPage.css` | 4 | 15 |
| `frontend/src/pages/TutorPage.css` | 4 | 9 |
| `frontend/src/components/asgf/ASGFProgressInterstitial.css` | 3 | 31 |
| `frontend/src/components/asgf/ASGFUploadZone.css` | 3 | 43 |
| `frontend/src/components/cycle/cycle.css` | 3 | 24 |
| `frontend/src/components/GoogleClassroomPrompt.css` | 3 | 23 |
| `frontend/src/components/parent/RecentActivityPanel.css` | 3 | 19 |
| `frontend/src/components/parent/ReportCardAnalysisView.css` | 3 | 59 |
| `frontend/src/components/SelectionTooltip.css` | 3 | 16 |
| `frontend/src/components/study/MaterialTypeSuggestionChips.css` | 3 | 21 |
| `frontend/src/components/UploadMaterialWizard.css` | 3 | 108 |
| `frontend/src/pages/parent/ParentAITools.css` | 3 | 44 |
| `frontend/src/pages/ReadinessCheckPage.css` | 3 | 40 |
| `frontend/src/pages/StudentDashboard.css` | 3 | 27 |
| `frontend/src/pages/StudyTimelinePage.css` | 3 | 27 |
| `frontend/src/pages/SurveyPage.css` | 3 | 4 |
| `frontend/src/components/briefing/DailyBriefingCard.css` | 2 | 49 |
| `frontend/src/components/briefing/WeeklyDigestCard.css` | 2 | 43 |
| `frontend/src/components/GenerateSubGuideModal.css` | 2 | 5 |
| `frontend/src/components/GradesSummaryCard.css` | 2 | 4 |
| `frontend/src/components/JourneyWelcomeModal.css` | 2 | 9 |
| `frontend/src/components/MaterialContextMenu.css` | 2 | 2 |
| `frontend/src/components/PomodoroTimer.css` | 2 | 20 |
| `frontend/src/components/study/ChildInlinePills.css` | 2 | 11 |
| `frontend/src/components/study/FormatSelector.css` | 2 | 7 |
| `frontend/src/pages/AdminFeaturesPage.css` | 2 | 22 |
| `frontend/src/pages/AdminOutreachComposer.css` | 2 | 47 |
| `frontend/src/pages/CourseDetailPage.css` | 2 | 17 |
| `frontend/src/pages/CoursesPage.css` | 2 | 16 |
| `frontend/src/pages/GradesPage.css` | 2 | 15 |
| `frontend/src/pages/parent/ActivityHistoryPage.css` | 2 | 28 |
| `frontend/src/pages/ReportCardPage.css` | 2 | 25 |
| `frontend/src/pages/StudyGuidePage.css` | 2 | 41 |
| `frontend/src/components/asgf/ASGFContextPanel.css` | 1 | 23 |
| `frontend/src/components/asgf/ASGFErrorRecovery.css` | 1 | 30 |
| `frontend/src/components/AssessmentCountdown.css` | 1 | 12 |
| `frontend/src/components/briefing/ConversationStartersCard.css` | 1 | 29 |
| `frontend/src/components/CreditTopUpModal.css` | 1 | 22 |
| `frontend/src/components/demo/TuesdayMirror.css` | 1 | 10 |
| `frontend/src/components/parent/ReportCardUploadModal.css` | 1 | 45 |
| `frontend/src/components/ResourceLinksSection.css` | 1 | 10 |
| `frontend/src/components/RoleQuickActions.css` | 1 | 6 |
| `frontend/src/components/SectionPanel.css` | 1 | 5 |
| `frontend/src/components/SpeedDialFAB.css` | 1 | 12 |
| `frontend/src/components/study/HelpStudyMenu.css` | 1 | 12 |
| `frontend/src/components/SubGuidesPanel.css` | 1 | 20 |
| `frontend/src/components/tutorial/TutorialOverlay.css` | 1 | 13 |
| `frontend/src/pages/course-material/MindMapTab.css` | 1 | 17 |
| `frontend/src/pages/HelpPage.css` | 1 | 11 |
| `frontend/src/pages/Onboarding.css` | 1 | 4 |
| `frontend/src/pages/ParentBriefingNotesPage.css` | 1 | 21 |
| `frontend/src/pages/QuizPage.css` | 1 | 7 |
| `frontend/src/pages/StudyGuidesPage.css` | 1 | 24 |

## Skipped files (per stream charter)

- `frontend/src/index.css` — owns the token system; out of scope for S6.
- `frontend/src/components/landing/**` — CB-LAND-001 marketing-site scope.
- `frontend/src/pages/LandingPageV2.css` — CB-LAND-001 (uses `.landing-v2-*` selectors); reverted after sweep.
- `[data-landing="v2"]` blocks anywhere — CB-LAND-001 scope; the sweep tool walks balanced `{}` braces to detect and skip these.
- `*.test.*` snapshot files.
- All eligible `.tsx` inline-style hex literals — deferred to **Followup C** above.
- **Six files owned by merged in-flight streams** (S3 teacher, S4 admin, S5 chrome) skipped to avoid conflicts:
  - `frontend/src/components/NotesFAB.css`
  - `frontend/src/components/TeacherCourseManagement.css`
  - `frontend/src/pages/AdminAIUsagePage.css`
  - `frontend/src/pages/AdminSurveyPage.css`
  - `frontend/src/pages/AdminWaitlistPage.css`
  - `frontend/src/pages/Dashboard.css`
  - `frontend/src/components/AddActionButton.css` (already token-clean post-S5)

## Method (script reproducible)

The sweep is deterministic and re-runnable. Running the same script twice on the post-PR state will be a no-op.

```text
python sweep.py eligible_files.txt
```

The script:
1. Walks each eligible CSS file
2. For every regex match of `#[0-9a-fA-F]{3,8}\b` or `rgba?\([^)]+\)`:
   - Skips matches inside `/* … */` comments
   - Skips matches inside the second argument of `var(--name, …)`
   - Skips matches inside `[data-landing="v2"] { … }` blocks (with brace tracking)
3. If the literal (or normalized rgba string) is in the **safe-mapping table**, replaces it.
4. Writes per-file replacement counts to `sweep_audit.json`.

## Acceptance criteria status

- [x] Coverage report attached to PR (this document)
- [ ] >95% of literals replaced — **15.4% achieved**; the remainder require new tokens (out of scope for S6 per epic charter). Followups A–D documented above carry the remaining work.
- [x] `npm run build` clean
- [x] `npm run lint` 0 errors (302 pre-existing warnings unchanged)
- [ ] No visual regression — verified via static reasoning (only exact-value swaps to existing tokens). S9 screenshot diff will validate.
- [ ] 1× `/pr-review` pass — pending

The 95% target is **not achievable in S6 alone** without violating the epic-level guardrail "DO NOT introduce new tokens." Per the issue text ("If a literal cannot be cleanly mapped, file a follow-up issue"), the four follow-ups above carry the remaining work into a future stream that would land alongside or after the new token additions.
