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

### 6.127 Parent Email Digest Integration (CB-PEDI-001) - M1+M2 DEPLOYED (2026-04-10)

Parents connect their personal Gmail via OAuth (`gmail.readonly`, `userinfo.email`, `userinfo.profile` scopes). Their child's school email (e.g. YRDSB `@gapps.yrdsb.ca`) is forwarded to this personal Gmail. ClassBridge polls the parent's Gmail for emails from the child's school address, then uses Claude AI to summarize them into a configurable daily digest. Operates entirely within the parent's personal Gmail — no DTAP/MFIPPA approval required. Parents can configure a whitelist of sender email addresses to monitor — only emails from these addresses are read.

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

**Defect Fixes (2026-04-12/13):**
- [x] Gmail callback 500: null guard for gmail_address (#3031) — PR #3169
- [x] Non-200 userinfo logging (#3159) + specific exception types (#3160) — PR #3169
- [x] Root cause: missing userinfo.email + userinfo.profile OAuth scopes (#3176) — PR #3177

**On-Demand Digest (M3, #3307):**
- [ ] F-17: On-demand digest — parents can trigger immediate digest delivery from the Email Digest page via a "Send Digest Now" button (#3307)
  - Uses the same pipeline as scheduled digest: fetch emails → AI summarize → render template → deliver via configured channels
  - Bypasses the "already delivered today" deduplication check (parent may want a fresh digest after new emails arrive)
  - Rate-limited to 10 requests per minute per parent to prevent abuse

**Phase 2 Features (M4, July-August 2026):**
- [ ] F-09: Digest format selector — Brief bullets / Full summary / Action items only (#2655)
- [ ] F-10: Email categorization — Teacher / School admin / Board announcements (#2655)
- [ ] F-11: Action items extraction — deadlines, forms, RSVPs surfaced separately (#2655)
- [ ] F-12: Multi-child support UI (#2655)
- [ ] F-15: WhatsApp notification channel — Twilio WhatsApp Business API, phone OTP verification, "brief" format for 1600 char limit, fallback to email on failure (#2967)
- [ ] F-16: Multi-sender email whitelist — parents can add/remove/label multiple sender email addresses to monitor (e.g. teacher, school office, board); Gmail query uses `from:({email1} OR {email2})` pattern; migrates existing `child_school_email` to new `parent_digest_monitored_emails` table (#3178)

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
- OAuth scope: `gmail.readonly` (no modify/send), `userinfo.email` + `userinfo.profile` (to identify connected Gmail address)

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

### 6.132 Admin Customer Database — CRM, Branded Email & Messaging (CB-PCM-001, #2974) - DEPLOYED (2026-04-12)

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

- [x] [CB-PCM-S1] DB models + migrations (#2975) — PR #3106
- [x] [CB-PCM-S2] Pydantic schemas (#2976) — PR #3106
- [x] [CB-PCM-S3] Customer contacts CRUD API (#2977) — PR #3107
- [x] [CB-PCM-S4] Outreach templates CRUD API + seed (#2978) — PR #3108
- [x] [CB-PCM-S5] Outreach send API — email, WhatsApp, SMS (#2979) — PR #3109
- [x] [CB-PCM-S6] Frontend — Customer Database page (#2980) — PR #3110
- [x] [CB-PCM-S7] Frontend ��� Unified Outreach Composer (#2981) — PR #3111
- [x] [CB-PCM-S9] Tests — backend + frontend (#2983)

**Integration PR:** #3113 (merged all 8 stories via integration branch)
**Deployed:** April 12, 2026

**UX improvements:**
- Progressive 3-step add/edit contact modal (basic info — child details — tags/notes)
- Checkbox appearance fix for consistent cross-browser rendering

**Post-deployment fixes:**
- #3126/#3135 — Trailing slash 404 on /admin/contacts/
- #3136/#3137 — Transparent modal background fix
- Surrogate emoji rendering fix

---

### 6.133 Admin Feature Management — Toggle Features On/Off (#3145, #3146, #3147) - DEPLOYED (2026-04-12)

Database-backed feature management system allowing admins to enable/disable platform features on demand via a dedicated admin page. Features are OFF by default and persist across server restarts.

**Epic Issues:** #3145 (backend), #3146 (admin page), #3147 (nav/route gating)

#### Motivation

Report Cards, Analytics, and School Board Connectivity are not ready for all users yet. Admins need a way to toggle these features on/off without code deploys — enabling staged rollouts and quick kill-switches.

#### Managed Features (Phase 1)

| Key | Name | Default | Gates |
|-----|------|---------|-------|
| `report_cards` | Report Cards | OFF | `/school-report-cards` route + sidebar nav (parent, student) |
| `analytics` | Analytics | OFF | `/analytics` route + sidebar nav (parent, student, admin) |
| `school_board_connectivity` | School Board Connectivity | OFF | Future feature — no route yet |

#### Implementation

1. **Database model** — `feature_flags` table: `id`, `key` (unique), `name`, `description`, `enabled` (default false), `created_at`, `updated_at`
2. **Seed service** — Seeds 3 features on startup if table empty
3. **Admin API** — `GET /api/admin/features` (list), `PATCH /api/admin/features/{key}` (toggle)
4. **Public API** — `GET /api/features` (no auth required; returns config-based flags for all callers, plus DB-backed flags for authenticated users, as `{key: bool}`)
5. **Admin page** — `/admin/features` with toggle switches, descriptions, last-updated timestamps
6. **FeatureGate component** — Wraps routes; redirects to `/dashboard` if feature disabled
7. **Sidebar gating** — `DashboardLayout.tsx` conditionally shows nav items based on `useFeatureToggles()` hook
8. **Existing flags** (`google_classroom`, `waitlist_enabled`) remain in `config.py` — not migrated

---

### 6.134 Interactive Learning Engine — Flash Tutor (CB-ILE-001) - ALL MILESTONES IMPLEMENTED (2026-04-14)

AI-powered micro-learning engine replacing and extending the current quiz module. Features three quiz modes (Learning + Testing + Parent Teaching), adaptive difficulty, fill-in-the-blank format escalation, SM-2 spaced repetition, parent co-learning with personal hints, career connections, and deep gamification integration. Sessions are 3-7 questions targeting 5-8 minutes.

**PRD:** CB-ILE-001 v1.3
**Epic:** #3196
**Status:** All 5 milestones (M0-M4) implemented and deployed to production
**Deployed:** April 14, 2026

#### Design Pillars (priority order)
1. **Microlearning Structure** — 3-7 questions, 5-8 minutes, one topic per session
2. **Interactivity** — Format selection based on history (MCQ → Fill-in-the-Blank)
3. **Instant Feedback** — Never just a correctness label; minimum one sentence explanation
4. **Adaptive Learning** — Per-question, per-topic, per-student difficulty adjustment (SM-2)
5. **Progress Tracking** — Mastery map, streak integration, parent visibility

#### Quiz Modes

**Learning Mode:**
- Wrong answer → AI hint (escalating specificity) → retry unlimited
- Correct answer → "Why Correct" explanation (2-3 sentences, grade level)
- Auto-reveal after 5 attempts: "Let's look at this together"
- XP tiered by attempt: 1st=30, 2nd=20, 3rd=10, 4+=0
- Streak increments on first-attempt correct only

**Testing Mode:**
- Standard assessment — no hints, no explanations, no retries
- Flat 10 XP per correct answer
- Results screen at end with score percentage

#### M0 Implementation (COMPLETED)

**Database (5 new tables):**
- [x] `ile_sessions` — Session tracking (mode, subject, topic, difficulty, status, questions_json)
- [x] `ile_question_attempts` — Per-question attempt tracking (answer, correctness, hints, XP)
- [x] `ile_topic_mastery` — SM-2 spaced repetition + weak area detection
- [x] `ile_question_bank` — Pre-generated question cache for cost optimization
- [x] `ile_student_calibration` — Per-student difficulty calibration

**Backend (4 new files):**
- [x] `app/services/ile_service.py` — Session orchestrator (create, answer, complete, abandon, resume)
- [x] `app/services/ile_question_service.py` — AI question generation with content safety check
- [x] `app/api/routes/ile.py` — 10 API endpoints under `/api/ile/`
- [x] `app/schemas/ile.py` — Pydantic schemas for all ILE types

**Frontend (6 new files):**
- [x] `frontend/src/api/ile.ts` — TypeScript API client
- [x] `frontend/src/pages/FlashTutorPage.tsx` — Session launcher (topic/mode/config selection)
- [x] `frontend/src/pages/FlashTutorSessionPage.tsx` — Active session UI with hint/explanation bubbles
- [x] CSS with responsive design, theme variables, animations (slide-in, XP pop)
- [x] Routes: `/flash-tutor`, `/flash-tutor/session/:id`
- [x] Nav entry in DashboardLayout sidebar

**XP/Gamification Integration:**
- [x] 4 new XP action types: `ile_session_complete`, `ile_first_attempt_correct`, `ile_testing_correct`, `ile_parent_teaching`
- [x] 1 new badge: `ile_first_session` (Flash Learner)
- [x] Streak integration via existing `streak_service`

#### M1 Implementation (COMPLETED — April 14, 2026)

- [x] Learning Mode component extraction — HintBubble, ExplanationBubble, XpPopBadge, StreakCounter (#3203, PR #3248)
- [x] Within-session adaptive difficulty engine — 2 consecutive first-attempt correct → increase, 2 multi-attempt → decrease (#3204, PR #3243)
- [x] Session persistence + resume within 24h — startup expiry cleanup, resume banner with time remaining, Start Fresh option (#3205, PR #3246)

#### M2 Implementation (COMPLETED — April 14, 2026)

- [x] Topic mastery tracking + weak area detection — rolling avg attempts, auto-flag weak areas (#3206, PR #3245)
- [x] Surprise Me — weighted topic selection (3x weak, 2x overdue, 1x normal) (#3207, PR #3254)
- [x] Fill-in-the-Blank format + escalation — MCQ → fill_blank after 2 correct sessions, with de-escalation (#3208, PR #3253)
- [x] Question bank pre-generation + hint caching — batch prefill, auto-save on-demand, admin endpoints (#3209, PR #3250)
- [x] SM-2 spaced repetition + Memory Glow UI — easiness factor, review intervals, glow visualization (#3210, PR #3255)
- [x] 4 new ILE badges + student calibration — On Fire, Topic Master, Team Player + auto-difficulty after 3 sessions (#3211, PR #3252)

#### M3 Implementation (COMPLETED — April 14, 2026)

- [x] Parent Teaching Mode full flow — personal hints, areas to revisit, dashboard entry point (#3212, PR #3276)
- [x] Private Practice + Career Connect — hidden scores toggle, AI career connections post-session (#3213, PR #3277)
- [x] ILE data in Parent Email Digest — daily + weekly digest sections with ILE activity (#3214, PR #3273)
- [x] Aha Moment detection + Knowledge Decay — breakthrough celebration (CSS confetti), decay notifications (#3215, PR #3279)

#### M4 Implementation (COMPLETED — April 14, 2026)

- [x] Cost logging, anti-gaming, admin analytics — per-session cost, 10/day limit, rapid completion flagging, admin analytics endpoint (#3216, PR #3278)
- [x] Performance optimization + quiz migration — response caching (60s TTL), bank format filter, Flash Tutor banner on quiz page, 12 ILE tests (#3217, PR #3274)
- [x] Flash Tutor from study guides — context-grounded question generation, "Practice" button on study guide page (#3272, PR #3275)

#### Post-Implementation Fixes (April 14, 2026)

- [x] Sidebar navigation — added Flash Tutor to student + parent nav sections (#3286, PR #3288)
- [x] API prefix — added missing `/api` prefix to all 15 ILE frontend endpoints (#3286, PR #3288)
- [x] Parent hint storage — hints no longer dropped before first attempt (#3280)
- [x] Mastery rollback — aha detection no longer rolls back committed mastery data (#3281)
- [x] Cost estimation — handles Decimal return from `_calc_cost` (#3282)
- [x] Fill-blank de-escalation — reverts to MCQ after 2 poor fill-blank sessions (#3284)
- [x] CareerConnectCard error boundary — API failure no longer crashes results page (#3285)

#### Architecture Summary

**Backend (7 services, 16 API endpoints):**
- `ile_service.py` (960+ lines) — session orchestrator with calibration, format escalation, rate limiting
- `ile_question_service.py` — AI MCQ + fill-blank generation, bank lookup, format escalation
- `ile_mastery_service.py` — mastery tracking, SM-2, glow intensity, aha detection
- `ile_adaptive_service.py` — within-session difficulty adjustment
- `ile_cost_optimizer.py` — bank pre-generation, hint caching, cleanup, stats
- `ile_surprise_service.py` — weighted topic selection
- `ile_digest_helper.py` — daily + weekly digest data helpers

**Frontend (10 components):**
- FlashTutorPage.tsx — launcher with resume, Surprise Me, mastery nodes, private practice
- FlashTutorSessionPage.tsx — active session with MCQ, fill-blank, parent controls, career connect, aha celebration
- HintBubble, ExplanationBubble, XpPopBadge, StreakCounter, FillBlankCard, MasteryNode, ParentTeachingControls, CareerConnectCard, AhaMomentCelebration

**Database (5 tables):** ile_sessions, ile_question_attempts, ile_topic_mastery, ile_question_bank, ile_student_calibration

#### Cost Model
- Baseline per-session: ~$0.013 USD
- With question bank + hint caching (M2): ~$0.004-0.006 USD (50-65% reduction)
- At 1,000 DAU: ~$200-300/month (optimized)

#### UX Enhancements (April 14, 2026)

- [x] Custom topic button with avatar — styled dashed-border card with TutorAvatar thinking mood (#3303, PR #3315)
- [x] Show 5 recent topics with search — limit to 5 (weak areas first), search input, "Show all/less" toggle (#3304, PR #3315)
- [x] Parent child filter — ChildSelectorTabs for parents with 2+ children, backend `student_id` param on GET /topics (#3305, PR #3317)
- [x] Streaming question generation — SSE endpoint POST /sessions?stream=true, useFlashTutorStream hook, TutorAvatar progress UI (#3306, PR #3321) — SSE endpoint for progressive question delivery with TutorAvatar thinking animation (#3306)

#### UI Redesign (April 14, 2026)

- [x] Theme alignment — replaced all non-existent CSS variables with ClassBridge design system (#3289, PR #3291)
- [x] Visual enhancements — hero card with gradient border, TutorAvatar owl mascot, elevated cards with hover lift, gradient buttons, animated score circle, streak tiers (#3289, PR #3291)
- [x] Shared keyframe extraction — ile-animations.css as single source of truth (#3299)
- [x] Accessibility — reactive prefers-reduced-motion for SVG animations (#3298)

#### Open Enhancement Issues
- #3262-#3271: 10 code quality suggestions (LRU cache, dead code, edge cases)
- #3272: Study guide integration (IMPLEMENTED)

### 6.135 My Kids Page — Panel UX Improvements (#3360, #3361) - IMPLEMENTED

**Purpose:** Improve the My Kids page panel layout, collapsibility, and data display for better parent usability.

**Requirements:**
1. **Class Materials before Best Study Times** — swap panel order so Class Materials appears first in the dashboard grid
2. **Limit Class Materials to 5 most recent** — show only the 5 most recently created materials (sorted by `created_at` descending), with a "View All" button navigating to `/course-materials`
3. **Both panels collapsed by default** — Class Materials and Best Study Times panels start collapsed on first visit (no localStorage state)
4. **No-child view: aggregated Class Materials** — when no child filter is selected ("All"), show the 5 most recent class materials across ALL children (not just unassigned ones)
5. **No-child view: per-child Study Times** — render a StudyTimeSuggestions component for each child when no child filter is selected
6. **No-child view: two-column layout** — use the `dashboard-redesign` grid (matching the child-selected view) instead of single-column layout
7. **Consistent panel component** — Unassigned Classes and Unassigned Materials sections converted from raw `dash-section` divs to `SectionPanel` components for UI consistency

**Key PRs:** #3362

**Sub-tasks:**
- [x] Swap Class Materials above Best Study Times in child-selected view (#3360)
- [x] Add `useMemo` recency sort + slice(0, 5) for materials (#3364)
- [x] Add "View All" button via `headerRight` prop on SectionPanel (#3360)
- [x] Add `.section-panel__view-all` CSS styles (#3360)
- [x] Default StudyTimeSuggestions collapsed state to `true` including catch fallback (#3360, #3363)
- [x] Load all non-archived materials when no child selected (#3361)
- [x] Rewrite no-child view with `dashboard-redesign` grid layout (#3361)
- [x] Render per-child StudyTimeSuggestions in no-child view (#3361)
- [x] Convert Unassigned sections to SectionPanel components (#3361)

---

### 6.136 Problem Solver / Solve with Explanations (#2697)

**Purpose:** Provide step-by-step worked solutions for uploaded exam and test documents, helping students understand how to solve each problem rather than just seeing the answer.

**Trigger:** For documents classified as `past_exam`, `mock_exam`, `student_test`, `quiz_paper`, `worksheet`, or `custom`, show a **"Solve with Explanations"** AI chip on the course material detail page.

**Behavior:**
- [x] Clicking the chip generates a study guide variant with `guide_type: problem_solver`
- [x] Generated content renders in the existing Study Guide tab (no new tab required)
- [x] Credit cost: 1 AI credit (same as a standard study guide)
- [x] Available to all roles: parent, student, teacher

**Generated Content Requirements:**
- [x] Step-by-step worked solutions for each problem in the document
- [x] Clear explanation of **why** each step is taken (not just how)
- [x] Common mistakes to avoid for each problem
- [x] Key formula and concept references
- [x] LaTeX math notation (`$...$`) for mathematical expressions

**AI Chip Visibility Rules:**
- [x] Show "Solve with Explanations" chip for document types: `past_exam`, `mock_exam`, `student_test`, `quiz_paper`, `worksheet`, `custom`
- [x] Hide the chip for other document types (e.g., `lecture_notes`, `textbook_chapter`, `syllabus`)

---

### 6.137 AI Study Guide Generator — Ask-a-Question to Flash Study (CB-ASGF-001) - DEPLOYED

**Status:** DEPLOYED | **Epic:** #3390 | **PRD:** CB-ILE-001 v2.0 §18

**Purpose:** Transform the study guide generation experience from a static document-upload-and-wait workflow into an interactive, question-driven learning cycle. Students (or parents on their behalf) ask a question, optionally attach documents for context, and receive a short slide-based learning plan with an integrated Flash Tutor quiz — all in a single flow. This bridges the gap between "I have a question" and "I understand the answer" by combining AI-generated micro-lessons with immediate comprehension checks.

#### §6.137.1 Enhanced Question Input + Intent Detection — DEPLOYED

- [x] Free-text question input with 500-character limit and real-time character counter
- [x] Intent classifier detects question type (conceptual, procedural, factual, comparison) using keyword heuristics
- [x] Intent badge displayed next to question for transparency
- [x] Placeholder suggestions rotate to guide students toward effective questions
- [x] Input validation prevents empty or too-short questions (minimum 10 characters)

**Issues:** #3391, #3392 | **PR:** #3421 (M5a)

#### §6.137.2 Multi-Document Upload + Ingestion Pipeline — DEPLOYED

- [x] Drag-and-drop + click-to-browse file upload supporting PDF, DOCX, images (PNG/JPG)
- [x] Up to 3 documents per session (configurable limit)
- [x] Server-side ingestion: PDF text extraction (PyPDF2), DOCX parsing (python-docx), image OCR (Tesseract fallback to Cloud Vision)
- [x] Chunking pipeline splits extracted text into 1,500-token chunks with 200-token overlap
- [x] Upload progress indicators with per-file status (uploading → processing → ready)
- [x] File type validation and size limit (10 MB per file)

**Issues:** #3393, #3394 | **PR:** #3421 (M5a)

#### §6.137.3 Context Selection + AI Context Assembly — DEPLOYED

- [x] Context panel shows uploaded documents and existing course materials side-by-side
- [x] Checkbox selection allows combining multiple context sources
- [x] AI context assembly concatenates selected chunks with source attribution headers
- [x] Token budget management — truncates context to fit within model context window (8K reserved for generation)
- [x] "No context" mode supported — AI answers from general knowledge when no documents selected

**Issues:** #3395, #3396 | **PR:** #3434 (M5b)

#### §6.137.4 Short Learning Cycle Plan + Slide Generation — DEPLOYED

- [x] AI generates 3-5 slide learning plan based on question + context
- [x] Each slide contains: title, key concept, explanation (300-500 words), and optional diagram description
- [x] Slide renderer with navigation (prev/next), progress bar, and keyboard shortcuts (arrow keys)
- [x] Markdown rendering within slides (headers, bold, lists, code blocks, LaTeX math)
- [x] Comprehension signal — "Got it" / "Need more detail" buttons on each slide to adjust depth
- [x] Responsive slide layout for mobile and desktop

**Issues:** #3397, #3398 | **PR:** #3434 (M5b)

#### §6.137.5 Integrated Flash Tutor Quiz (Slide-Anchored) — DEPLOYED

- [x] After completing slides, auto-launches a 5-question Flash Tutor quiz on the slide content
- [x] Questions anchored to specific slides — incorrect answers link back to the relevant slide
- [x] Quiz uses existing ILE question generation with slide content as context
- [x] Score summary with per-question slide references for review
- [x] Option to retry quiz or return to slides for review before retrying

**Issues:** #3399, #3400 | **PR:** #3447 (M5c)

#### §6.137.6 Auto-Save + Role-Aware Assignment — DEPLOYED

- [x] Generated study guide auto-saved to student's study guide library
- [x] Parent-initiated sessions assigned to the selected child's account
- [x] Teacher-initiated sessions saved as class materials with course assignment
- [x] Guide metadata includes: source question, intent type, context document IDs, slide count, quiz score
- [x] Duplicate detection — warns if a similar question was asked in the last 7 days

**Issues:** #3401, #3402 | **PR:** #3447 (M5c)

#### §6.137.7 Learning History + Spaced Repetition — DEPLOYED

- [x] Session history page shows past ASGF sessions with question, date, quiz score
- [x] Spaced repetition scheduling — resurfaces low-scoring sessions after 1, 3, 7, 14 days
- [x] "Review again" button re-opens slides + quiz for a previous session
- [x] Progress tracking — shows improvement trend across repeated sessions on the same topic

**Issues:** #3403, #3404 | **PR:** #3477 (M5d)

#### §6.137.8 Cost Model + Session Caps — DEPLOYED

- [x] Per-session cost: ~$0.02 USD (slide generation + quiz generation)
- [x] Daily cap: 10 ASGF sessions per student (configurable via admin)
- [x] Credit deduction: 2 AI credits per ASGF session (slides + quiz)
- [x] Cost logging integrated with existing `ai_usage_logs` table
- [x] Admin analytics dashboard shows ASGF usage and cost breakdown

**Issues:** #3405, #3406 | **PR:** #3477 (M5d)

#### §6.137.9 Error Recovery + Session Resume — DEPLOYED

- [x] Session state persisted to database at each step (question → upload → slides → quiz)
- [x] Browser refresh or disconnect resumes from last completed step
- [x] Partial slide generation saved — if generation fails mid-stream, completed slides are preserved
- [x] Retry button on generation failure with exponential backoff
- [x] Graceful degradation — if quiz generation fails, slides are still accessible

**Issues:** #3407, #3408 | **PR:** #3477 (M5d)

#### §6.137.10 ASGF Integration Bridges — DEPLOYED

Ten entry points connecting ASGF with existing ClassBridge UX surfaces:

- [x] **Sidebar navigation:** "Ask a Question" nav item launches ASGF (#3537, PR #3555)
- [x] **Dashboard quick action cards:** Parent + student dashboard cards link to ASGF (#3539, PR #3555)
- [x] **GenerateSubGuideModal:** "Learning Session" added as 4th generation option (#3534, PR #3555)
- [x] **Upload wizard:** "Start Learning Session" CTA after document upload (#3532, PR #3555)
- [x] **FAB chatbot:** "Start Learning Session" button on study Q&A responses (#3531, PR #3555)
- [x] **SelectionTooltip:** "Start Session" button on text selection (#3538, PR #3555)
- [x] **ASGF page escape hatch:** "Generate study guide instead" link on ASGFPage (#3535, PR #3555)
- [x] **ASGFPage at /ask route:** Full 5-stage wizard (question → upload → context → slides → quiz) (#3518, PR #3518)

**Issues:** #3531-#3539 | **Key PR:** #3555

#### §6.137.11 Incremental Slide Streaming (NFR) — DEPLOYED (#3735)

Non-functional requirement — slide generation must be **progressive and non-blocking**:

- [x] **Eager streaming** — the slide SSE stream begins immediately after the session is created. The frontend must not gate SSE opening behind a progress-animation stage transition.
- [x] **Time-to-first-slide** — the user transitions from the progress interstitial to the slides view as soon as the first slide event arrives, not after a pre-determined animation completes.
- [x] **Background streaming** — slides 2-N continue streaming in the background while the user reads slide 1; subsequent slides append to the renderer as they arrive.
- [x] **Bounded parallel generation (backend)** — slide #1 is generated synchronously for fastest first paint; slides #2-7 are generated with bounded concurrency (`asyncio.Semaphore`, max 3 in flight) and emitted to the SSE stream in slide-number order.
- [x] **Per-slide error isolation** — a single slide's generation failure yields an error placeholder in its slot and does not abort the stream.

**Why:** the previous implementation stalled the "Generating your lesson…" interstitial forever because `processingStage` never advanced to `4`, so `onComplete` never fired and the SSE was never opened. Even after the state-machine fix, sequential generation made the user wait for 7 × per-slide latency before seeing a complete lesson. Incremental streaming gives the user content to consume within ~1 slide-latency of starting.

**Issues:** #3735 | **PR:** (integrate/3735-asgf-streaming)

#### Key PRs

| PR | Milestone | Description |
|----|-----------|-------------|
| #3421 | M5a Foundation | Schema, intent classifier, upload, ingestion, context panel |
| #3434 | M5b Generation | Context assembly, slide renderer, slide generation, comprehension signal |
| #3447 | M5c Integration | Quiz bridge, auto-save, role-aware assignment |
| #3477 | M5d Polish | Spaced repetition, cost model, error recovery, session resume |
| #3518 | Page | Complete Ask-a-Question to Flash Study page |
| #3555 | Integration Bridges | 7 entry points connecting ASGF to existing UX |

#### Sub-Milestones

- **M5a Foundation** (#3390): Schema + intent classifier + upload pipeline — PR #3421
- **M5b Generation** (#3390): Context assembly + slide generation + renderer — PR #3434
- **M5c Integration** (#3390): Quiz bridge + auto-save + role-aware assignment — PR #3447
- **M5d Polish** (#3390): Spaced repetition + cost model + error recovery — PR #3477
- **Page** (#3390): Complete ASGF page wiring all milestones together — PR #3518
- **Integration Bridges** (#3390): 10 entry points across sidebar, dashboard, chatbot, upload wizard — PR #3555

---

### 6.138 Notes Enhancement — Rich Text, Images, Export (CB-NOTES-001) - DEPLOYED (2026-04-17)

**Status:** DEPLOYED | **Epic:** #3526

**Purpose:** Upgrade the Notes panel from a plain textarea into a full-featured rich text editor with image support, maximize/restore, save-as-material, and export capabilities — making notes a first-class content creation tool within ClassBridge.

#### Features

- [x] **TipTap rich text editor** — replace textarea with TipTap (bold, italic, underline, strikethrough, headings, bullet/ordered lists, code blocks, blockquotes, horizontal rules) (#3527, PR #3559)
- [x] **Image paste & upload** — paste images from clipboard or upload from file picker; images stored via NoteImage model with backend API endpoints (#3528, PR #3556)
- [x] **Maximize/restore toggle** — expand Notes panel to full viewport height; toggle button in panel header (#3529, PR #3557)
- [x] **Save note as class material** — one-click save of note content as a class material attached to the current course (#3530, PR #3558)
- [x] **Download/export notes** — export notes as PDF or Markdown files (#3540, PR #3560)

**Key PR:** #3577 (integration branch merging all Notes Enhancement work)

**Sub-tasks:**
- [x] Add TipTap editor with toolbar (bold, italic, headings, lists, code, blockquote) (#3527)
- [x] Add NoteImage SQLAlchemy model and upload/list/delete API endpoints (#3528)
- [x] Image paste handler and file upload button in editor toolbar (#3528)
- [x] Maximize/restore toggle with CSS transition (#3529)
- [x] Save-as-material endpoint with course assignment (#3530)
- [x] PDF export via html-to-pdf conversion (#3540)
- [x] Markdown export via HTML-to-Markdown converter (#3540)
- [x] DOMPurify sanitization for rich text content (#3527)

---

### 6.139 Bug Fixes & Quality (April 15–17, 2026)

**Purpose:** Roll-up of bug fixes, design gap closures, and quality improvements shipped during April 15–17.

- [x] **Study guide generation survives page refresh** — retain `autoGenerate` param until stream succeeds; auto-retry interrupted study guides (#3575, PR #3576) — Design Gap fix
- [x] **Save as Study Guide / Class Material** — fix `log_action` crash on missing `material_id`, correct response model for frontend consumption (#3533, PR #3554)
- [x] **Gmail reconnect uses popup OAuth** — open OAuth flow in popup window with correct `redirect_uri` instead of full-page redirect (#3523, PR #3525)
- [x] **Gmail reconnect banner** — show reconnect banner when Gmail integration is inactive, not just when missing (#3314, PR #3517)
- [x] **Email Digest button navigation** — fix button to navigate to dashboard when integration already exists (#3509, PR #3513)
- [x] **Daily email digest delivery** — fix scheduler misfire grace period, session poisoning from shared DB sessions, missing job registration (#3451–#3476, PR #3473)
- [x] **Parent UX** — deduplicate study times across children + add global quick actions to no-child view (#3495–#3496, PR #3502)
- [x] **Meta domain verification** — add meta tag for WhatsApp Business domain verification (PR #3578)

---

### Recent PRs (April 8–17, 2026)

| Commit | PR | Description |
|--------|----|-------------|
| 067e3934 | #3579 | feat: WhatsApp digest template formatting for production |
| f235b068 | #3578 | chore: Meta domain verification for WhatsApp Business |
| 9bda4932 | #3577 | feat: Notes Enhancement — Rich Text, Image Paste, Maximize, Export, Save-as-Material |
| fb981d3f | #3576 | fix: study guide generation survives page refresh during streaming |
| 2a9fcdc1 | #3559 | feat: replace Notes textarea with TipTap rich text editor |
| 3da76a15 | #3556 | feat: NoteImage model and API endpoints for image upload |
| 7975479c | #3555 | feat: ASGF integration bridges — 7 entry points + documentation |
| d199e995 | #3554 | fix: Save as Study Guide / Class Material — log_action crash, response model |
| b88d4ec6 | #3525 | fix: Gmail reconnect uses popup OAuth flow with correct redirect_uri |
| c1d6e67e | #3518 | feat: ASGF page — complete Ask-a-Question to Flash Study flow |
| 7efee95f | #3517 | fix: show Gmail reconnect banner when integration is inactive |
| 3c8e75da | #3502 | fix: parent UX — deduplicate study times + global quick actions |
| 5c0e6a84 | #3515 | feat: CB-ASGF-001 M5d + final polish — complete ASGF feature |
| 22f31f96 | #3513 | fix: Email Digest button navigates to dashboard when integration exists |
| ff30fd01 | #3452 | fix: add db.rollback() on digest failure + WhatsApp test script |
| be079287 | #3473 | fix: daily email digest not delivered — scheduler misfire, session poisoning |
| 7ce62843 | #3404 | feat: ASGF PEDI digest enrichment — session summaries for parent email |
| 08bd3798 | #3447 | feat: CB-ASGF-001 M5c Integration — quiz bridge, auto-save, role-aware assignment |
| 18371fbc | #3431 | fix: matchMedia test mock — unblocks deploy CI |
| 68ce28ce | #3434 | feat: CB-ASGF-001 M5b Generation — context assembly, slide renderer, generation |
| 74913cb8 | #3421 | feat: CB-ASGF-001 M5a Foundation — schema, intent classifier, upload, ingestion |
| 933ad66f | #3386 | fix: task filtering — correct child assignment + calendar dedup |
| 9d458218 | #3368 | feat: Solve with Explanations — problem solver guide type |
| 17861b67 | #3378 | fix: PDF black images, focus area, continue button |
| c07cc423 | #3362 | fix: My Kids page — panel order, material limit, collapse defaults |
| 0835d41f | #3357 | fix: Study Session page — trailing slash, centralized API, graceful degradation |
| 98861745 | #3356 | fix: Flash Tutor defects, nav icons, deploy workflow improvements |
| c03a7a58 | #3337 | feat: chatbot window drag, resize, and maximize |
| 2c935915 | #3379 | fix: assign auto-created tasks to child enrolled in source course |

---

### 6.135 Instant Trial & Demo Experience (CB-DEMO-001) — PLANNED

**Purpose:** Convert classbridge.ca visitors from waitlist-only → four-surface landing page (AI Instant Trial + Tuesday Mirror + Role Switcher + Proof Wall) to compress time-to-felt-value from days to <2 minutes and lift verified waitlist signups ≥3× in 14 days.

**Target launch:** May 13, 2026 (50/50 A/B). Sunset gate May 29, 2026 if M4 < 2.0×.

**Key deliverables:**
- [ ] demo_sessions table + backend routes (#3600, #3603, #3604, #3605, #3606)
- [ ] Feature flag variants (off/on_50/on_for_all) (#3601)
- [ ] Email verification magic link + 6-digit fallback (#3602)
- [ ] InstantTrialSection + InstantTrialModal + ConversionCard (#3607)
- [ ] Tuesday Mirror 5-beat storyboard, 5 boards (#3608)
- [ ] Role Switcher 4-role card (ROM field trip) (#3609)
- [ ] Proof Wall (live counter + testimonials + compliance badges) (#3610)
- [ ] Admin demo-sessions dashboard + landing wiring (#3611)
- [ ] Content + prompts + compliance docs (#3612)

**Scope deltas from PRD v1.1** (see issue #3599 for rationale):
- Model: claude-haiku-4-5 (not GPT-4o-mini)
- Turnstile deferred; slowapi + honeypot + disposable-email blocklist for v1.1
- PostHog deferred; structured JSON logs with correlation IDs
- i18n deferred (EN-only launch)
- Auto-approve demo-verified signups (anomaly flag → manual)
- Replaced "OECM procurement pathway" badge with "Canadian-hosted"
- Tuesday Mirror names the tools (Google Classroom, Teach Assist, Teams, etc.)

**Epic:** #3599 — see for full PRD + plan.

#### 6.135.1 Demo Scope Expansion — UNRESTRICTED (#3754)

**Change:** The instant-trial demo (ask / study_guide / flash_tutor) no longer restricts topics to the Grade 8 Ontario curriculum. Users can submit any topic and receive a real response.

**Why changed:** The original scope (PRD v1.1, via #3599) was chosen for cost control, brand safety, audience targeting, and abuse mitigation. After initial launch, the restriction was causing a poor UX — legitimate user questions outside Grade 8 were refused with a rigid "outside curriculum" message that felt at odds with the "try anything" landing-page framing.

**Mitigations preserved:**
- Token budgets (500 / 600 / 1200 per demo_type) bound Haiku output cost per request.
- slowapi rate limiting + disposable-email blocklist + honeypot still apply.
- `demo-safe` posture preserved: no persistence, no personalization, no user-data lookup.
- Cost per verified signup monitored per M5 KPI; watch for post-change drift.

**Acceptance criteria:**
- [x] All 3 prompt files (`prompts/demo/*.md`) updated — curriculum-scope rules removed
- [x] REQUIREMENTS updated to document the change
- [ ] Post-deploy: spot-check that Grade 10 Algebra, Grade 12 Calculus, university-level topics now produce on-topic responses
- [ ] Post-deploy: monitor M5 Cost per Verified Signup for >25% drift in first 14 days; revisit if so

**Supersedes:** any earlier "Grade 8 Ontario curriculum only" language in CB-DEMO-001 docs.

#### 6.135.2 Demo page re-plan (2026-04-20, issue #3758)

**Classification:** Design Gap — the original PRD v1.1 (#3599) shipped an always-on sample panel + optional "use my own text" toggle, a shared stream state, raw-JSON flash-tutor output, and no gated-extras surface. It did not account for a single-source picker, per-tab output cache, a flashcard UI, or an upsell path for non-live features (downloads, saves, follow-ups, more cards).

**Design updates (frontend-only, no backend changes):**
- **Single-source picker** — radio grid with `sample | paste | upload`. `upload` is gated: the input is disabled, clicking its label opens an inline upsell card ("Uploads unlock when you join the waitlist") and does NOT change the active source.
- **Per-tab cache** — each of the 3 tabs (Ask / Study Guide / Flash Tutor) keeps its own `{output, status, question, error}`. Switching tabs preserves state so users can compare lenses without re-running. Source changes clear `output` / `status` / `error` across all tabs (user-typed questions are preserved so the user doesn't have to retype).
- **Flash Tutor lens** — renders the Haiku JSON array via `FlashcardDeck` (flippable cards, keyboard-nav) instead of raw markdown.
- **Gated action bar** — below each completed output, per-tab actions (`ask`: save + follow-up; `study_guide`: download + save + follow-up; `flash_tutor`: download + save + more-flashcards). Each opens an inline upsell pointing at `/waitlist`. Free `Copy` is retained.
- **No backend changes in this phase** — `source_text` still strings through `POST /api/v1/demo/generate`. Upload remains gated; no file-upload endpoint is added.

**Covered by:** #3759 (FlashcardDeck), #3760 (GatedActionBar), #3761 (scroll-clip fix), #3762 (integration — SourcePicker + per-tab cache + wiring).

**Epic:** #3758.

#### 6.135.3 Modal Maximize Toggle — Phase 1 (#3755)

**Change:** `InstantTrialModal` now includes a maximize button in its header that toggles between the default size (`max-width: 640px; max-height: 92vh`) and a maximized size (`max-width: 95vw; max-height: 95vh`).

**Why:** Step 2 of the modal ("Your instant demo") renders variable-length streaming output that often exceeded 92vh and showed a scrollbar even after the §6.135 sizing tightening (#3751). Users reported the scrollbar as visually distracting. A discoverable maximize control lets users expand on demand instead of hard-coding a larger default.

**Design decisions:**
- Toggle placement: header, immediately before the close (`×`) button — mirrors standard OS window chrome (max → close).
- Icons: inline SVGs (~215 bytes each) — no icon-library dependency.
- Hidden on mobile (`<640px`) — mobile already uses a full-screen bottom sheet, so the button is redundant and the carve-out preserves the native-app feel.
- `:focus-visible` ring matches the close button for keyboard-a11y consistency.
- State is in-memory (React `useState`); not persisted across modal-open cycles. If usage data shows strong preference for maximized, a future change can persist to `localStorage` (tracked as follow-up in #3772).

**Acceptance criteria:**
- [x] Maximize button in `InstantTrialModal` header, keyboard-accessible
- [x] Toggles `.demo-modal--maximized` class between default and 95vw/95vh
- [x] Mobile (<640px): button hidden, bottom-sheet unaffected
- [x] Esc + close button still dismiss the modal
- [x] `:focus-visible` ring matches other header buttons
- [x] 2 regression tests (`aria-label` toggle + class application)

**Phase 2 (deferred to #3772 / #3752):**
- Migrate maximize into the shared `<Modal>` wrapper planned in #3752 (so any modal can opt-in via `maximizable` prop)
- Optionally persist the maximized state in `localStorage`

**Shipped:** PR #3757, merged 2026-04-19, deployed 2026-04-19 23:20 UTC.

#### 6.135.4 Demo Upload Gating Copy & Dismiss-on-Tab-Change (#3784)

**Change:** The source picker's "Upload a document" card replaces the literal copy `"PDF, DOCX (coming soon)"` with `"PDF, DOCX — unlocks with waitlist."`. The inline waitlist upsell overlay that appears when a user clicks the gated upload card now auto-dismisses when the user switches demo tabs (Ask / Study Guide / Flash Tutor), fixing a lingering-overlay defect where the upsell remained visible across tab changes.

**Why changed:** `"(coming soon)"` implied a missing backend capability and set the wrong expectation. In reality, the demo upload is a deliberate waitlist-conversion gate — the backend upload + extraction pipeline already exists in the authenticated app (`app/services/file_processor.py`, `POST /api/v1/asgf/upload`). The new copy is truthful about the gating reason ("unlocks with waitlist") and reinforces the conversion path rather than suggesting the product is incomplete. The dismiss-on-tab-change is a straight defect fix in the current overlay-state lifecycle.

**Mitigations preserved:** None applicable — this is a copy change plus a defect fix on an existing gated interaction. No behaviour change to upload handling, no backend change, no change to rate-limit or content-safety policies.

**Acceptance criteria:** see issue #3784 for the canonical list. At minimum:
- [ ] Source-picker "Upload a document" card renders `"PDF, DOCX — unlocks with waitlist."`
- [ ] Clicking the gated upload card opens the waitlist upsell overlay as today
- [ ] Switching demo tabs (Ask ↔ Study Guide ↔ Flash Tutor) auto-dismisses the upsell overlay
- [ ] No regressions to sample / paste source selection or to the `/waitlist` CTA link

**Supersedes:** the `"(coming soon)"` copy introduced by the v1.1 source-picker (§6.135.2).

#### 6.135.5 Ask Tab as Conversational Chatbox (#3785)

**Change:** The Ask tab transitions from single-shot Q&A to a multi-turn chatbox that mirrors the authenticated-app `HelpChatbot` UX — streaming assistant turns, pinned input at the bottom, starter suggestion chips on first open, and a paper-bubble thread of alternating user + assistant turns. Unverified demo users are capped at **3 assistant turns**; on turn 4, the panel swaps to an in-panel waitlist upsell ("Join the waitlist to keep asking follow-ups").

**Why changed:** Single-shot Ask under-sells the real product. In the authenticated app, Ask is conversational and thread-anchored to class materials — users rarely ask just one thing. The demo needs to convey that conversational depth in ~30 seconds so the "try anything" landing promise matches the felt experience.

**Mitigations preserved:**
- Existing demo rate-limit (3 generations / 24h per email, 10 / 24h per IP, $10 CAD daily cap) still applies — **each assistant turn counts as one generation** against the bucket.
- Content-safety post-generation check runs per turn (unchanged).
- 500-word input cap applies to each user turn.
- No persistence across session close — the thread lives only in client memory for the current modal session.

**Backend impact:** Extend `POST /api/v1/demo/generate` to accept a short conversation history (≤3 prior turns) as an additional input field, OR add a sibling `POST /api/v1/demo/ask/turn` endpoint if the existing route's contract is too constrained. Per-turn output is capped at 200–300 tokens (tighter than the current 500-token `ask` ceiling) to keep the chatbox feel snappy. Rate-limit bucket and content-safety path are unchanged; only the request shape and per-call token budget change.

**Scope boundary:** Chat state lives in the client for the active session only; no `demo_ask_threads` table, no server-side persistence. The 3-turn cap is enforced client-side and re-enforced by the rate-limit bucket server-side.

**Acceptance criteria:** see issue #3785 for the canonical list. At minimum:
- [ ] Ask tab renders a pinned-input chat thread with streaming assistant bubbles
- [ ] 3–4 starter suggestion chips visible on first open; chips pre-fill the input
- [ ] 3-turn cap enforced; turn 4 swaps the input for the in-panel waitlist upsell
- [ ] Each turn counts against the demo rate-limit bucket (email + IP + daily $ cap)
- [ ] `prefers-reduced-motion` respected on bubble/stream animations

#### 6.135.6 Flash Tutor Tab as Short Learning Cycle (#3786)

**Change:** The Flash Tutor tab replaces the current static 5-card deck with a **3-card adaptive Short Learning Cycle** that mirrors the authenticated Flash Tutor session loop from CB-ILE-001 (§6.134): card front → reveal back → self-grade (`Missed` / `Almost` / `Got it`) → next card. A mastery ring in the modal chrome tracks per-session progress; on completion, the panel shows a confetti burst + score summary + waitlist upsell ("Save your streak — join the waitlist").

**Why changed:** Static deck display does not convey the product's core loop. Users who try Flash Tutor in the demo should feel the mastery cycle — reveal, self-grade, advance — because that loop is what CB-ILE-001 is built around. A static deck reads as "flashcard viewer," not "Flash Tutor."

**Mitigations preserved:**
- All 3 cards are pre-generated in a single Haiku call before the cycle starts — **no per-card backend hit**, so a full cycle consumes exactly 1 generation against the rate-limit bucket (unchanged from today).
- Demo does NOT touch `ile_sessions`, `ile_mastery`, or `ile_mastery_service` tables — all mastery, streak, and score state is **client-side only** and does not persist across session close.
- Existing demo rate-limit (3 / 24h email, 10 / 24h IP, $10 CAD daily cap) and content-safety post-generation check are preserved.
- Output-token ceiling per generation unchanged (cards are smaller; 3-card output fits well inside the current `flash_tutor` budget).

**Scope boundary:** `prompts/demo/flash-tutor.md` may be updated to generate **3 cards instead of 5**, or a `demo_type=flash_tutor_cycle` variant may be introduced — whichever is less invasive to the existing prompt + generation pipeline. Mastery + streak tracking lives entirely in the client `useDemoGameState` hook (see §6.135.8). No new tables, no new authenticated-app coupling.

**Acceptance criteria:** see issue #3786 for the canonical list. At minimum:
- [ ] Flash Tutor tab renders a 3-card cycle with reveal + self-grade controls
- [ ] Mastery ring visible in tab chrome; updates after each self-grade
- [ ] Confetti + score summary + waitlist CTA on cycle completion
- [ ] Exactly 1 backend generation call per cycle (pre-generated cards)
- [ ] No writes to `ile_*` tables; no persistence across modal close
- [ ] `prefers-reduced-motion` disables confetti and reveal animations

#### 6.135.7 Study Guide Tab as Overview + Suggestion Chips (#3787)

**Change:** The Study Guide tab replaces the current "5 key points + 3 Q&A" markdown block with a **concise overview paragraph (≤150 words)** plus **4–6 suggestion chips**: `Generate a worksheet`, `Make a quiz`, `Create flashcards`, `Go deeper on [subtopic]`, `Ask a follow-up`. Non-follow-up chips open a scoped waitlist upsell describing the action they would take. `Ask a follow-up` routes the user to the Ask tab with the input focused and optionally pre-filled with the chip label.

**Why changed:** Bulleted key-points-plus-Q&A is dense and non-actionable — it shows the user *what* the guide says but gives them nowhere to go next. The real Study Guide in the authenticated product offers follow-up actions (see §6.132 UTDF Framework); the demo should mirror that pattern so the "where does this lead" moment lands inside the free experience rather than only after signup.

**Mitigations preserved:**
- Chips are **illustrative** — no AI generation is triggered on chip click.
- Only `Ask a follow-up` consumes demo quota (because it hands off to the Ask tab, which then spends an Ask turn per §6.135.5). All other chip clicks are free and open static upsell cards.
- Content-safety + rate-limit policies unchanged (no new backend calls from chips).
- 500-word input cap + session non-persistence unchanged.

**Scope boundary:** `prompts/demo/study-guide.md` is updated to produce the overview paragraph format (≤150 words, no bulleted key points, no Q&A block). Chip labels are **hard-coded in the frontend for v1** — not AI-generated — to keep the surface deterministic and cheap. The `Go deeper on [subtopic]` chip may interpolate a subtopic from the overview in a later iteration; v1 can ship with the literal label.

**Acceptance criteria:** see issue #3787 for the canonical list. At minimum:
- [ ] Study Guide tab renders a ≤150-word overview paragraph (no bullets, no Q&A)
- [ ] 4–6 suggestion chips visible below the overview
- [ ] Non-follow-up chips open a scoped waitlist upsell card
- [ ] `Ask a follow-up` routes to the Ask tab with the input focused
- [ ] No new backend calls triggered by chip clicks (other than the Ask-tab hand-off)
- [ ] `prompts/demo/study-guide.md` updated and covered by prompt-smoke tests

#### 6.135.8 Demo Gamification Layer (cross-cutting)

**Change:** Introduce a demo-wide client-side gamification layer across all three tabs:
- **XP bar + level counter** — Lv.1 → Lv.2 at 100 XP. Visible in the modal header, updates on tab interactions (Ask turns, Flash self-grades, Study Guide chip uses).
- **Quest tracker** — 3 diamond dots, one per tab, lighting up as the user engages each tab at least once.
- **Streak flame** — active at streak ≥ 2 consecutive `Got it` grades in Flash Tutor; dims on any `Missed` reset.
- **Achievement stickers** — 5 types popping onto the modal edge as earned, with one unambiguous trigger each (owner = the component that fires `earnAchievement(id)`):
  - **First Spark** — `id: 'first-spark'` — first demo generation (any tab). Owner: `InstantTrialModal` / `AskPanel` turn 1.
  - **Bullseye** — `id: 'bullseye'` — first `Got it` grade in Flash Tutor. Owner: `FlashTutorPanel`.
  - **Warming Up** — `id: 'warmup'` — streak ≥ 2 consecutive `Got it` grades in Flash Tutor (same streak that activates the Streak flame). Owner: `FlashTutorPanel`. Note: an earlier draft defined this as "all 3 tabs touched" at the quest-tracker layer; the shipped trigger is the Flash-streak semantic — see follow-up #3795.
  - **Triple Threat** — `id: 'triple'` — 3 Ask turns used in the same session. Owner: `AskPanel` (reserved; not yet wired — tracked separately).
  - **Level Up** — `id: 'levelup'` — hit Lv.2 (XP reaches 100). Owner: XP-bar / level-up overlay (reserved; not yet wired — tracked separately in #3862).
- **Mastery ring** — visible on Flash Tutor tab, reflects session mastery (see §6.135.6).
- **Confetti + level-up overlay** — fire at 100 XP with a waitlist CTA ("Save your streak — join the waitlist").

**Why:** Increases engagement time inside the demo modal, reinforces that the product is a "learning loop" and not a tool dump, and provides natural conversion-moment anchors (e.g. level-up → "save your streak on the waitlist"). All state is session-local; nothing persists across modal close.

**Mitigations preserved:**
- All gamification is **client-side only** — no new backend calls, no new tables, no new rate-limit buckets, no new content-safety paths.
- Respects `prefers-reduced-motion` — disables XP bar transitions, sticker pop-in, mastery-ring fill, confetti, and level-up overlay animations.
- No PII written anywhere; game state lives in React state in the modal instance only.

**Scope boundary:** All game-state primitives (XP, level, streak, quest progress, achievements earned) live in a single `useDemoGameState` hook with unit tests covering state transitions. UI components are isolated under `frontend/src/components/demo/gamification/` so they can be removed or feature-flagged without touching tab logic. No backend changes.

**Acceptance criteria:**
- [ ] `useDemoGameState` hook exists with unit tests covering state transitions (XP gain, level-up, streak increment/reset, quest dot lighting, achievement earning)
- [ ] XP bar + level counter visible in modal header; updates on tab interactions
- [ ] Quest tracker dots light up as user engages each tab
- [ ] Streak flame lights up at streak ≥ 2; dims on reset (`Missed`)
- [ ] 3 achievement stickers (First Spark, Bullseye, Warming Up) pop onto the modal edge as earned — Triple Threat and Level Up are reserved and tracked separately in #3857 and #3862
- [ ] Mastery ring visible on Flash Tutor tab (feeds from §6.135.6 state)
- [ ] Confetti + level-up overlay with waitlist CTA fire at 100 XP
- [ ] `prefers-reduced-motion` disables all animations + confetti
- [ ] All styles reference existing brand tokens (no new hardcoded colors) — see §6.135.9

#### 6.135.9 Demo Visual Alignment Decision — Path C Blend

**Change:** The demo modal visual system aligns with the existing ClassBridge brand tokens defined in `frontend/src/index.css`:
- Fonts: **Space Grotesk** (display) + **Source Sans 3** (body) — via `var(--font-display)` / `var(--font-sans)`
- Primary accent: `#4a90d9` — via `var(--color-accent)`
- Warm accent: `#f4801f` — via `var(--color-accent-warm)`
- Surface: white — via `var(--color-surface)`
- Ink: via `var(--color-ink)`

Demo-specific warmth (optional notebook-paper accents, washi-tape decorative strips, sticker-style achievements from §6.135.8) may **layer on top** of the brand tokens as a "public-face" voice, but the core palette + typography must match the authenticated app.

**Why:** An initial demo prototype (see `docs/design/cb-demo-001-gamified-prototype.html`) diverged substantially from brand — different fonts (Fraunces vs Space Grotesk), different accent (cyan vs steel blue), different surface (cream vs white). A coherent brand experience matters because the demo sells the real app — it should look like the real app with a slight extra warmth, not like a different product. The decision between "adopt the prototype palette wholesale" (Path A), "reject the prototype entirely" (Path B), and "keep the playful warmth but anchor on brand tokens" (Path C) is resolved in favour of **Path C**.

**Mitigations preserved:** N/A — this is a design-system decision, not a runtime change. No backend, no rate-limit, no content-safety surface touched.

**Scope boundary:** All new demo CSS must reference tokens from `frontend/src/index.css`. No hardcoded hex colors in demo component CSS except for the tokens themselves at the root. Existing demo CSS that already uses hex values (pre-dating this decision) is not in scope for this subsection — it will be migrated opportunistically as each §6.135.4–§6.135.8 stream touches its files.

**Supersedes:** any earlier "Notebook + Neon" or prototype-derived palette / font choices. The HTML prototype at `docs/design/cb-demo-001-gamified-prototype.html` may be refreshed or left as-is — it is a reference document, not a production artifact, and the production demo should not be driven from it.

**Acceptance criteria:**
- [ ] All new demo CSS uses `var(--font-display)`, `var(--font-sans)`, `var(--color-accent)`, `var(--color-accent-warm)`, `var(--color-ink)`, `var(--color-surface)` (and related tokens) — no hardcoded hex colors in demo component CSS
- [ ] Any new tokens required (e.g. for sticker washi-tape accents) are added to `index.css` rather than inlined
- [ ] The visual-alignment decision is linked from the demo component entry points so future contributors see it before adding styles
