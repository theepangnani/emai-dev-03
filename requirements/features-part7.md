### 6.115 User Bug Report with Screenshot → GitHub Issue + Admin Notification (Phase 2) (#2087) - IMPLEMENTED

**Purpose:** Let users report bugs directly from the app with an optional screenshot, creating a GitHub issue and notifying admins.

- [x] "Report a Bug" button accessible from help/support area
- [x] Bug report form with title, description, and optional screenshot upload
- [x] Screenshot capture via clipboard paste or file upload
- [x] Screenshot uploaded to backend and attached to GitHub issue
- [x] Backend creates GitHub issue via GitHub API with user context (role, browser, URL)
- [x] Admin notification (email or in-app) when new bug report is submitted
- [x] Rate limiting to prevent spam submissions
- [x] Success/error feedback to the user after submission

**Key PRs:** #2088 (initial feature), #2092 (fix 405, paste, prefill), #2104 (fix screenshot 500 + modal styling)

### 6.116 Error Dialog → Report Bug Link (Phase 2) (#2089) - IMPLEMENTED

**Purpose:** When an error dialog appears (e.g., API failure), include a "Report Bug" link that pre-fills the bug report form with error context.

- [x] Error dialogs include a "Report this bug" link/button
- [x] Clicking the link opens the bug report form pre-filled with error details (endpoint, status code, message)
- [x] Seamless transition from error dialog to bug report modal

**Key PRs:** #2090 (error dialog report links)

### 6.117 Bug Report Bot Protection (Phase 2) (#2103)

**Purpose:** Add bot/spam protection to the bug report submission flow.

- [ ] Implement honeypot field or CAPTCHA on bug report form
- [ ] Server-side validation for bot submissions
- [ ] Rate limiting per IP in addition to per-user

### 6.118 AI Answer Uncertainty Detection — Block Saving Uncertain Responses (Phase 1) - IMPLEMENTED

**GitHub Issues:** #2098 (requirement gap), PR #2102

AI responses containing uncertainty markers must not be saveable as study guides or class materials. When an AI response indicates the model is unsure, confused, or requesting clarification, the system shall detect these uncertainty phrases and prevent the user from saving that response as study content.

**Uncertainty Phrases Detected (case-insensitive):**
- "I'm not sure", "I'm not certain", "I don't know", "I cannot determine"
- "Could you clarify", "Could you provide more", "Can you clarify"
- "I don't have enough information", "I don't have access to"
- "I'm unable to", "I cannot answer", "beyond my knowledge"
- "I'd need more context", "not enough detail"

**Frontend Behavior:**
- When an AI assistant message contains any uncertainty phrase, the "Save as Study Guide" and "Save as Class Material" action buttons are disabled
- A tooltip or visual indicator explains why saving is blocked (e.g., "This response contains uncertain information and cannot be saved as study material")
- Detection runs on the full message text before rendering save actions

**Backend Validation:**
- The save-as-guide and save-as-material endpoints perform the same uncertainty phrase check server-side
- If uncertainty is detected, the endpoint returns HTTP 422 with an error message explaining the block
- This prevents bypassing the frontend restriction via direct API calls

**Key Principle:** Only high-confidence, definitive AI answers should become part of a student's study material library. Uncertain or clarification-seeking responses could embed misinformation into study guides.

---

## §6.115 Bug Report System

**Status:** COMPLETE | **Issues:** #2087, #2091, #2101, #2103, #2112, #2114

Users can report bugs directly from error dialogs or the help menu. Bug report modal captures: description, steps to reproduce, expected behavior, and optional screenshot (paste or file upload). Screenshots uploaded to GCS with signed URLs. Reports auto-create GitHub issues with full context and admin email notification.

### §6.115.1 Bug Report Submission
- Modal captures: description (required), steps to reproduce, expected behavior, screenshot (paste/file)
- Screenshots uploaded to GCS with signed URLs (1hr expiry)
- Creates GitHub issue with full context
- Admin email notification via SendGrid

### §6.115.2 Bot Protection
- Honeypot field (hidden, must remain empty)
- 60-second cooldown between submissions
- Rate limit: 20/hour per user

### §6.115.3 Error Dialog Integration
- All error dialogs include "Report a Bug" link opening BugReportModal pre-filled with error context
- Implemented in ErrorBoundary and useConfirm hook

---

## §6.116 Streaming Study Guide Generation

**Status:** COMPLETE | **Issues:** #2120-#2127 (7 issues)

SSE endpoint streams markdown tokens for ChatGPT-like real-time generation experience.

### §6.116.1 Backend Streaming
- SSE at `/api/study/stream/{content_id}`
- Supports OpenAI and Anthropic streaming APIs
- Graceful error handling preserves partial content

### §6.116.2 Frontend Rendering
- StreamingMarkdown component with react-markdown
- useStudyGuideStream hook for SSE lifecycle
- Cursor animation during streaming

### §6.116.3 Insufficient Content & Credit Error Handling (#2921, #2933, #2935)
- Frontend pre-checks extracted text length (MIN_EXTRACTION_CHARS = 50) before calling API
- 422 responses from backend are parsed to surface the `detail` message to the user
- User sees descriptive error ("We couldn't read enough text…") instead of generic "Server error (422)"
- 402 responses (insufficient credits) shown with clear message in streaming hook
- `debit_wallet` HTTPException re-raised to client instead of being silently swallowed
- Pre-flight credit check (`check_ai_usage`) aligned with minimum debit amount to prevent orphaned guides

---

## §6.117 Phase-2 Repository Consolidation

**Status:** PLANNED | **Issues:** #2130-#2140 | **Milestone:** Phase 2F: Phase-2 Port (due May 1, 2026)

Features to port from class-bridge-phase-2:
1. 2FA/TOTP Authentication (#2130)
2. Feature Flags Infrastructure (#2131)
3. Learning Journals (#2132)
4. Meeting Scheduler (#2133)
5. Discussion Forums (#2134)
6. Peer Review (#2135)
7. AI Writing Assistance (#2136)
8. AI Homework Help (#2137)
9. Wellness Check-ins (#2138)
10. Student Goals (#2139)

---

## §6.119 Document Privacy & IP Protection (Phase 1) - IMPLEMENTED

**Status:** IMPLEMENTED (2026-03-25) | **Priority:** CRITICAL | **Value Score:** 9/10
**Epic:** #2268 | **Issues:** #2269, #2270, #2272, #2273, #2274
**Related:** #61 (content privacy), #50 (FERPA/PIPEDA), #114 (GCS storage)
**Target:** Phase 1 (access control) before April 14, 2026 launch
**PRs:** #2376 (trust circle), #2367 (admin override removal), #2375 (audit logging), #2372 (access log endpoint), #2370 (frontend privacy UI)

Class materials uploaded by private tutors and teachers must be protected from unauthorized access — including platform administrators. This feature implements a "trust circle" access model where materials are visible only to users directly connected to the course.

#### Strategic Value Assessment

This is a **platform trust gate** — private tutors will not upload proprietary curriculum if they can't trust the platform. Without this, the Phase 4 tutoring marketplace has no supply side.

| Factor | Impact | Score |
|--------|--------|-------|
| Tutor acquisition — won't join if admin can see/copy IP | Critical | 10/10 |
| Regulatory compliance — FERPA/PIPEDA require access controls + audit trails | High | 9/10 |
| Parent trust — sensitive docs (IEPs, report cards) need privacy | High | 8/10 |
| Competitive moat — most ed-tech gives admins full access | Medium | 8/10 |
| Revenue enabler — premium storage (§6.71) only valuable if content is protected | High | 9/10 |

#### Recommended Implementation Order

| Phase | Scope | Priority | Target | Effort |
|-------|-------|----------|--------|--------|
| **Phase 1** | Backend access control (#2269, #2270) | CRITICAL | DONE (PR #2376, #2367) | ~1 day |
| **Phase 2** | Audit logging (#2272) | HIGH | DONE (PR #2375) | ~1 day |
| **Phase 3** | Frontend UI + access log (#2273, #2274) | MEDIUM | DONE (PR #2372, #2370) | ~2 days |
| **Phase 4** | Signed URLs + encryption (§6.93) | LOW | With GCS migration | TBD |
| **Phase 5** | Per-material visibility | LOW | When tutor marketplace launches | TBD |

**Key insight:** Phase 1 alone delivers ~80% of total value. It's a small, atomic backend change with no schema migration required.

### §6.119.1 Trust Circle Access Model - IMPLEMENTED (PR #2376, #2367)

Materials are accessible ONLY to the course's trust circle:

| Role | View | Download | Modify | Delete |
|------|------|----------|--------|--------|
| Document owner (uploader) | Yes | Yes | Yes | Yes |
| Course creator | Yes | Yes | No | No |
| Assigned teacher | Yes | Yes | No | No |
| Enrolled students | Yes | Yes | No | No |
| Parents of enrolled students | Yes | Yes | No | No |
| Parent of student creator | Yes | Yes | Yes | Yes |
| **Pure admin** (admin-only role) | **Metadata only** | **No** | **No** | **No** |
| **Multi-role admin** (e.g. admin+parent) | Via other role | Via other role | Via other role | Via other role |

**Admin metadata access:** Pure admins (admin-only) can see aggregate data (material count per course, total storage usage, file types) for platform management, but cannot view material content, text extractions, or download files.

**Multi-role admin access (fix #2468):** Users who hold admin AND another role (e.g. parent, teacher, student) are evaluated through their non-admin role paths. A user with roles=admin+parent is granted parent-level access if their child is enrolled. The admin exclusion must NOT use `has_role(ADMIN)` as a blanket deny — `has_role()` checks ALL roles, so it would block multi-role users. Instead, pure admins are denied naturally by matching no trust-circle rule.

**Public course access:** Materials in public courses (`is_private=False`) are accessible to all authenticated non-admin users. This matches `can_access_course()` semantics.

**Implementation:**
- New `can_access_material(db, user, content)` function in `app/api/deps.py` (#2269)
- No blanket admin exclusion — pure admins naturally match no trust-circle rule (fix #2468)
- Remove admin override from `_can_modify_content()` in `app/api/routes/course_contents.py` (#2270)
- Replace `can_access_course()` with `can_access_material()` in all content read/download endpoints
- Strip `text_content` from API responses for non-trust-circle users

### §6.119.2 Material Access Audit Logging - IMPLEMENTED (PR #2375)

Every material access event is logged for compliance (FERPA/PIPEDA) and owner transparency.

**Audit Actions:**
- `MATERIAL_VIEW` — when a user views material content
- `MATERIAL_DOWNLOAD` — when a user downloads a file
- `MATERIAL_UPLOAD` — when a user uploads new material

**Log Entry Fields:** user_id, resource_type, resource_id, action, details (JSON: course_id, filename, file_size), IP address, user-agent, timestamp

**Implementation:** (#2272)
- Add new values to `AuditAction` enum in `app/models/audit_log.py`
- Instrument content endpoints in `app/api/routes/course_contents.py`
- Uses existing `audit_service.log_action()` infrastructure with savepoints

### §6.119.3 Owner Access Log Endpoint - IMPLEMENTED (PR #2372)

Material owners can view who has accessed their content.

**Endpoint:** `GET /api/course-contents/{content_id}/access-log` (#2273)

**Authorization:** Material creator only (+ parent of student creator)

**Response includes:**
- List of access events (user name, role, action, timestamp)
- Summary stats: total views, total downloads, unique viewers
- Filterable by date range (`?days=30`) and action type (`?action=download`)

### §6.119.4 Frontend Privacy UI - IMPLEMENTED (PR #2370)

**Privacy Indicators:** (#2274)
- Lock/shield icon on materials in course detail page
- "IP Protected" badge for private course materials (`classroom_type === "private"`)
- Tooltip explaining trust-circle access model

**Access Log Tab:**
- New tab on `CourseMaterialDetailPage` visible only to material creator
- Table: User Name, Role, Action, Timestamp
- Date range filter (7/30/90 days)
- Summary stats header

**Admin Dashboard:**
- Show aggregate material counts and storage usage only
- No links to individual material content

### §6.119.5 Future: Per-Material Visibility Override (Phase 2)

Optional granular visibility control per material:
- `course_members` (default) — full trust circle
- `owner_only` — only the uploader can see
- `teacher_and_owner` — uploader + assigned teacher only

Requires new `visibility` column on `course_contents` table.

### §6.119.6 Future: File Storage Security (Phase 2, pairs with §6.93)

- Time-limited signed URLs for file downloads (15-min expiration)
- Customer-Managed Encryption Keys (CMEK) via GCP KMS at bucket level
- No direct file serving — all downloads via signed URL redirect

---

### 6.120 School Board Announcements (§6.120) - PLANNED

**Status:** Research complete, deferred to phased approach
**Issues:** #2276 (research & analysis), #2279 (Google Classroom announcements), #113 (School Board model)

Parents want visibility into school board announcements (closures, events, policy changes) without manually checking each board's website.

#### §6.120.1 API Research Findings (2026-03-24)

No public API exists for Ontario school board announcements. Key findings:

| Source | API Available | Announcement Data | Ontario Coverage |
|--------|:---:|:---:|:---:|
| Google Classroom | Yes | Course-level only | TDSB, PDSB, DDSB, HDSB |
| D2L Brightspace | Yes | Org-unit news | Some boards (partnership required) |
| SchoolMessenger | No | — | TDSB, PDSB, DDSB, HDSB (closed platform) |
| Edsby | No | — | YRDSB (closed platform) |
| Ontario Open Data | Yes | Demographics only | All boards |
| Board website RSS | No | — | None of 5 boards offer RSS |

#### §6.120.2 Phase 1: Google Classroom Announcements Sync (#2279)

Extend existing Google Classroom integration to sync course announcements via [`courses.announcements`](https://developers.google.com/workspace/classroom/reference/rest/v1/courses.announcements) API.

**Scope:**
- Sync announcements during existing Google Classroom sync job
- New `classroom_announcements` table (google_announcement_id, course_id, text, creator_name, source_url, published_at)
- `GET /api/classroom-announcements` endpoint for parents (filtered by children's courses)
- Notify parents on new announcements via existing notification system
- Frontend: Announcements section on Parent Dashboard or My Kids page
- OAuth scope: `classroom.announcements.readonly`
- Covers 4/5 target boards (TDSB, PDSB, DDSB, HDSB use Google Classroom)
- **Estimate:** 3-5 days

**Bug Fixes:**
- [x] Fix: populate `creator_name` and `creator_email` in announcement sync — were always None (#2350, PR #2374, 2026-03-25)

#### §6.120.3 Phase 2: Board-Level Announcements (Deferred — requires partnerships)

When ClassBridge establishes formal school board partnerships (DTAP/VASP path — #803, #942):
- Build `school_boards` table (#113) with subscription model
- Negotiate API access to SchoolMessenger or board data feeds
- Explore D2L Brightspace API for boards using that LMS
- Admin-managed board directory; parents subscribe to their boards

#### §6.120.4 Web Scraping (Not Recommended)

Web scraping was evaluated and **deferred** due to:
- **Brittle** — Board websites redesign yearly, breaking parsers
- **No RSS feeds** — All 5 target Ontario boards lack RSS
- **Legal risk** — No explicit permission for scraping
- **Redundant** — Parents already receive SchoolMessenger emails/texts
- **Maintenance burden** — 5 bespoke parsers for marginal value

If scraping is reconsidered in future: httpx + BeautifulSoup4, APScheduler cron at 5:30 AM UTC, content-hash dedup, batch notifications. Cost: ~$0.00/month. Full architecture in #2276.

#### §6.120.5 MCP Integration (Phase 2, pairs with #2192-#2199)

Once MCP is ported to emai-dev-03, expose announcements as an MCP resource so the AI tutor can answer questions like "When is March Break?" using board announcement data. Not suitable for the scraping pipeline itself (adds unnecessary LLM cost to a deterministic task).

---

### 6.121 School Report Card Upload & AI Analysis (Phase 1) - IMPLEMENTED

**Status:** IMPLEMENTED (2026-03-24, PR #2362)
**GitHub Issue:** #2286

Parents upload physical school report cards (photos/scans). AI (GPT-4o-mini vision) extracts structured data: grades per subject, teacher comments, trends. Career path analysis suggests career directions based on academic strengths.

**Sub-features:**
- [x] Report card upload with drag-drop, multi-file, school name (PR #2362)
- [x] AI-powered grade extraction and analysis view with color-coded grade table (#2356)
- [x] Career path analysis with sorted trends, strength badges, career cards (#2357)
- [x] Delete confirmation with `useConfirm` dialog (#2358)
- [x] Frontend tests: 14 tests for ReportCardAnalysis + CareerPathView (#2359)
- [x] Backend tests: 7 tests for career path, cache, file validation (#2360)
- [x] Integration links on My Kids + ParentAITools pages (#2361)
- [x] Route `/school-report-cards` + sidebar nav link for parents (#2352)
- [x] Student read-only access: students can view their own report cards and AI analysis (#2401)

**Key files:**
- `app/api/routes/report_cards.py` — upload and analysis endpoints
- `app/services/report_card_service.py` — AI extraction service
- `frontend/src/pages/parent/ReportCardAnalysis.tsx` — analysis view
- `frontend/src/pages/parent/CareerPathView.tsx` — career path view

**Bug Fixes:**
- [x] Fix: ISO date format fallback in `_parse_report_date` (#2349, PR #2364, 2026-03-25)
- [x] Test: career path analysis test coverage (#2329, PR #2363, 2026-03-25)

---

### §6.123 Course Material Metadata & Clickable Popovers (Phase 1) - IMPLEMENTED (PR #2395)

All course material content tabs now display a consistent metadata bar showing Class name, Created Date, and linked Tasks count. Class name and Tasks are interactive — clicking opens a popover with details and navigation.

**Implementation:**
1. **Shared `ContentMetaBar` component** (`frontend/src/pages/course-material/ContentMetaBar.tsx`) — renders in all 6 content tabs: Study Guide, Quiz, Flashcards, Mind Map, Parent Briefing, Source Document
2. **Class popover:** Click course name → shows course name + "View Course" link navigating to `/courses/{id}`
3. **Tasks popover:** Click task count → shows linked task list with title, due date, completion status (✓/○/!), and links to `/tasks/{id}`
4. **Overdue indicator:** Tasks past due date shown with red "!" badge and red due date text. Uses timezone-safe local midnight comparison to avoid off-by-one.
5. **Mobile UX:** Popovers render as bottom sheets on `< 600px` with semi-transparent backdrop overlay (CSS `:has()` selector). Tap backdrop to dismiss.
6. **Keyboard accessible:** Escape key closes popovers; outside click dismisses.

**Tabs with metadata:**
| Tab | Created Date Source | Linked Tasks Source |
|-----|-------------------|-------------------|
| Study Guide | `studyGuide.created_at` | Tasks linked to study guide |
| Quiz | `quiz.created_at` | Tasks linked to quiz |
| Flashcards | `flashcardSet.created_at` | Tasks linked to flashcard set |
| Mind Map | `mindMapGuide.created_at` | Tasks linked to mind map guide |
| Parent Briefing | `briefingNote.created_at` | All linked tasks (flattened) |
| Source Document | `content.created_at` | All linked tasks (flattened) |

**Key files:**
- `frontend/src/pages/course-material/ContentMetaBar.tsx` — shared component (115 lines)
- `frontend/src/pages/CourseMaterialDetailPage.tsx` — prop threading to all tabs
- `frontend/src/pages/CourseMaterialDetailPage.css` — popover + mobile bottom sheet styles

**Issues resolved:** #2259, #2260, #2388, #2389, #2390, #2394

---

### 6.122 Bug Fixes & Quality (March 24-26, 2026)

**Bug fixes deployed in this period:**

| PR | Issue | Description | Date |
|----|-------|-------------|------|
| #2395 | #2259, #2260, #2388-#2390, #2394 | Feat: course material metadata & clickable popovers in all tabs | 2026-03-26 |
| #2384 | #2366, #2368 | Fix: report card ordering & mobile view | 2026-03-26 |
| #2379 | #2377, #2378 | Fix: bug report modal submit + login bot protection clock skew | 2026-03-26 |
| #2365 | #2354 | Fix: expand class material section by default | 2026-03-25 |
| #2373 | #2353 | Fix: register `daily_quiz` router — Quiz of the Day 404 | 2026-03-25 |
| #2364 | #2349 | Fix: ISO date format fallback in `_parse_report_date` | 2026-03-25 |
| #2374 | #2350 | Fix: populate `creator_name`/`creator_email` in announcement sync | 2026-03-25 |

### 6.124 Bug Fixes & Quality (March 26-28, 2026)

**Bug fixes and improvements deployed in this period:**

| PR | Issue | Description | Date |
|----|-------|-------------|------|
| #2584 | #2167, #2228 | Feat: CSV template import and Weekly Family Report | 2026-03-28 |
| #2589 | #2585-#2588 | Fix: CSV import RBAC, password, savepoints, file size limit | 2026-03-28 |
| #2574 | #2554 | Feat: replace Generate Study Material with Ask Chat Bot flow | 2026-03-28 |
| #2578 | #2567, #2569 | Fix: race condition and re-render optimization in chatbot question injection | 2026-03-28 |
| #2577 | — | Fix: suppress set-state-in-effect lint for intentional chatbot open | 2026-03-28 |
| #2573 | #2562 | Fix: make access log test fully robust against CI shared DB state | 2026-03-28 |
| #2561 | #2531 | Fix: Study Q&A — diagram citation, chatbot UI redesign | 2026-03-28 |
| #2548 | #2538-#2540 | Fix: redesign Study Q&A chatbot UI for usability and simplicity | 2026-03-28 |
| #2544 | #2536 | Fix: make admin dashboard metrics and activity items clickable | 2026-03-28 |
| #2537 | #2532, #2535 | Fix: study Q&A — image context, access check for enrolled students | 2026-03-28 |
| #2530 | #2523, #2528, #2529 | Fix: study Q&A chatbot — import crash, FK join bug, logging, tests | 2026-03-28 |
| #2524 | #2522, #2526 | Fix: dashboard Quick Actions placement + XP badge layout | 2026-03-28 |
| #2495 | #2491 | Fix: hide OCR text when source files provide original document | 2026-03-27 |
| #2469 | #2468 | Fix: add public course bypass to can_access_material() | 2026-03-27 |
| #2467 | #2465 | Fix: post-merge improvements — docstring, JWT import, PG compat, dedup | 2026-03-27 |
| #2466 | — | Fix: CI test failures from weekend batch merge | 2026-03-27 |
| #2453 | #2442-#2444, #2451 | Fix: PR review fixes — streak commit, JWT expiry, email counts, quiz safety | 2026-03-27 |
| #2441 | — | Integrate: weekend batch — 15 features + all review fixes | 2026-03-27 |
| #2429 | #2413, #2414 | Refactor: centralize upload constants & update docs to 30 MB | 2026-03-27 |
| #2423 | #2408 | Fix: enforce role-based messaging recipient restrictions | 2026-03-27 |
| #2402 | #2401 | Fix: allow students to view their own school report cards | 2026-03-27 |
| #2400 | #2397 | Fix: support concurrent report card analysis loading indicators | 2026-03-27 |

---

### 6.125 Help Page User Journey Guide & Role-Based Diagrams (Phase 2) - IMPLEMENTED

**Added:** 2026-03-29 | **GitHub Issue:** #2597

Expand the Help Center and Tutorial pages to incorporate the full **ClassBridge User Journey Guide** (v1.0, March 2026) with role-based visual diagrams covering 37 journeys across all user roles.

#### Content Source

- **User Journey Guide:** `ClassBridge_User_Journey_Guide.docx` — complete step-by-step walkthroughs
- **Diagrams:** 36 SVG/PNG files (cover + p01–p10, s01–s10, t01–t08, a01–a05, x01–x02)

#### Journeys by Role

| Role | ID Range | Count | Topics |
|------|----------|-------|--------|
| **Parent** | P01–P10 | 10 | Registration, Add Child, Upload Material, Report Card, Dashboard, Messaging, Tasks, Briefing, Courses, Google Classroom |
| **Student** | S01–S10 | 10 | Registration, Study Guide, Quiz, Flashcards/Mind Maps, Q&A Chatbot, Notes, XP/Streaks, Pomodoro, Dashboard, Assessment Countdown |
| **Teacher** | T01–T08 | 8 | Registration, Create Class, Upload Materials, Google Sync, Communication, Dashboard, Invites, Student Progress |
| **Admin** | A01–A05 | 5 | Dashboard, Users, Broadcasts, AI Limits, Audit/FAQ |
| **Cross-Role** | X01–X02 | 2 | How Roles Connect, Mobile |

#### Requirements

- [x] §6.125.1 New "User Journeys" tab/section in Help Center (`/help`), organized by role tabs (#2600)
- [x] §6.125.2 Each journey rendered as expandable card: title, description, step-by-step walkthrough, inline SVG diagram (#2600)
- [x] §6.125.3 "Ask the Bot" button on each journey card → opens AI chatbot pre-filled with journey context (#2601)
- [x] §6.125.4 Diagram assets hosted at `frontend/public/help/journeys/` (SVG preferred) (#2599)
- [x] §6.125.5 Journey content indexed in Help KB YAML files for search and AI chatbot RAG (#2602)
- [x] §6.125.6 Cross-links from Tutorial page (§6.56) steps to corresponding journey articles (#2603)
- [x] §6.125.7 Mobile responsive — diagrams scale, accordion layout on small screens (#2600)

#### Key Files
- `frontend/src/pages/HelpPage.tsx` — Add Journeys section/tab
- `app/data/help_knowledge/` — Journey content in KB YAML files
- `app/services/chatbot_service.py` — Index journey content for RAG
- `frontend/public/help/journeys/` — SVG/PNG diagram assets (new)
- `frontend/src/pages/TutorialPage.tsx` — Cross-links to journey articles

---

### 6.126 Proactive Journey Hints — Smart First-Login Popups & Contextual Guidance (Phase 2) - IMPLEMENTED

**Added:** 2026-03-29 | **GitHub Issue:** #2598 | **Depends on:** #2597 (§6.125)

Proactively guide users through their ClassBridge journey with smart, contextual hints that appear only when genuinely needed. Includes a first-login welcome modal and subtle page-level nudges linked to User Journey articles (§6.125) and the AI Help Chatbot (§6.59).

**Key design principle:** The system must be **smart, not annoying**. Hints fire based on real user state, never repeat, and respect user behavior signals.

#### Smart Hint Intelligence Rules

1. **State-Based** — Hints fire only when the action is genuinely missing (queries real DB: children count, materials count, quiz attempts). If the user already completed the action, the hint never appears — even if they never saw it.
2. **Show Once, Remember Forever** — Each hint has a unique key. Once dismissed or completed, permanently suppressed. No "re-enable all hints."
3. **Frequency Cap** — Max 1 hint per page load. Max 1 per session. Max 1 per calendar day. Snooze = 7 days minimum.
4. **Progressive Disclosure** — First login: 2-3 next steps only. Days 2-7: max 1 nudge/day. After day 7: only undiscovered features. After day 30: stop all proactive hints entirely.
5. **Respect Behavior Signals** — Navigate away in <2s: auto-dismiss. Close 2 hints without engaging: 14-day cooldown. "Don't show tips": suppress ALL permanently. Visited Help/Tutorial in last 7 days: suppress nudges (self-directed user).
6. **Page Context Matching** — Hints only appear on the page where the action can be taken. Never on unrelated pages.

#### First-Login Welcome Modal

- Triggers on first authenticated session (no entries in `journey_hints` table)
- Role-tailored top 2-3 next steps with diagram thumbnails:
  - **Parent:** Add Child → Upload Material → Explore Dashboard
  - **Student:** Dashboard → Study Guide → Practice Quiz
  - **Teacher:** Create Class → Add Students → Upload Materials
  - **Admin:** Dashboard Overview → Managing Users
- Each card: diagram thumbnail + description + "Show me how" (→ Help journey) + "Ask the Bot" (→ chatbot)
- Footer: "Got it, let me explore" (dismiss) / "Don't show tips" (permanent suppress all)

#### Contextual Journey Nudges

| User State | Nudge | Page | Journey |
|------------|-------|------|---------|
| Parent, 0 children | "Add your first child to get started" | Dashboard, My Kids | P02 |
| Parent, children but 0 materials | "Upload course material for [child]" | Courses | P03 |
| Parent, not connected to Google | "Connect Google Classroom to auto-sync" | Courses, Settings | P10 |
| Student, 0 study guides | "Generate your first AI study guide" | Study Hub, Course Detail | S02 |
| Student, guides but 0 quizzes | "Test yourself with a practice quiz" | Study Guide Detail | S03 |
| Teacher, 0 courses | "Create your first class" | Dashboard, Courses | T02 |
| Teacher, course but 0 students | "Add students to your class" | Course Detail | T02 |

**Nudge UI:** Subtle, non-blocking banner below header. Muted color, small text, fade-in animation. Contains: hint text + "Learn more" + "Ask Bot" + dismiss ×. NOT a modal.

#### Backend

**New table:** `journey_hints` — `id, user_id, hint_key (varchar), status (shown|dismissed|completed|snoozed), shown_at, dismissed_at, snooze_until, created_at`

**Endpoints:**
- `GET /api/journey/hints?page={pageName}` — max 1 applicable hint after all filtering
- `POST /api/journey/hints/{hint_key}/dismiss` — permanent dismiss
- `POST /api/journey/hints/{hint_key}/snooze` — snooze 7 days
- `POST /api/journey/hints/suppress-all` — nuclear option

**Service:** `app/services/journey_hint_service.py` — queries real user state, caches per request

#### Frontend

**Hook:** `useJourneyHint(pageName)` — returns `{ hint, dismiss, snooze, suppressAll }` or null. Session-cached.

#### Requirements Checklist

- [x] §6.126.1 First-login welcome modal with role-tailored 2-3 next steps and diagram thumbnails (#2607)
- [x] §6.126.2 "Show me how" and "Ask the Bot" actions on each hint card (#2607)
- [x] §6.126.3 State-based hint detection — queries real user data, not timers (#2605)
- [x] §6.126.4 Auto-suppress hint when action is completed (even if hint was never shown) (#2605)
- [x] §6.126.5 Permanent dismiss persisted server-side in `journey_hints` table (#2604, #2606)
- [x] §6.126.6 Frequency caps: max 1/page, 1/session, 1/day (#2605, #2606)
- [x] §6.126.7 "Don't show tips" nuclear option suppresses all hints permanently (#2609)
- [x] §6.126.8 Behavior signal detection: 2 closes without engage → 14-day cooldown (#2609)
- [x] §6.126.9 Page context matching — hints only on relevant pages (#2608)
- [x] §6.126.10 Subtle non-blocking nudge banner (not modal) (#2608)
- [x] §6.126.11 30-day account age cutoff — stop all proactive hints (#2605)
- [x] §6.126.12 Mobile responsive (#2607, #2608)
- [x] §6.126.13 Optional "Getting Started" progress widget on dashboard (low priority) (#2610)

#### Key Files
- `frontend/src/components/JourneyWelcomeModal.tsx` — First-login popup
- `frontend/src/components/JourneyNudgeBanner.tsx` — Contextual nudge banner
- `frontend/src/hooks/useJourneyHint.ts` — Hint state management
- `app/services/journey_hint_service.py` — Detection logic
- `app/api/routes/journey.py` — Hint API endpoints
- `app/models/journey_hint.py` — `journey_hints` table model

### 6.127 Parent Email Digest Integration (CB-PEDI-001) - PLANNED

Parents connect their personal Gmail via OAuth (`gmail.readonly` scope). Their child's school email (e.g. YRDSB `@gapps.yrdsb.ca`) is forwarded to this personal Gmail. ClassBridge polls the parent's Gmail for emails from the child's school address, then uses Claude AI to summarize them into a configurable daily digest. Operates entirely within the parent's personal Gmail — no DTAP/MFIPPA approval required.

**PRD:** CB-PEDI-001-Parent-Email-Digest-PRD-v1.1
**M0 Feasibility:** CONFIRMED (March 29, 2026) — YRDSB forwarding enabled, dual-parent filter-based forwarding validated.

**Data Flow:**
```
YRDSB Student Gmail → [manual forwarding] → Parent Personal Gmail → [ClassBridge OAuth] → Gmail API poll → Claude AI summarization → Parent Dashboard / Email
```

**Database Tables:**
- `parent_gmail_integrations` — parent_id, gmail_address, access_token (encrypted), refresh_token (encrypted), child_school_email, child_first_name, is_active, paused_until, whatsapp_phone, whatsapp_verified, whatsapp_otp_code, whatsapp_otp_expires_at
- `parent_digest_settings` — integration_id, digest_enabled, delivery_time, timezone, digest_format, notify_on_empty
- `digest_delivery_log` — parent_id, integration_id, email_count, digest_content, status

**Architecture Decisions:**
- Token storage: Fernet-encrypted at rest (AES-128-CBC via `app/core/encryption.py`; future Secret Manager migration for all tokens)
- Separate OAuth flow via `ParentGmailIntegration` table (parent's personal Gmail may differ from Classroom account)
- Single cron job every 4 hours (matches `daily_digest_job.py` pattern)
- Delivery: **one ClassBridge notification per parent per day** containing all school emails summarized together (not one notification per email); uses `send_multi_channel_notification` — email sent if parent has email enabled for `school_emails` category
- Multi-child support in data model from Day 1; UI restricted in Phase 1

**Phase 1 Features (M1+M2, April-May 2026):**
- [x] M0: YRDSB forwarding feasibility confirmed
- [x] F-01: Gmail OAuth 2.0 connection flow for parent accounts (#2644) (IMPLEMENTED — PR #2780)
- [x] F-02: Child email address configuration (#2642, #2643) (IMPLEMENTED — PR #2780)
- [x] F-03: Guided setup wizard with forwarding instructions + OAuth callback page (#2647, #3017) (IMPLEMENTED — PR #2780, #3018)
- [x] F-04: Gmail API polling — filter by child school email (#2648) (IMPLEMENTED — PR #2985)
- [x] F-05: Claude AI summarization engine (#2650) (IMPLEMENTED — PR #2985)
- [x] F-06: Configurable digest delivery time (#2645) (IMPLEMENTED — PR #2780)
- [x] F-07: Digest delivery via in-app notification + email + WhatsApp (#2651, #2652, #2653, #2967) (IMPLEMENTED — PR #2985)
- [x] F-08: Digest toggle ON/OFF with pause duration (#2645) (IMPLEMENTED — PR #2780)
- [x] Backend CRUD routes (#2645) (IMPLEMENTED — PR #2780)
- [x] Notification type + preference category (#2646) (IMPLEMENTED — PR #2780)
- [x] Forwarding verification endpoint (#2649) (IMPLEMENTED — PR #2985)
- [x] Backend test suite — 83 tests (#2654) (IMPLEMENTED — PR #2985)

**Phase 2 Features (M4, July-August 2026):**
- [ ] F-09: Digest format selector — Brief bullets / Full summary / Action items only (#2655)
- [ ] F-10: Email categorization — Teacher / School admin / Board announcements (#2655)
- [ ] F-11: Action items extraction — deadlines, forms, RSVPs surfaced separately (#2655)
- [ ] F-12: Multi-child support UI (#2655)
- [ ] F-15: WhatsApp notification channel — Twilio WhatsApp Business API, phone OTP verification, "brief" format for 1600 char limit, fallback to email on failure (#2967)

**Phase 3 Features (M5, September 2026+):**
- [ ] F-13: Historical digest archive — searchable in Parent Dashboard (#2656)
- [ ] F-14: Weekly summary roll-up — weekend digest of full week (#2656)

**Key New Files (planned):**
- `app/models/parent_gmail_integration.py` — SQLAlchemy models (3 tables)
- `app/schemas/parent_email_digest.py` — Pydantic schemas
- `app/api/routes/parent_email_digest.py` — CRUD routes (prefix `/parent-digest`)
- `app/services/parent_gmail_service.py` — Gmail API polling
- `app/services/parent_digest_ai_service.py` — Claude Haiku summarization
- `app/jobs/parent_email_digest_job.py` — Scheduled digest job
- `app/templates/parent_email_digest.html` — Branded email template
- `frontend/src/pages/parent/EmailDigestSetupPage.tsx` — 5-step setup wizard
- `frontend/src/pages/parent/EmailDigestPage.tsx` — Digest view + delivery log
- `frontend/src/api/parentEmailDigest.ts` — Axios API client

**Files to Modify:**
- `app/api/routes/google_classroom.py` — Add `purpose="parent_gmail"` OAuth callback branch
- `app/models/notification.py` — Add `PARENT_EMAIL_DIGEST` to enum
- `main.py` — Mount router, register scheduler job
- `frontend/src/pages/AccountSettingsPage.tsx` — Add digest section for parents
- `frontend/src/pages/NotificationPreferencesPage.tsx` — Add "School Emails" category

**Cost Estimate:**
- Model: `claude-haiku-4-5` (~$0.001/digest)
- At 1,000 parents: ~$1/day, ~$30/month

**Compliance:**
- DTAP: NOT required — operates on parent's personal Gmail only
- MFIPPA risk: LOW — no direct access to board student accounts
- OAuth scope: `gmail.readonly` only (no modify/send)

**Milestones:**
| Milestone | Target | Deliverable |
|-----------|--------|-------------|
| M0 | March 2026 | COMPLETE — YRDSB forwarding confirmed |
| M1 | April 2026 | Gmail OAuth + settings UI + setup wizard |
| M2 | May 2026 | Digest engine + AI summarizer + scheduler |
| M3 | June 2026 | Pilot with 5-10 YRDSB families |
| M4 | July-Aug 2026 | Phase 2: format selector, categorization, multi-child |
| M5 | September 2026 | Public launch — feature GA |

### 6.128 Ask a Question — Parent Open-Ended Study Guide Generation (Phase 2) - IMPLEMENTED

Parents can type free-form education questions (e.g., "My son is doing OSSLT — how can I help him prep?") and get a structured, actionable study guide generated through the existing pipeline. No file upload or course content required.

**GitHub Epic:** #2861

**User Flow:**
1. Parent opens Upload Material wizard (from Dashboard or Study Guides page)
2. Clicks "Ask a Question" tab (new mode alongside "Upload Material")
3. Types open-ended question in textarea
4. Selects child + course on Step 2
5. Clicks "Generate Study Guide"
6. System **immediately starts streaming** a comprehensive, full study guide (4000 tokens) — no "Learn Your Way" picker, no extra clicks (#2880)
7. Parent sees the AI response streaming in real-time with suggestion chips for drill-down

**Backend:**
- New `document_type: "parent_question"` in strategy pattern (`study_guide_strategy.py`)
- Comprehensive AI prompt template with structured sections (Understanding, Step-by-Step Plan, Focus Areas, Resources, Test Day Tips, Accommodations)
- Ontario curriculum awareness (OSSLT, EQAO, grade-level expectations)
- `max_tokens: 4000` (full guide — no source material, AI generates all content) (#2880)
- Minimum content length relaxed from 50 to 10 characters for questions
- Question content prefixed with `"PARENT'S QUESTION:\n"` for clear AI context
- Safety guardrails: age-appropriate educational content only, redirects off-topic queries

**Frontend:**
- Mode toggle tabs in UploadWizardStep1: "Upload Material" | "Ask a Question"
- Question mode: hides file drop zone, shows focused textarea with example placeholder
- Auto-title from question text (first 50 chars)
- Submit button shows "Generate Study Guide" (vs "Upload")
- Creates CourseContent then navigates with `?autoGenerate=study_guide` — streaming starts immediately (#2880)
- CourseMaterialDetailPage auto-triggers `stream.startStream()` when `autoGenerate` param present

**Reuses existing infrastructure:**
- `POST /api/study/generate-stream` endpoint for SSE streaming (no new endpoints)
- StudyGuideCreate schema (no new fields)
- Suggestion chips + sub-guide generation pipeline
- AI usage limits (§6.54), content safety checks, streaming (§6.115)
- Deduplication, XP awards, audit logging

**Safety Guardrails:**
- `check_content_safe()` runs on all question text (existing)
- AI prompt includes safety instructions: age-appropriate content only
- System prompt forbids medical/legal/mental health advice — suggests professional consultation
- Off-topic questions politely redirected to educational guidance

**AI Cost:** ~$0.02-0.04/question (Claude Sonnet, 4000 max tokens)

**Sub-tasks:**
- [x] Backend: parent_question strategy pattern + AI prompt template (#2862)
- [x] Backend: max tokens, min-length gate, question prefix (#2862)
- [x] Frontend: wizard mode tabs + question textarea UI (#2863)
- [x] Frontend: wire question mode through parent hook (#2863)
- [x] CSS: mode tab styles with dark mode support (#2863)
- [x] Backend: full guide user prompt (not brief overview) in `_build_study_guide_prompt` (#2883, #2884)
- [x] Backend: CourseContent create stores document_type/study_goal — root cause fix (#2883, #2888)
- [x] Frontend: auto-stream via `?autoGenerate=study_guide` param (#2880, #2881)

**Key files:**
- `app/services/study_guide_strategy.py` — `parent_question` system prompt template
- `app/services/ai_service.py` — `parent_question: 4000` max tokens + full guide user prompt in `_build_study_guide_prompt()`
- `app/api/routes/study.py` — min-length gate bypass, question prefix, `_apply_parent_question_guards()` helper
- `app/api/routes/course_contents.py` — stores `document_type`/`study_goal` on CourseContent create
- `frontend/src/components/UploadWizardStep1.tsx` — mode tabs + question textarea
- `frontend/src/components/UploadMaterialWizard.tsx` — question mode wiring
- `frontend/src/components/parent/hooks/useParentStudyTools.ts` — question mode with `?autoGenerate=study_guide`
- `frontend/src/pages/CourseMaterialDetailPage.tsx` — auto-stream useEffect for `autoGenerate` param

**PRs:**
| PR | Title |
|----|-------|
| #2866 | feat: Ask a Question — core feature, wizard tabs, strategy pattern, safety guardrails |
| #2881 | fix: full guide + immediate streaming via `?autoGenerate` param |
| #2884 | fix: `_build_study_guide_prompt()` uses full guide user prompt for `parent_question` |
| #2888 | fix: CourseContent create endpoint stores `document_type`/`study_goal` (root cause fix) |

**Known future enhancements:**
- [ ] Document dual prompt locations — system in `study_guide_strategy.py`, user in `ai_service.py` (#2886)
- [ ] Add `CRITICAL_DATES` extraction to parent_question prompt for auto-task creation (#2887)
- [x] Convert continue endpoint to SSE streaming — spinner shows but no content streams (#2896) (FIXED — PR #2906)

### 6.129 Study Guide Section Navigation — Collapsible Sections & Table of Contents (#2894) - IMPLEMENTED

Long study guides render with section-based navigation for improved readability. Implemented in PR #2906 (commit bfc9965e), refined in PR #2915 (commit f482fdf4).

**Requirements:**
1. **Table of Contents (TOC)** — Auto-generated from H2/H3 markdown headings, rendered at top of study guide
2. **Collapsible sections** — Each H2 section can be collapsed/expanded (default: all expanded)
3. **Smooth scroll** — Clicking a TOC item smooth-scrolls to the corresponding section
4. **Section anchors** — Each heading gets an anchor ID for direct linking (e.g., `?tab=guide#trapezoids`)
5. **Streaming compatibility** — TOC updates as sections stream in during generation
6. **Mobile-friendly** — TOC adapts to mobile layout (floating menu or inline)
7. **Sub-guides only** — TOC and collapsible sections only render on sub-guide pages (with `parent_guide_id`), not on overview pages (#2923)

**Sub-tasks:**
- [x] Frontend: Parse markdown headings to generate TOC component
- [x] Frontend: Add collapse/expand toggle to each H2 section
- [x] Frontend: Smooth-scroll navigation from TOC to sections
- [x] Frontend: Persist collapse state in localStorage per guide
- [x] Frontend: Mobile-responsive TOC layout
- [x] Frontend: Only show TOC/collapsible on sub-guides, not overviews (PR #2915)
- [ ] Testing: Verify TOC works with streaming and sub-guides
- [ ] Accessibility: Keyboard navigation for TOC (#2900)
- [ ] Cleanup: localStorage cleanup for deleted guides (#2901)

**Key files:**
- `frontend/src/components/StudyGuideTOC.tsx` — TOC component
- `frontend/src/components/CollapsibleSection.tsx` — collapsible section wrapper
- `frontend/src/pages/StudyGuidePage.tsx` — study guide display with TOC integration

### 6.130 Inline Helpful Links for Major Topics in Study Guides (#2895) - IMPLEMENTED (Phase 1)

Study guides surface helpful external links (videos, interactive tools, articles) for major topics. Phase 1 implemented in PR #2906 (commit bfc9965e).

**Current state:** `ResourceSuggestionService` AI-generates and validates links against 30+ trusted educational domains (Khan Academy, Desmos, GeoGebra, PhET, etc.) and stores them as `ResourceLink` records. Phase 1 displays these within the study guide view via `ResourceLinksSection` component.

**Requirements:**

**Phase 1: Resource Links Section in Study Guide View — IMPLEMENTED**
1. [x] Query existing `ResourceLink` records for the guide's `course_content_id`
2. [x] Render a **"Helpful Resources"** section at the bottom of the study guide
3. [x] Group links by `topic_heading` with icons for YouTube vs external links
4. [x] Show thumbnail preview for YouTube videos
5. [x] Links open in new tab

**Phase 2: Inline Topic Links (AI-generated) — PLANNED**
6. Enhance study guide generation prompt to include `Learn more` callouts after major sections
7. AI selects from trusted domain whitelist
8. Post-process to validate URLs resolve (HEAD check)
9. Render as styled callout boxes in guide markdown

**Phase 3: Teacher-Curated Links — PLANNED**
10. Teachers can pin specific resources to course materials (`source: "teacher_shared"`)
11. Teacher-pinned links appear with "Teacher Recommended" badge
12. Prioritized above AI-suggested links

**Sub-tasks:**
- [x] Frontend: Add "Helpful Resources" section to StudyGuidePage when ResourceLinks exist (PR #2906)
- [x] Frontend: Resource link card component with icons, thumbnails, grouping (PR #2906)
- [x] Backend: ResourceLinks returned with study guide API response
- [ ] Refactor: ResourceLinksSection should use useQuery instead of raw useEffect (#2903)
- [ ] AI: Update study guide prompts to include inline resource callouts (Phase 2)
- [ ] Backend: URL validation for AI-embedded links (Phase 2)
- [ ] Frontend: Teacher resource pinning UI (Phase 3)
- [ ] Testing: Verify links display for all guide types and roles

**Key files:**
- `frontend/src/components/ResourceLinksSection.tsx` — resource links display component
- `app/services/resource_suggestion_service.py` — AI resource generation
- `app/models/resource_link.py` — ResourceLink model
- `frontend/src/pages/StudyGuidePage.tsx` — study guide display with resource links

---

### 6.131 Unified Template + Detection Framework (CB-UTDF-001, #2948) - DEPLOYED (2026-04-11)

Enhance the existing §3.9 Study Guide Strategy Pattern to auto-detect material type, subject, student, and teacher from uploaded documents, then show context-aware suggestion chips and route generation to the correct named template. Adds worksheet generation as a new first-class output type.

**PRD:** [docs/CB-UTDF-001-PRD-v1.md](../docs/CB-UTDF-001-PRD-v1.md)

**Deployed features:**
- Named template library (8 subject-specific templates)
- Subject/class auto-detection via extended Claude Haiku classification
- Multi-child disambiguation modal
- Teacher auto-assignment from course record
- Material-type-driven suggestion chip sets (replacing generic chips)
- Worksheet generation (`guide_type='worksheet'` on `study_guides` table)
- Answer key generation
- High-level summary chip
- Weak area analysis (Claude Sonnet)
- Manual detection override UI
- ClassificationBar, ClassificationOverridePanel, ChildDisambiguationModal (frontend)
- Worksheets tab on CourseDetailPage
- Mobile support via WebView approach
- Worksheet pagination and PDF export
- Gmail callback fix for email digest setup

**Data model:** Extends existing `study_guides` table with `guide_type='worksheet'` and `guide_type='weak_area_analysis'`. New columns: `template_key`, `num_questions`, `difficulty`, `answer_key_markdown`, `weak_topics`. New columns on `course_content`: `detected_subject`, `detection_confidence`, `classification_override`.

**Credit costs:**

| Output Type | Credits |
|-------------|---------|
| Worksheet | 1 credit |
| Answer Key | 0 (free) |
| High Level Summary | 0 (free) |
| Weak Area Analysis | 2 credits |

**Confidence UX model:** Child disambiguation is the ONLY blocking interaction (modal, chips disabled until resolved). Low-confidence material type, subject, and teacher are non-blocking visual indicators (dashed badges). Multiple low-confidence dimensions show simultaneously — no stacked modals.

**Existing upload backfill:** No batch backfill. Pre-UTDF materials show generic chips (current behavior) + "Detect subject" opt-in link for on-demand classification (free, no credits consumed).

**Stories (13) — all IMPLEMENTED:**
- [x] [CB-UTDF-S1] Extend document classification: add subject + confidence (#2949)
- [x] [CB-UTDF-S2] DB migration: new columns on course_content + study_guides (#2950)
- [x] [CB-UTDF-S3] Template key resolver + High Level Summary variant (#2951)
- [x] [CB-UTDF-S4] ClassificationBar component + teacher auto-assignment (#2952)
- [x] [CB-UTDF-S5] ChildDisambiguationModal — multi-child selector (#2953)
- [x] [CB-UTDF-S6] MaterialTypeSuggestionChips — type-driven chip sets (#2954)
- [x] [CB-UTDF-S7] ClassificationOverridePanel + PATCH endpoint (#2955)
- [x] [CB-UTDF-S8] Worksheet generation: POST endpoint + viewer (#2956)
- [x] [CB-UTDF-S9] Answer key generation endpoint (#2957)
- [x] [CB-UTDF-S10] Weak area analysis: Claude Sonnet endpoint + viewer (#2958)
- [x] [CB-UTDF-S13] CourseDetailPage: add Worksheets tab (#2959)
- [x] [CB-UTDF-S14] Mobile (Expo): ClassificationBar + chips (#2960)
- [x] [CB-UTDF-S15] Tests: classifier unit, integration, E2E (#2961)

**Architecture review fixes (G1–G12):** #3019–#3030

**PRs:**
- PR #3068 — Main UTDF implementation (17 parallel streams merged via integration branch)
- PR #3085 — Post-deployment fixes (Gmail callback, classifier prompt, pagination, PDF export, guide cleanup, digest format)

**Deployment Incident Summary (2026-04-10/11):**
- 2026-04-10 21:08 — PR #3068 merged to master
- 2026-04-10 21:18 — Production 500 errors: PostgreSQL ALTER TABLE migrations blocked by `pg_advisory_lock(1)` held by previous Cloud Run instance
- 2026-04-11 01:00–04:00 — Hotfix attempts: deferred columns, synchronous migrations, advisory lock fix
- 2026-04-11 ~17:30 — Final resolution: columns manually added via Cloud SQL Studio, code redeployed with columns enabled
- 2026-04-11 17:40 — PR #3085 merged with additional fixes
- 2026-04-11 18:36 — PR #3091 merged: PR review fixes (dead code, skip validation, cleanup dedup, frontend empty state, activity logging, Print/PDF gating)
- 2026-04-11 18:47 — Deployed revision `classbridge-01055-q96` (manual trigger — daily auto-deploy limit reached)
- **Key lesson:** replaced `pg_advisory_lock` with `pg_try_advisory_lock` (3 retries, 5s wait) to prevent future deadlocks
- **Deployment issues:** #3070–#3075 (PR review fixes), #3077–#3078 (pagination, PDF export), #3079 (advisory lock root cause), #3080 (re-enable columns), #3081–#3082 (documentation), #3083 (Gmail callback)
- **PR review issues (all closed):** #3086 (dead code), #3087 (skip validation), #3088 (cleanup dedup), #3092 (log_action consolidation), #3094 (Print/PDF gating), #3076 (frontend empty state + activity log)
- **Follow-up issues:** #3089 (health check schema verification), #3090 (migration-aware traffic routing)

**Study Guide Failure Handling (#3076) — DEPLOYED:**
- Backend: `_cleanup_empty_guide(guide_id, logger, *, user_id, error)` helper handles both record deletion and activity logging in one call
- Backend: Failed generations recorded in activity log (`action="error"`) for parent/admin visibility
- Frontend: `StudyGuideTab` shows "Generation failed" notice when `studyGuide` exists but `content` is empty
- Frontend: Print/PDF buttons hidden for empty guides; single Regenerate button in action bar
- Prevents blank study guides from appearing in the UI after API errors

**Remaining open architecture review items (future enhancements):**
- #3021 — Contradictory answer key storage design
- #3022 — Multi-subject document detection
- #3023 — Dual chip code paths for legacy materials
- #3024 — teacher_notes enum chip set ambiguity

---

### 6.132 Admin Customer Database — CRM, Branded Email & Messaging (CB-PCM-001, #2974) - PLANNED

Standalone **Customer Database** (CRM) within the Admin panel for managing parent/prospective customer contacts, sending branded ClassBridge emails from templates, and WhatsApp/SMS messaging via Twilio. Independent of the existing `users` table — this is an outreach system for pre-registration relationship management.

**Epic:** #2974

#### Motivation

Admins need to manage parent relationships outside the platform's registered user base — for outreach, onboarding campaigns, school board demos, and pilot communication. The existing broadcast system only reaches registered users. This fills the gap between "interested parent" and "registered user."

#### Key Capabilities

1. **Customer Database** — Add/edit/delete contacts with name, email, phone, school, child info, notes. CRM pipeline statuses (lead → contacted → interested → converted). Independent of `users` table with optional linking when contact converts.
2. **Contact Notes** — Timestamped notes per contact for tracking interactions.
3. **PIPEDA Compliance** — Consent tracking (consent_given boolean + date) for Canadian privacy law.
4. **Email Templates** — 5 branded ClassBridge email templates with variable substitution. Admin CRUD for custom templates.
5. **On-Demand Email** — Select contacts (single or bulk), pick a template, preview branded HTML, send via SendGrid.
6. **WhatsApp / SMS** — Send messages via Twilio (WhatsApp Business API or SMS). Graceful degradation when Twilio not configured.
7. **Outreach Log** — Every send attempt logged with rendered body snapshot for audit trail.

#### Data Model (4 New Tables)

- `parent_contacts` — full_name, email, phone (E.164), school_name, child_name, child_grade, status (lead/contacted/interested/converted/archived/unresponsive), source, tags (JSON), linked_user_id (FK), consent_given, consent_date, timestamps
- `parent_contact_notes` — parent_contact_id (FK CASCADE), note_text, created_by_user_id, created_at
- `outreach_templates` — name, subject, body_html, body_text, template_type (email/whatsapp/sms), variables (JSON), is_active, timestamps
- `outreach_log` — parent_contact_id (FK), template_id (FK), channel, status, recipient_detail, body_snapshot, sent_by_user_id, error_message, created_at

#### API Endpoints

**Customer Contacts (`/api/admin/contacts`):**
- GET list (search, filter, paginate), GET stats, GET duplicates, POST create, GET/:id detail, PATCH/:id update, DELETE/:id, GET export/csv
- Notes: GET/:id/notes, POST/:id/notes, DELETE/:id/notes/:noteId
- Outreach history: GET/:id/outreach-history
- Bulk: POST bulk-delete, bulk-status, bulk-tag

**Outreach Templates (`/api/admin/outreach-templates`):**
- GET list, POST create, GET/:id, PATCH/:id, DELETE/:id (soft), POST/:id/preview

**Outreach Send (`/api/admin/outreach`):**
- POST /send (email, WhatsApp, SMS), GET /log, GET /log/:id, GET /stats

#### Seed Templates (5 Branded ClassBridge Emails)

1. Initial Outreach — first contact introducing ClassBridge
2. Follow-Up #1 (3 days) — gentle nudge
3. Follow-Up #2 (7 days) — social proof, feature deep-dive
4. Follow-Up #3 (14 days) — urgency, last chance
5. Pilot Invite — direct invitation with registration token

#### Frontend

- `/admin/contacts` — Customer Database page (table, search, filters, stats, detail drawer, notes, outreach history)
- `/admin/contacts/compose` — Unified Outreach Composer (Email/WhatsApp/SMS tabs, template selection, variable substitution, preview, bulk send)
- Admin nav: "Customer DB" item in sidebar

#### Security & Compliance

- PIPEDA: consent_given + consent_date on contacts; UI warning when consent not recorded
- XSS: HTML-escape all variable values before template substitution
- Audit trail: body_snapshot captures rendered content at send time
- Phone masking in application logs

#### Tech

- Email: SendGrid (existing)
- WhatsApp/SMS: Twilio (new dependency: `twilio>=9.0.0`)
- New env vars: `TWILIO_SMS_FROM`
- Existing env vars used: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`

#### Stories

- [ ] [CB-PCM-S1] DB models + migrations (#2975)
- [ ] [CB-PCM-S2] Pydantic schemas (#2976)
- [ ] [CB-PCM-S3] Customer contacts CRUD API (#2977)
- [ ] [CB-PCM-S4] Outreach templates CRUD API + seed (#2978)
- [ ] [CB-PCM-S5] Outreach send API — email, WhatsApp, SMS (#2979)
- [ ] [CB-PCM-S6] Frontend — Customer Database page (#2980)
- [ ] [CB-PCM-S7] Frontend ��� Unified Outreach Composer (#2981)
- [ ] [CB-PCM-S9] Tests — backend + frontend (#2983)
