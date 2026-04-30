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

#### §6.127.1 Per-Channel Delivery Status Contract (#3880, refined #3887)

**Added:** 2026-04-21 | **GitHub Issues:** #3880 (initial), #3887 (skip-vs-failure refinement)

Prior to #3880, the `POST /api/parent/email-digest/integrations/{id}/send-digest` endpoint always returned `status="delivered"` with the message `"Digest delivered with N emails"` — regardless of whether the email send actually succeeded or the WhatsApp delivery failed. Parents saw a green success toast even when they received nothing. #3880 fixed this with three states (delivered / partial / failed) but still conflated intentional skips (preference off, WhatsApp not verified) with actual delivery failures — parents saw "Failed channels: WhatsApp — check your setup" when they had simply not yet verified the channel. #3887 introduces a fourth state (`skipped`) and a three-valued per-channel convention so that intentional skips never masquerade as failures.

**Four delivery states (top-level `status`):**
- `delivered` — every selected channel with an actual outcome succeeded
- `partial` — at least one channel succeeded and at least one actually failed
- `failed` — every selected channel with an actual outcome failed
- `skipped` — every selected channel was intentionally skipped (preference off, WhatsApp not verified, no email on file) OR no channels were selected at all. Nothing was delivered, but nothing actually failed either.

"Selected channels" are parsed from `ParentDigestSettings.delivery_channels` (comma-separated subset of `in_app`, `email`, `whatsapp`). "Actual outcome" means `true` or `false` — channels with a `null` per-channel status are excluded from the overall-state computation entirely.

**Parent-facing copy (rendered on the Email Digest page):**
- `delivered` → green toast: `"Digest delivered with {N} emails"`
- `partial` → amber toast: `"Digest partially delivered ({N} emails). Failed channels: {list}. Check your setup."` — `{list}` contains only channels where the per-channel status was `false`, never channels that were skipped.
- `failed` → red toast with retry CTA: `"Digest delivery failed on all channels ({N} emails). Please try again or check your setup."`
- `skipped` → info toast (neutral blue) with a link to preferences, no retry CTA: `"No eligible channels ({N} emails). Please verify WhatsApp or enable notifications in your preferences."`

**Three-valued per-channel convention (`channel_status` dict on the response):**

Every per-channel field uses the same `true` / `false` / `null` semantics:

- `true` — channel was requested and delivery succeeded
- `false` — channel was requested and delivery actually failed (exception raised, or underlying send helper returned False)
- `null` — not applicable: channel was not requested, OR was requested but intentionally skipped (recipient preference off, no email on file, WhatsApp not verified / phone missing, no valid sender for the classbridge_message channel, etc.). `null` is explicitly NOT a failure. Frontends and analytics MUST NOT count `null` as a delivery failure.

Per-field specifics:
- `channel_status.in_app` — `true` if the in-app Notification row was created, `null` if `in_app` was not selected OR was selected but the recipient's notification preferences suppressed in-app delivery, `false` only on actual create-side exceptions.
- `channel_status.email` — `true` if `send_email_sync` returned True without raising, `false` if it returned False or raised (SendGrid error, SMTP failure, etc.), `null` if `email` was not selected OR the recipient has no email on file / has `email_notifications=False` / preference-suppressed email for this notification type.
- `channel_status.whatsapp` — `true` if the Twilio WhatsApp template/message send returned success, `false` if Twilio returned failure or the send raised, `null` if `whatsapp` was not selected OR WhatsApp is not verified / phone missing (parent hasn't completed setup — we cannot score this channel).

**Machine-readable skip reason (`reason` on the response, #3894):**

When `status="skipped"`, the response includes a `reason` field so that frontends can gate UI actions on the specific cause of the skip. When `status != "skipped"`, `reason` is `null` (or absent). Valid values:

- `"already_delivered"` — a digest was already delivered earlier today for this integration (deduplication skip on the scheduled run)
- `"no_settings"` — the integration has no `ParentDigestSettings` row configured
- `"no_new_emails"` — Gmail returned zero messages and `notify_on_empty=False`
- `"no_eligible_channels"` — the digest was generated but every selected channel was intentionally skipped (preference off, WhatsApp not verified, etc.). This is the only skip reason for which an "Open preferences" action is meaningful — the other three skips cannot be resolved by editing notification preferences.

Frontends MUST gate "Open preferences" / "Change settings" style CTAs on `reason === "no_eligible_channels"` rather than `status === "skipped"` alone.

**Persistence — `digest_delivery_log` table:**
- `status` — top-level state (`delivered` / `partial` / `failed` / `skipped`)
- `email_delivery_status` — `"sent"` / `"failed"` / `"skipped"` / `null` (`"skipped"` when email was selected but recipient has no email on file / preference off; `null` when email was not selected)
- `whatsapp_delivery_status` — unchanged (`"sent"` / `"failed"` / `"skipped"` / `null`)

Both per-channel columns enable analytics on channel reliability independent of the top-level summary status. Analytics queries distinguishing "delivery reliability" from "parent setup completeness" should filter on the column values: `"failed"` for reliability, `"skipped"` for setup completeness.

#### §6.127.2 Sectioned 3×3 Digest Contract (#3956 — Phase A of #3905)

**Added:** 2026-04-21 | **GitHub Issue:** #3956 (Phase A) — parent of #3905 multi-variable Twilio template redesign.

Parent feedback on the original single-HTML-blob digest: "text heavy, group in 3, 'More' opens ClassBridge". Phase A ships everything that can go live **without** Meta approval dependency; Phase B (#3905) adds the V2 Twilio template once Meta approves.

**Digest format:** `digest_format="sectioned"` is added alongside existing `full` / `brief` / `actions_only`. New parents default to `"sectioned"`; existing parents keep their configured format until explicitly migrated.

**AI-service JSON contract:**

`generate_sectioned_digest(emails, child_name, parent_name) -> dict` produces:

```json
{
  "urgent":        ["str", "str", "str"],
  "announcements": ["str", "str", "str"],
  "action_items":  ["str", "str", "str"],
  "overflow": {
    "urgent": 0, "announcements": 0, "action_items": 0
  },
  "legacy_blob":  null
}
```

- Each section: AT MOST 3 items, each ONE SHORT SENTENCE (max 140 chars), no HTML.
- `urgent` = due today or tomorrow. `announcements` = classroom posts, not time-sensitive. `action_items` = things the parent or child must DO.
- `overflow.<section>` = count of additional items we would have included if the cap were higher. Drives the "And N more →" CTA.
- Empty sections = `[]`. Empty overflow entries = `0` (never missing — Pydantic `SectionedDigest` coerces).
- On JSON parse failure or upstream AI error, the service falls back to the legacy `generate_parent_digest` call and returns `{"legacy_blob": "<html>"}`. Downstream renderers MUST check `legacy_blob` first and render the legacy HTML unchanged.

**Overflow / "More →" CTA:**
- Link target: `https://www.classbridge.ca/email-digest`
- Email path: rendered below each section's `<ul>` as `<p><a href="...">And {N} more → View full digest</a></p>`.
- WhatsApp V1 path: flattened inline as `(And N more)` inside the single-line-with-bullets string.
- WhatsApp V2 path: appended inside each section block as `+ And N more` below the bullet items.

**Per-channel rendering rules:**

- **Email (3×3 inline-styled HTML):** sections have coloured accents (Urgent 🔴 red `#dc2626`, Announcements 📢 grey `#6b7280`, Action Items ✅ blue `#2563eb`). `<h3>` heading + `<ul>` with up to 3 `<li>` + overflow `<p>` CTA. Inline CSS only (email clients strip `<style>`). Empty sections skipped entirely — no empty card is rendered.
- **WhatsApp V1 (current `TWILIO_WHATSAPP_DIGEST_CONTENT_SID` single-variable template):** sectioned content is flattened into a single-line-with-bullets string: `"Urgent • item1 • item2 • item3 • (And N more) • Announcements • ... • Action Items • ..."`. Empty sections are omitted (no heading appears). The existing #3941 sanitisation (`\n\n` → `•`, control-char stripping, 1024-char cap) is applied unchanged.
- **WhatsApp V2 (new `TWILIO_WHATSAPP_DIGEST_CONTENT_SID_V2` 4-variable template):** when the V2 env var is set, the digest job calls `send_whatsapp_template` with 4 variables:
  - `1` = parent_name
  - `2` = urgent block (up to 3 `- item` lines + optional `+ And N more`, newline-separated)
  - `3` = announcements block (same format)
  - `4` = action_items block (same format)
- **Empty-section substitution:** Twilio V2 template variables cannot be empty. Empty sections in the V2 path are substituted with the literal string `"(none)"`. V1 flatten and email renderers simply omit empty sections instead.

**V1 / V2 toggle:**
- `TWILIO_WHATSAPP_DIGEST_CONTENT_SID_V2` empty (default) → silent V1 fallback. No user-visible change.
- `TWILIO_WHATSAPP_DIGEST_CONTENT_SID_V2` set → V2 4-variable template used. Scheduled for Phase B once Meta approves.
- Env var is plumbed through `.github/workflows/deploy.yml` from GitHub Secrets, dormant until Meta approval.

**Supersedes §6.127.1 where it mentions the legacy single-variable template flow** — §6.127.1's three-valued per-channel delivery-status contract still applies unchanged to all three rendering paths (email, V1, V2).

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

### 6.128 Ask a Question — Parent Open-Ended Study Guide Generation (Phase 2) - DEPRECATED (superseded by §6.137 / CB-ASGF-001)

> **⚠️ DEPRECATED 2026-04-22 (#3955):** The in-wizard "Ask a Question" tab was removed. The canonical Ask flow is now **§6.137 AI Study Guide Generator (CB-ASGF-001)** at route `/ask` (ASGFPage). The legacy `document_type='parent_question'` → `CourseMaterialDetailPage` autoGenerate pipeline is no longer reachable from the UI. Any lingering `mode: 'question'` callers in `useParentStudyTools` are safely redirected to `/ask?question=<encoded>`. Backend prompts and services listed below remain in the codebase so existing parent-question study guides keep rendering, but no new ones can be created via this path.

**Why deprecated:** The modal flow created a CourseContent + relied on an autoGenerate redirect that produced the "We couldn't determine the document type" empty state when the stream kick-off failed (e.g. session expiry, stale content). ASGFPage replaces it with a first-class 5-stage wizard (Input → Processing → Slides → Quiz → Results) and is the only supported entry point going forward (sidebar nav + dashboard quick actions already route there).

---

**Historical reference (superseded):** Parents could type free-form education questions and get a structured study guide through the existing pipeline. No file upload or course content required.

**GitHub Epic:** #2861 — *Closed; see §6.137 for the successor feature.*

**User Flow (historical):**
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

**Known future enhancements (historical — no longer actionable since §6.128 is deprecated):**
- [ ] Document dual prompt locations — system in `study_guide_strategy.py`, user in `ai_service.py` (#2886)
- [ ] Add `CRITICAL_DATES` extraction to parent_question prompt for auto-task creation (#2887)
- [x] Convert continue endpoint to SSE streaming — spinner shows but no content streams (#2896) (FIXED — PR #2906)
- [x] Retire legacy in-wizard Ask tab; route parent questions to `/ask` (ASGFPage) (#3955) — **DEPRECATED ON 2026-04-22**

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
- [x] **Legacy in-wizard Ask tab removed (#3955):** The "Ask a Question" tab inside `UploadMaterialWizard` (originally part of §6.128) was retired; `/ask` is now the single canonical entry point for open-ended parent/student questions. `useParentStudyTools.handleGenerateFromModal` redirects any stray `mode: 'question'` caller to `/ask?question=<encoded>` as a safety net.

**Issues:** #3531-#3539, #3955 | **Key PR:** #3555

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

**Design note — persisted content cap (#3843, 2026-04-20):** `DemoGenerateEvent.user_content` and `DemoGenerateEvent.assistant_content` (the server-reconstructed history source introduced in #3819) are capped via `_DEMO_PERSISTED_CONTENT_MAX_CHARS` in `app/schemas/demo.py`. The cap was raised from 500 to **1260 chars** after measurement. A 20-sample Haiku sweep of diverse Ask questions (`ask` prompt at `max_tokens=300`, temperature 0.7) produced p50=837, p95=1108, p99=1145 chars; 80% of typical replies exceeded the original 500-char cap, which truncated honest-user turns mid-sentence when replayed as history on turn 2. New cap = `round(p99 * 1.1) = 1260`, still well below the 2000-char "prompt is wrong" ceiling. Input-side abuse is still bounded — only the last completed Ask turn is replayed (§6.135.5, #3819) and each user turn is independently capped at 500 words via the rate-limit layer.

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

### 6.140 Landing Page Redesign (CB-LAND-001) — SHIPPED (2026-04-21)

**Purpose:** Replace the current `LaunchLandingPage.tsx` (hero + 4 demo surfaces + 4 feature cards + footer) with a 12-section Mindgrasp-inspired persuasion architecture, aligned to the CB-DEMO-001 brand tokens (Path C decision, §6.135.9). Coexists with CB-DEMO-001 — the existing `InstantTrialModal` / `TuesdayMirror` / `RoleSwitcher` / `ProofWall` are wrapped behind a new flag-gated `landing_v2` scaffold rather than replaced.

**Epic:** #3800 (open) — initially claimed requirements would land under §6.136, but §6.136 was already used for Problem Solver; this section is filed as §6.140 post-hoc to close the documentation gap.

**Reference material:**
- `docs/design/landing-v2-reference/` — 12 annotated Mindgrasp.ai screenshots
- Visual system inherits §6.135.9 Path C (Space Grotesk + Source Sans 3 + `var(--color-accent)` / `var(--color-accent-warm)`; no new hardcoded hex)

**Section map (Mindgrasp → ClassBridge):**

| # | Section | Child issue | PR | Shipped |
|---|---------|-------------|----|---------|
| S1 | Design tokens + typography | #3801 | #3821 | ✅ 2026-04-21 |
| S2 | `LandingPageV2` scaffold + `landing_v2` flag + section registry | #3802 | #3849 | ✅ 2026-04-21 |
| S3 | Hero — `Close the homework gap. Together, in *one place.*` + demo CTA + waitlist + Ontario-board trust bar | #3803 | #3831 | ✅ 2026-04-21 |
| S4 | Pain — `School communication is *broken.*` + 4 role-quote cards | #3804 | #3823 | ✅ 2026-04-21 |
| S5 | Feature rows — 6 alternating pastel rows (AI Study Guides · Flash Tutor · Quizzes + Flashcards · Parent Digest · Classroom/Boards · Messaging) | #3805 | #3837 | ✅ 2026-04-21 |
| S6 | How It Works — 4-step accordion + synced preview | #3806 | #3824 | ✅ 2026-04-21 |
| S7 | Old vs New — 5 ✗/✓ comparison rows | #3807 | #3825 | ✅ 2026-04-21 |
| S8 | Progress tracking — 2×2 grid (Activity · Streak/XP · Per-Child Focus · Resume) | #3808 | #3826 | ✅ 2026-04-21 |
| S9 | Learner-segment tabs (Parents · Students · Teachers · Admins · Private Tutors) | #3809 | #3836 | ✅ 2026-04-21 |
| S10 | Cross-device + integrations bar (Web · iOS · Classroom · YRDSB · WhatsApp) | #3810 | #3835 | ✅ 2026-04-21 |
| S11 | Pricing teaser — Free · Family · Board | #3811 | #3830 | ✅ 2026-04-21 |
| S12 | Final CTA + footer polish | #3812 | #3827 | ✅ 2026-04-21 |

**Cross-cutting streams (still open as of 2026-04-21):**
- S13 Motion + microinteractions (#3813) — `in-progress`
- S14 Accessibility pass WCAG 2.1 AA (#3814) — `in-progress`
- S15 SEO + meta / OG / JSON-LD / lazy-load (#3815) — `in-progress`
- S16 Analytics (section-view + CTA click events) (#3816) — `in-progress`
- S17 Frontend tests (render / keyboard / reduced-motion / flag on-off) (#3817) — `in-progress`

**Fast-follows filed (open):**
- #3822 — S1 follow-up: reduced-motion token semantics + font load strategy
- #3828 — S8 ProgressGrid headline font-face vs. reference
- #3829 — S12 footer bg tokenization + dark-cyan gradient stop + real social SVGs
- #3832 — S6 How It Works mobile preview pane UX
- #3833 — S3 trust-bar boards source from TuesdayMirror data
- #3834 — S3 swap hero mockup placeholder for real product screenshot
- #3838 — S5 FeatureRow polish (safer headline, real icons/screenshots, RTL flip, test ordering)
- #3850 — S2 fast-follow: `HomeRedirect` calls `useVariantBucket` even for authed users + redundant `.test.` filter in `sectionRegistry`

**Success metrics:**
- **M1** — landing → demo click-through ≥ 25% (baseline to capture pre-50% rollout)
- **M2** — landing → waitlist signup conversion +50% vs v1 landing
- **M3** — bounce rate −20%
- **M4** — Lighthouse Performance ≥ 90, Accessibility ≥ 95, SEO ≥ 95
- **M5** — zero regressions in CB-DEMO-001 demo-completion funnel

**Rollout:**
- Feature flag `landing_v2` (mirrors `demo_landing_v1_1` pattern) — 0% → 5% → 25% → 50% → 100%
- Kill-switch: flag off → renders existing `LaunchLandingPage` (no code removal)
- Target wide-rollout: May 2026 (Phase 2)

**Scope boundary:**
- Coexists with §6.135 CB-DEMO-001; does not replace InstantTrialModal / TuesdayMirror / RoleSwitcher / ProofWall — only re-composes them inside the new 12-section scaffold.
- Frontend-only feature. Backend touched in #3849 only to add `landing_v2` to the feature-flag seed list and admin surface.
- No database schema changes.
- No new Python routes beyond the feature-flag enablement in S2.

#### 6.140.2 Visual system (CB-LAND-001)

Inherits §6.135.9 Path C tokens (Space Grotesk + Source Sans 3 + `var(--color-accent)` / `var(--color-accent-warm)`; no new hardcoded hex). Section-specific visual conventions:

- **Brand logo sizing (#3902 / #3908):** nav 64px desktop / 44px mobile; footer 80px. Intrinsic img width/height must match CSS height × ~2.14 (v6 asset is 400×187, ratio ≈ 2.139:1) to preserve CLS. Shipped values: nav `137×64`, footer `171×80`.
- **Logo asset (#3908):** `/classbridge-logo-v6.png` (tight-cropped variant, ~5% whitespace) across all UI surfaces. The loose-cropped `classbridge-logo.png` / `classbridge-hero-logo.png` (1536×1024, 3:2 ratio) are kept for JSON-LD `logo` and OG `og:image` fallback only in `LandingSeo.tsx` — search engines and social unfurls prefer a logo with safe-zone padding around the artwork.

**Feature-flag kill-switch semantics (#3930):** `enabled=false` is the authoritative kill-switch for DB-backed flags (`landing_v2`, `demo_landing_v1_1`, etc.). When `enabled=false`, the `variant` field is advisory only — the backend `/api/features` coerces `_variants[key]` to `"off"` (Stream B #3932), and the frontend `useVariantBucket` short-circuits to `'off'` before consulting variant (Stream A #3931). The admin UI warns on mismatched state (Stream C #3933). Authors of new DB-backed flags MUST preserve this contract. Same semantics apply to `demo_landing_v1_1` (see §6.135 CB-DEMO-001).

#### 6.140.7 Analytics funnel (CB-LAND-001)

**Events:**
- `landing_v2.section_view` — props: `section` (one of `hero` / `pain` / `features` / `how_it_works` / `old_vs_new` / `progress` / `segments` / `integrations` / `pricing` / `final_cta`).
- `landing_v2.cta_click` — props: `cta` (`primary` / `secondary` / `demo` / `waitlist` / `get_started` / `board`), `section`.
  - `get_started` (added #3889): fired on secondary CTAs when `waitlist_enabled=false` (launch mode). Routes to `/register` instead of `/waitlist`.

**Funnel:** `section_view(hero)` → `cta_click(demo | waitlist | get_started)` → demo completion / register / waitlist signup. The `waitlist` and `get_started` CTAs are mutually exclusive per session (gated by `waitlist_enabled`) — dashboards should union the two buckets when comparing landing → signup conversion across the `waitlist_enabled` flip.

#### 6.140.8 Post-deploy hardening round (PR #3888, 2026-04-21) — SHIPPED

One-day post-ship defect sweep after CB-LAND-001 hit production (revision `classbridge-01125-2sl`). Flag stayed `off` throughout — fixes landed before first ramp.

| Issue | Defect | Fix |
|-------|--------|-----|
| #3885 | LandingPageV2 had no visible ClassBridge brand — no top nav, no logo | New `LandingNav` section (`order: 5`): sticky logo + Log In + primary CTA. Footer also gained a decorative logo. |
| #3889 | Hero / FinalCTA / PricingTeaser / Nav hardcoded "Join Waitlist" CTAs — ignored `waitlist_enabled` admin toggle (regression of #1219 for legacy landing) | New `useLandingCtas()` hook — single source of truth for CTA label / href / pricing-mode branching on `waitlist_enabled`. All 4 consumers migrated. |
| #3893 | `PricingTeaser` Family tier CTA routed to `/register` in launch mode with no subscription flow | Launch mode renders disabled "Coming soon" + "join the early-access list" sub-copy linking to `/register` only. |
| #3895 | `useFeature('waitlist_enabled')` returned `false` during TanStack Query hydration → "Get Started" flicker on cold loads when admin had waitlist enabled | Per-key `DEFAULT_DURING_LOAD = { waitlist_enabled: true }` in `useFeatureToggle`. Applies to legacy `LaunchLandingPage` too. |
| #3892 | §6.140.7 funnel docs missing `get_started` CTA enum | Added above (§6.140.7). |
| #3897 | `LandingFooter.css` used `filter: brightness(0) invert(1)` to whiten the color logo on dark bg | Swapped to existing `/classbridge-logo-dark.png` asset; filter hack removed. |
| #3898 | CTA copy duplicated per-consumer (nav "Join Waitlist" short vs hero "Join the waitlist" long) | `useLandingCtas` now exposes `secondaryLabel` (long) + `secondaryLabelShort` (short). |
| #3899 | Section-id string literals scattered across registry / page split / section files | New `frontend/src/components/landing/sectionIds.ts` with `LANDING_SECTION_ID` const + `LandingSectionId` type. All 12 section files + `LandingPageV2` footer-split migrated. |
| #3930 | Feature-flag kill-switch broken — `useVariantBucket` ignored `enabled` boolean, so admin toggle-off had no effect when variant remained `on_for_all`. Both `landing_v2` and `demo_landing_v1_1` affected. | Defense-in-depth: frontend hook short-circuit (#3931), backend `/api/features` response coercion (#3932), admin UI mismatch warning (#3933) + Auto-fix button, docs (#3935). |
| #3902 | Nav + footer logos too small — user-reported visibility issue | Bumped CSS heights: nav 64px desktop / 44px mobile, footer 80px. Intrinsic `width`/`height` attrs bumped in lockstep for CLS. |
| #3908 | Logo PNGs had ~70% baked-in whitespace; CSS height bump scaled the padding too | Swapped `/classbridge-logo.png` → `/classbridge-logo-v6.png` (tight-cropped, 400×187, ~5% whitespace, 50 KB). Nav intrinsic attrs `137×64`, footer `171×80` (preserve 2.139:1 ratio). Legacy negative-margin hacks on `.launch-nav-logo` removed (no longer needed). Footer re-added `filter: brightness(0) invert(1)` (v6 is gradient; filter flattens to white on dark bg). |
| #3939 | PR #3910 accidentally replaced the custom `classbridge-hero-logo.png` illustration (children + book + bridge) on legacy `LaunchLandingPage` with the plain v6 wordmark | Reverted hero `<img src>` + restored compositionally-tuned negative margins on `.launch-hero-logo` (desktop `-24px auto -16px`, mobile `-10px auto -10px`). Inline CSS comment added to prevent re-regression. |
| #3958 | Deploy #1422 failed — `AdminFeaturesPage.test.tsx` Auto-fix button test triggered an unmocked `/api/features` refetch that crashed jsdom/undici in CI with `InvalidArgumentError: invalid onError method` | Extended the existing `vi.mock('../../api/client')` in the test file to stub the `api` axios instance (get/post/patch/put/delete). Production code untouched. |

**Quality gates:** `npm run build` clean · `npm run lint` 0 errors · all landing tests pass · 2× `/pr-review` per fix branch + orchestrator-level review across PR #3888, #3903, #3910, #3944, #3961.

**Workflow:** parallel isolated-worktree streams per fix → per-round integration branches (`fix/3885-landing-v2-logo`, `integrate/killswitch-fix`) → one PR to master per round. 24 PRs total across the redesign + hardening + activation epics.

#### 6.140.9 Open fast-follows (deferred polish — all `CB-LAND-001-fast-follow`)

**Design / content:**
- #3828 — S8 ProgressGrid headline font-face vs reference
- #3829 — S12 footer: tokenize bg + gradient stop + real social SVG icons (superseded partially by #3897; see residual)
- #3832 — S6 How It Works mobile preview pane UX
- #3833 — S3 trust-bar boards should be sourced from `TuesdayMirror` data
- #3834 — S3 swap hero mockup placeholder for real product screenshot
- #3838 — S5 FeatureRow polish (safer headline, real icons/screenshots, RTL flip, test ordering)
- #3875 — real 1200×630 `og-image.png` asset (OG currently points to `classbridge-hero-logo.png` as fallback)

**Engineering:**
- #3822 — S1 reduced-motion token semantics docs + render-blocking font-load revisit
- #3850 — `HomeRedirect` calls `useVariantBucket` even for authed users + redundant `.test.` filter in `sectionRegistry`
- #3852 — add `vitest-axe` + automated axe-core scan to landing-v2
- #3853 — body-text contrast audit (cyan accents + pastel row bg) against WCAG AA
- #3858 — S16 analytics: StrictMode-safe step_view + tab_change guards; ref-callback hook; section_view unit test
- #3911 — v6 hero logo may appear soft at 280px on retina (#3908 follow-up) — post-deploy visual check pending

All non-blocking; epic #3800 tracks overall completion. Epic closes once retina visual check passes (#3911) and V2 rolls to 100 % (currently `on_for_all` live).

#### 6.140.10 Deploy trail (2026-04-21 → 2026-04-23)

| Date (UTC) | Revision | SHA | Contents |
|------------|----------|-----|----------|
| 2026-04-21 17:30 | classbridge-01125-ksj* | `6147806c` | CB-LAND-001 main redesign (`99a06cf9` #3871) + docs (`e6a5650f` #3818) + CI tweak (`6147806c` #3882) |
| 2026-04-21 23:09 | classbridge-01128-mwp | `80f6572b` | Digest delivery honesty (#3886 / #3879+#3880+#3884) |
| 2026-04-21 23:46 | classbridge-01128-mwp | `98467ba6` | Logo size bump (#3903) + WhatsApp \n→ bullet hotfix (#3942) |
| 2026-04-22 01:49 | classbridge-01128-mwp | `42ca2d06` | v6 logo tight-crop swap (#3910) |
| 2026-04-22 03:15 | (same) | `a582c150` | WhatsApp template newline hotfix (#3906 + #3942) |
| 2026-04-22 15:06 | **FAILED** | — | Scheduled deploy of `a8c54abf` (kill-switch PR #3944) blocked by test crash in `AdminFeaturesPage.test.tsx` |
| 2026-04-23 00:13 | classbridge-01130-jqx | `1be02431` | **Current live.** Kill-switch defense-in-depth (#3944) + test mock (#3961) + CB-TASKSYNC-001 MVP-1 (#3946) + Ask-tab retirement (#3959) + CB-PEDI Phase A (#3962 / #3956 3×3 digest restructure with dormant V2 code path). Snapshot tag: `snapshot/2026-04-22-pre-killswitch-deploy` (at `0a693504`); deploy tag: `deploy/2026-04-22-1be02431`. |

Post-`1be02431` verification (live):
- `curl /api/features` with enabled=false on `landing_v2` → `_variants.landing_v2 === "off"` ✅ (kill-switch working)
- Legacy hero renders children + book + bridge illustration ✅
- V2 WhatsApp Content Template `classbridge_daily_digest_v2` (`HX7f765c17b88be6b90b564748b68458c4`) submitted to Meta; business-initiated review pending (see #3987 for activation)

---

### 6.141 Unified Tutor + Arc Mascot (CB-TUTOR-001) — 2026-04-22

**Purpose:** Merge the Ask-a-Question (CB-ASGF-001, §6.137) and Flash Tutor (CB-ILE-001, §6.134) surfaces into a single Arc-led `/tutor` page, ending the duplicate AI-tutor entry points that confused parents and students.

**Delivered (PR #3974, `integrate/pr-review-3966` → master):**

**New components**
- [x] `ArcMascot` — ClassBridge Learning Companion SVG (5 moods: neutral/thinking/happy/celebrating/waving) with `decorative` prop for labeled-container usage. Visual DNA drawn from the ClassBridge logo (arc smile + 3 floating sparkles mirror the bridge + 3 dots).
- [x] `lib/routing-helpers.tsx` — shared `RedirectPreservingQuery` + `LegacySessionRedirect` used by App.tsx and routing tests.

**Removed**
- [x] `ASGFPage.tsx` / `.css` deleted; behavior lifted into `TutorPage.tsx`.
- [x] `FlashTutorPage` no longer routed (file retained in tree as a future-delete marker; all functionality absorbed by drill mode).
- [x] `XpStreakBadge` component + CSS + export (deferred until real `/api/xp/summary` endpoint is wired — see fast-follows).

**Routing**
- [x] Canonical: `/tutor` (explain mode default), `/tutor?mode=drill`, `/tutor/session/:id`.
- [x] Legacy redirects (query-preserving): `/ask` → `/tutor`, `/flash-tutor` → `/tutor?mode=drill`, `/flash-tutor/session/:id` → `/tutor/session/:id`.
- [x] `/tutor` allows `parent`, `student`, `teacher` roles.

**Page modes (on `/tutor`)**
- [x] **Explain & learn** — conversational ASGF flow (intent classify → slides → quiz → results). Quick-prompt chips, attach drawer (PDF/DOCX/images), context drawer (child/subject/grade).
- [x] **Drill a topic** — ILE flow. Course-topic grid (with Show-all-N toggle), search, 🎲 Surprise Me, parent child-selector (2+ kids), sub-modes (Learning / Testing / Parent Teaching — parents only), question count (3/5/7), difficulty (easy/medium/challenging). Start kicks off an ILE session and navigates to `/tutor/session/:id`.
- [x] URL sync: `?mode`, `?submode`, `?content_id`, `?child_id` — all round-trip through `setSearchParams` so bookmarks + refresh preserve state.
- [x] Auto-start: `/tutor?content_id=N` triggers `ileApi.createSessionFromStudyGuide` → redirect to session runner. URL synchronized before API call so refresh-on-failure preserves drill intent.

**Sidebar**
- [x] Collapsed "Ask a Question" + "Flash Tutor" entries into single "Tutor" link (parent/student/teacher variants).

**HelpChatbot FAB**
- [x] `/chat-icon.png` replaced with `<ArcMascot>` (waving mood, glow halo); header mascot reacts to streaming state (thinking mood). Both usages pass `decorative` so screen readers read the parent button/heading label, not Arc's.

**Accessibility**
- [x] Mode switcher uses `role="group"` + `aria-pressed` (dropped incomplete `role="tab"` pattern).
- [x] `ArcMascot` respects `prefers-reduced-motion` via both JS prop and CSS media query.
- [x] `role="listitem"` anti-pattern removed from quick-prompt chips.

**Tests (46 passing across touched suites)**
- 3 regression tests from original ASGF work (eager SSE, abort-on-retry, stage transition)
- 4 new drill-mode tests (child selector, submode deep-link, URL sync, ARIA semantics)
- 8 routing tests (query preservation, role gating, legacy redirect, canonical session route)
- 3 ArcMascot component tests (default/custom label/decorative branching)
- Existing DashboardLayout + HelpChatbot tests unchanged (still green)

**Quality gates:** `npm run build` clean · `npm run lint` 0 errors on touched files · 2 rounds of `/pr-review` (pass 1: 10 findings = 3 CRITICAL + 7 IMPORTANT; pass 2: 0 findings, 4 SUGGESTIONS all fixed). All 21 review-tracked issues closed.

**Workflow:** 4 parallel isolated-worktree streams (routing / drill-parity / a11y / XP-cleanup) + 1 round-2 suggestion stream → merged sequentially into `integrate/pr-review-3966` → single PR to master.

#### 6.141.1 Fast-follows — RESOLVED 2026-04-23 (PR #4025)

All five §6.141.1 non-goals from the initial CB-TUTOR-001 ship have been delivered in integration PR #4025 (`integrate/cb-tutor-001-followups`):

- [x] **XP API wiring (#4019)** — `GET /api/xp/summary` already existed (XpLedger/XpSummary tables); added Pydantic `@computed_field` so the JSON serializes both `total_xp` AND `xp_total` without duplicate Python attributes. `XpStreakBadge` component resurrected from commit `79be73fc^`, gated in hero by `xp_total > 0 OR streak_days >= 2` (no "0 XP" stub). useQuery has `enabled: !!user`. aria-live moved to sr-only sibling to prevent tick-by-tick announcement noise. Reduced-motion users get immediate snap (no interval animation).
- [x] **T/F + fill-in-the-blank rendering (#4020)** — `FlashTutorSessionPage` branches on `question.format`: `true_false` → 2 radio-role buttons; `fill_blank` → existing `FillBlankCard` (untouched). `ASGFQuizBridge` branches identically, with a `normalizeAnswer` helper (punctuation + whitespace + case) for fill-blank matching. MCQ regression-test locked. (ASGF backend still enforces 4-option MCQ generation at `app/schemas/asgf.py:230`; UI is ready for future backend emission.)
- [x] **Delete `FlashTutorPage.tsx` (#4021)** — 1,124 lines deleted (page + CSS + App.tsx comment). Zero remaining callers verified pre-delete.
- [x] **Drill child overdue counts (#4022)** — new `useChildOverdueCounts` hook shares queryKey `['parent-dashboard']` with `useParentDashboard` (React Query dedupes to one `parentApi.getDashboard()` call). Same filter semantics as the dashboard. Task type tightened upstream — no inline casts.
- [x] **`FlashTutorSessionPage` Arc refresh (#4023)** — owl `TutorAvatar` swapped for `<ArcMascot size={64} mood="celebrating" decorative />` at the "Session Complete!" heading. `TutorAvatar.tsx` file deleted in the same integration (orphaned after #4021 landed).

**Quality gates:** `npm run build` clean · `npm run lint` 0 errors · 86 frontend tests + 65 backend XP tests passing · 2 rounds of `/pr-review` (pass 1: 0 Critical + 8 Important + 5 Suggestions all fixed in round-2 streams; pass 2: APPROVE — 0 Critical + 0 Important + 5 Suggestions, all resolved in round-3). All 12 review-tracked issues (#4019–#4032) closed.

**Workflow:** 4 parallel isolated-worktree streams (α=XP, β=quiz types, γ=cleanup+overdue, δ=session-Arc) → merged into `integrate/cb-tutor-001-followups` with conflict resolution in TutorPage.tsx + test; 3 round-2 streams (XP a11y, hook/alias, QuizBridge polish); 1 round-3 stream (pass-2 suggestions). Single PR to master: #4025.

#### 6.141.2 Remaining open work (tracked but unscoped)
- **ASGF backend emission of T/F + fill_blank** — schema validator currently enforces 4-option MCQ in `asgf_quiz_service.py`; loosening + prompt template updates = separate backend PR. UI is ready; frontend change not needed when this lands.
- **Fill-blank article-strip edge case (#3265)** — pre-existing ILE backend fuzzy-match concern; unchanged by this work.

---


### 6.142 Rock-solid Tutor v2 — Chat-first Q&A + Short Learning Cycle (CB-TUTOR-002) — Phase 1 IN PROGRESS 2026-04-24

**Purpose:** Rebuild `/tutor` into a rock-solid, pedagogically sound learning surface that fixes three concrete CB-TUTOR-001 regressions reported by the user: (1) "AI keeps asking for context" on simple questions, (2) "very slow" responses, (3) monolithic 7-slide-then-quiz flow ≠ the short learning cycle concept. Replaces the ASGF "teach-all-then-test-all" flow with:
1. **Chat-first Q&A** — answer the first question directly; context applies on follow-ups (last 3 turns)
2. **Short learning cycle loop** — teach subset → test subset → coach on failure (3 tries) → teach next subset → loop, with diminishing-returns XP for students
3. **Streaming + background tasks** — < 500ms to first token; heavy work off the request path
4. **Child safety** — OpenAI moderation + PII scrubber + grade-level tone adapters
5. **Paywall gate** — `tutor_chat_enabled` + `learning_cycle_enabled` admin feature flags, default off

**Design doc:** [docs/design/CB-TUTOR-002-short-learning-cycle.md](../docs/design/CB-TUTOR-002-short-learning-cycle.md)
**Epic:** [#4062](https://github.com/theepangnani/emai-dev-03/issues/4062)
**Master snapshot tag:** `snapshot/2026-04-24-pre-cb-tutor-002` (at `3b8eab19`)

#### 6.142.0 Locked decisions (2026-04-24)

| # | Decision |
|---|---|
| 1 | Chat memory scope = last 3 turns inherited for follow-up context |
| 2 | Chunk shape = 1 short teach block + 3 mixed questions (MCQ + T/F + fill-blank) per chunk · 4-6 chunks per topic · complexity progresses easier→harder |
| 3 | 3-try flow = force move-on after 3rd wrong; reveal answer + explanation; no per-try "show me" escape |
| 4 | Teacher / Parent-Teaching modes = kept, but **no XP** (student-only reward) |
| 5 | Legacy `/ask` and `/flash-tutor` redirects = keep indefinitely (no sunset) |
| 6 | Rate limits = Tutor chat behind admin feature flag `tutor_chat_enabled` (paywall); flag default = `off` until launched |

#### 6.142.1 Phase 1 — Chat-first Q&A (10 parallel streams landed on `integrate/cb-tutor-002-phase-1`)

Streams complete (all pushed, all build/lint/tests green in their isolated worktrees):

| Stream | Branch | Issue | Key deliverables |
|---|---|---|---|
| P1-Backend | `fix/4063-tutor-chat-sse` | [#4063](https://github.com/theepangnani/emai-dev-03/issues/4063) | `POST /api/tutor/chat/stream` SSE endpoint (token/chips/done/error events) · feature-flag gate (`tutor_chat_enabled`) · 20/hr rate limit · `TutorConversation` + `TutorMessage` DB models · moderation pass before streaming · last-3-turn memory loader |
| P1-Prompts-Safety | `fix/4064-tutor-prompts-safety` | [#4064](https://github.com/theepangnani/emai-dev-03/issues/4064) | `app/prompts/tutor_chat.py` (system+user prompt builders, `[[CHIPS: …]]` directive) · `app/services/safety_service.py` (OpenAI `omni-moderation-latest` + PII scrubber for phone/email/SIN) · `app/prompts/grade_tone.py` · 30 tests |
| P1-Frontend | `fix/4065-tutor-chat-component` | [#4065](https://github.com/theepangnani/emai-dev-03/issues/4065) | `components/tutor/` — `TutorChat`, `TutorMessage`, `TutorSuggestionChips`, `TutorInputBar`, `useTutorChat` SSE hook · gated in `TutorPage` behind `tutor_chat_enabled` feature flag · asymmetric chat design (warm-orange accent, Space Grotesk display font, spring-easing motion) · 5 tests |
| P1-Admin | `fix/4066-tutor-chat-feature-flag` | [#4066](https://github.com/theepangnani/emai-dev-03/issues/4066) | Seeded `tutor_chat_enabled` + `learning_cycle_enabled` flags (both default off) · `useTutorChatEnabled` hook wrapper · 9 tests |
| P2-Backend-Model | `fix/4067-learning-cycle-model` | [#4067](https://github.com/theepangnani/emai-dev-03/issues/4067) | `LearningCycleSession` + `Chunk` + `Question` + `Answer` ORM models with UUID PKs, CHECK-constraint enum columns, cascade deletes, TIMESTAMPTZ/DATETIME gating, JSONB/JSON gating · 14 tests |
| P2-Backend-Prompts | `fix/4068-cycle-prompts` | [#4068](https://github.com/theepangnani/emai-dev-03/issues/4068) | `app/prompts/learning_cycle.py` — 5 builders: topic_outline, chunk_teach, chunk_questions (enforces mcq+true_false+fill_blank trio), retry_hint (no answer leakage), answer_reveal · 12 tests |
| P2-Frontend-Shell | `fix/4069-cycle-shell` | [#4069](https://github.com/theepangnani/emai-dev-03/issues/4069) | `/tutor/cycle/:id` route + page · `components/cycle/` — `CycleTeachBlock`, `CycleQuestion` (3-format renderer), `CycleFeedback` (correct/retry/reveal), `CycleProgress`, `CycleResults` · `FlashCycleCard` + `MasteryRing` + `GradeButtons` lifted from demo · per-chunk warm-accent rotation · 4 tests |
| P3-Prompt-Refactor | `fix/4070-answer-first-prompts` | [#4070](https://github.com/theepangnani/emai-dev-03/issues/4070) | Rewrote ASGF (`_SYSTEM_PROMPT`, `_ALTERNATIVES_SYSTEM_PROMPT`, `_PLAN_SYSTEM_PROMPT`) + ILE (`_MCQ_SYSTEM`, `_FILL_BLANK_SYSTEM`, `_HINT_SYSTEM`, `_EXPLANATION_SYSTEM`) prompt strings to answer-first (default Grade 7, never ask, never refuse) · `test_prompt_quality.py` regression guard · 202 existing tests still green |
| P3-Grade-Tone | `fix/4071-grade-tone` | [#4071](https://github.com/theepangnani/emai-dev-03/issues/4071) | `app/prompts/grade_tone.py` — `get_tone_profile(grade_level)` 4 bands (K-3 / 4-6 / 7-9 / 10-12); `None` → 7-9 default · 5-key shape (voice, vocabulary, sentence_length, examples, directive) · 21 tests |
| P4-XP | `fix/4072-xp-per-question` | [#4072](https://github.com/theepangnani/emai-dev-03/issues/4072) | `XpService.award_cycle_question_xp` (100/70/40/0 per try) + `award_cycle_chunk_bonus` (50) · lifetime context-id dedup · registered `cycle_question_correct` + `cycle_chunk_bonus` action types with daily caps · streak multipliers apply · 17 tests |

**Next:** merge all 10 streams into `integrate/cb-tutor-002-phase-1` → integration /pr-review (2 passes per protocol) → single PR to master.

#### 6.142.2 Remaining work (queued, not yet started)

- **Phase 2 backend routes** — `POST /api/tutor/cycle/start`, `GET /api/tutor/cycle/:id`, `POST /api/tutor/cycle/:id/answer`, `POST /api/tutor/cycle/:id/complete` · state machine glue connecting Phase 2 model (#4067) + prompts (#4068) + XP (#4072)
- **Phase 2 frontend interaction layer** — wire the cycle shell (#4069) to the Phase 2 backend routes (replace mock data)
- **Phase 3 LLM regression harness extension** — beyond the 5 canonical prompts in #4064, expand to 20 per design doc
- **Phase 4 streaming expansion** — convert remaining LLM calls (slide generation, chunk prep) to SSE; add `BackgroundTasks` for file ingestion
- **Phase 4 observability** — `ttfi` (Time To First Insight) + `cycle_completion_rate` analytics events
- **Deployment ramp plan** — internal → paid beta → GA, gated on `tutor_chat_enabled` then `learning_cycle_enabled`

#### 6.142.4 Quick / Full / Worksheet modes + per-message PDF + chip-UX (Design-Gap remediation #4374)

Follow-on to §6.142.1. The user reported that `/tutor` Explain mode fell short of a claude.ai-class experience for cheat-sheet-style prompts (e.g. "give me a cheat sheet for grade 5 math"): the assistant produced a short reply with no way to expand it, no way to download it, suggestion chips were bare verbs ("Practice problems") that lost topic anchor when sent, and tapping a chip just populated the input — the parent still had to tap Send. Five parallel streams (#4375 / #4376 / #4377 / #4381 / #4382) close the gap.

##### Why this exists
- **No expansion path** — the `_TUTOR_SYSTEM` prompt + 800-token cap produced reasonable conversational answers but truncated genuine cheat-sheet / study-guide requests. Users had no opt-in to a longer, structured artifact.
- **No download** — there was no per-message way to capture a useful reply for offline use; only the conversation-level PDF utility from CB-ILE-001 existed and that targeted study guides, not chat turns.
- **Chip topic-anchor loss** — chips read like commands ("More examples", "Practice problems") relative to the previous reply, but when emitted as user messages they lost the topic the conversation was about. The model responded with generic content because the chip text was generic.
- **Chip click ergonomics** — tapping a chip populated the input but did not auto-send, requiring a second tap. Compounded with above, chips felt like a dead end.

##### Locked behaviour

| Decision | Value |
|---|---|
| Default reply mode | `quick` — current 800-token cap, current concise `_TUTOR_SYSTEM` prompt. **No behaviour change without opt-in.** |
| `full` mode trigger | User taps "Get the full version" button on a settled assistant reply |
| `full` mode budget | `max_tokens=3000` + structured-artifact prompt (Markdown headings, tables when comparing, fenced code for formulas/syntax, 1-2 worked examples per concept, short summary at end) |
| `worksheet` mode trigger | User taps a Practice / Problem / Exercise / Worksheet suggestion chip (keyword router) |
| `worksheet` mode budget | `max_tokens=3000` + numbered practice problems + clearly separated answer key section |
| Per-message PDF | "Download as PDF" button on every settled assistant reply; reuses existing `downloadAsPdf` utility from `frontend/src/utils/exportUtils.ts` (client-side, html2canvas + jsPDF; no new dep) |
| Suggestion chips | Self-contained, topic-anchored text (never bare verbs); chip click auto-sends in one tap |
| System prompt | Adds stay-on-topic directive for short follow-ups ("examples", "more", "another") so single-word follow-ups stay anchored to the prior turn's subject |

##### Streams

| Stream | Issue | Scope |
|---|---|---|
| A — Backend mode parameter | [#4375](https://github.com/theepangnani/emai-dev-03/issues/4375) | `mode: "quick" \| "full"` request field on chat endpoint; `full` switches prompt + raises `max_tokens` to 3000 |
| B — Frontend buttons | [#4376](https://github.com/theepangnani/emai-dev-03/issues/4376) | "Get the full version" + "Download as PDF" buttons on every settled assistant reply |
| C — Requirements | [#4377](https://github.com/theepangnani/emai-dev-03/issues/4377) | This section + REQUIREMENTS.md index entry |
| D — Chip UX + topic anchor | [#4381](https://github.com/theepangnani/emai-dev-03/issues/4381) | Chip click auto-sends; chip text is self-contained / topic-anchored; system prompt stay-on-topic directive for short follow-ups |
| E — Worksheet mode | [#4382](https://github.com/theepangnani/emai-dev-03/issues/4382) | `mode: "worksheet"` value (numbered problems + separated answer key); chip text matching `practice|problem|exercise|worksheet` keywords routes via this mode |

##### Cost / rate-limit notes
`full` and `worksheet` modes raise `max_tokens` from 800 to 3000 — roughly 3-4× the per-call OpenAI cost vs. `quick`. The existing per-user 20-req/hr Tutor rate limit (set in §6.142.1) is unchanged, so the **daily ceiling per user remains bounded** even if every request used the larger budget. No new metering needed; cost is observable through the existing AI usage rollups.

##### Out of scope (file separately if wanted)
- "PDF the whole conversation" multi-turn export (this PR does per-message only)
- Server-side typeset PDF (e.g. WeasyPrint / Puppeteer) — current path stays client-side
- Persistent worksheet library (saving worksheets to a kid's profile for re-take)
- Auto-grade student answers on a worksheet
- Server-side regeneration of an old reply at higher token budget (`full` only applies to fresh generations)

##### Cross-links
Parent: [#4374](https://github.com/theepangnani/emai-dev-03/issues/4374) · Streams: [#4375](https://github.com/theepangnani/emai-dev-03/issues/4375) [#4376](https://github.com/theepangnani/emai-dev-03/issues/4376) [#4377](https://github.com/theepangnani/emai-dev-03/issues/4377) [#4381](https://github.com/theepangnani/emai-dev-03/issues/4381) [#4382](https://github.com/theepangnani/emai-dev-03/issues/4382) · Integration branch: `integrate/cb-tutor-002-quickfull-pdf`


### 6.142 Unified Multi-Kid Email Digest V2 (CB-PEDI-002, #4012) — INTEGRATION READY (2026-04-23)

**Epic:** #4012 · **Design PR:** #4011 (`docs/design/email-digest-unified-v2.md`) · **Integration PR:** #4045 · **Feature flag:** `parent.unified_digest_v2` (off / on_5 / on_25 / on_50 / on_100; OFF by default)

#### Why this exists
The original Email Digest (CB-PEDI-001, §6.127) modeled one Gmail integration **per child**. A parent with two kids saw two separate management pages, two separate monitored-sender lists, and got two daily digests in their inbox. The defect surfaced at #4007 (clicking Email Digest from Haashini's card landed on Thanushan's page) was a routing bug fixed in PR #4010, but it exposed the deeper design gap: the data model could not express "this teacher emails both my kids."

CB-PEDI-002 redesigns the feature around the parent (not the integration), introduces school-email-based attribution via Gmail forwarding headers, and ships **one daily digest per parent** with per-kid sections.

#### Locked-in decisions (v1)
1. **One daily digest per parent** — all kids combined into a single email. Per-kid sections inside.
2. **"All kids" default** for newly added senders, with per-sender opt-out.
3. **School email is a first-class attribution key** — stored separately from the student's ClassBridge login email (`users.email`), in a new `parent_child_school_emails` table. Attribution **never** reads `users.email`.
4. **No email-based verification** for school emails — external email to school inboxes is blocked by board firewalls until DTAP approval lands. Replaced by:
5. **"Forwarding detected" indicator** — derived from the `forwarding_seen_at` timestamp stamped each time the worker matches a `Delivered-To:` header to a stored school email. UI shows three states (active <14d, may-have-stopped >14d, no messages yet).

#### Data model (4 new parent-level tables)
- `parent_child_profiles(id, parent_id, student_id?, first_name)` — one row per kid.
- `parent_child_school_emails(id, child_profile_id, email_address, forwarding_seen_at?)` — N per kid (parent can list multiple school addresses per child).
- `parent_digest_monitored_senders(id, parent_id, email_address, sender_name?, label?, applies_to_all)` — deduped on `(parent_id, email_address)`.
- `sender_child_assignments(id, sender_id, child_profile_id)` — many-to-many sender↔kid.

Idempotent backfill in `app/db/migrations.py` seeds these from existing `parent_gmail_integrations` + `parent_digest_monitored_emails` rows on first deploy.

#### Attribution algorithm (`app/services/unified_digest_attribution.py`)
For each ingested email:
1. Inspect `Delivered-To:` and `To:` headers (Gmail preserves the original recipient on forwarded mail).
2. Match against the parent's `parent_child_school_emails`. Exactly-one → attribute to that kid + stamp `forwarding_seen_at`. Multiple → attribute to all matched. None → step 3.
3. Fall back to `parent_digest_monitored_senders` lookup on the `From:` address. `applies_to_all=true` → "For both kids" section. Specific assignments → those kids' sections.
4. No tag, no header match → "Unattributed senders" footer.

#### New API endpoints (parent-scoped, all under `/api/parent/`)
- `GET /email-digest/monitored-senders` · `POST` (with `child_profile_ids: number[] | "all"`) · `DELETE /{id}` · `PATCH /{id}/assignments`
- `GET /child-profiles` · `POST /{id}/school-emails` · `DELETE /{id}/school-emails/{email_id}`
- Legacy `POST /email-digest/integrations/{id}/monitored-emails` still works and dual-writes to the new tables (one-release transition).

#### Frontend
- `EmailDigestPage.tsx` splits into `EmailDigestPageLegacy` (byte-for-byte preservation) and `EmailDigestPageUnified` (new layout). Gating: `useFeatureFlagEnabled('parent.unified_digest_v2')` AND no `?legacy=1` query param.
- Unified layout: header band (Gmail/delivery/WhatsApp) → "Your kids" rows with school-email management + forwarding badges → "Monitored senders" flat list with multi-kid chips + "Add sender" modal (multi-select with "All kids (incl. future)" default-checked).
- `EmailDigestSetupWizard.tsx` adds a flag-gated Step 5 that asks the parent for each kid's school email during initial setup.

#### Workflow & quality gates
- 6 parallel isolated-worktree streams (data model / API / worker attribution / frontend page / setup wizard / feature flag) → merged into `integrate/4012-unified-email-digest`.
- Conflict resolution in a dedicated worktree (`frontend/src/api/parentEmailDigest.ts` had overlapping additions from streams 4 and 5; resolved by unifying type names + correcting URL paths).
- 2 rounds of `/pr-review`: pass 1 surfaced 10 findings (3 CRITICAL + 7 IMPORTANT); 4 fix streams shipped + merged with zero conflicts; pass 2 verdict APPROVE with no new criticals.
- All 218+ tests pass on integration: 185 unified-digest backend tests + 33 legacy services tests + 34 frontend tests + `npm run build` clean + `npm run lint` 0 errors.

#### Rollout
- Flag stays OFF after merge. Internal testing first.
- Ramp via variant: on_5 → on_25 → on_50 → on_100.
- After one release with no regressions: drop legacy `ParentDigestMonitoredEmail` reads and retire dual-write.

#### Known follow-ups (not blocking)
- ~~**#4044** — Add `POST /api/parent/child-profiles` so the wizard can create profiles for brand-new parents (no pre-existing Gmail integration). Currently the wizard catches the 404 with a friendly error message; profiles for existing integrations were seeded by the Stream 1 backfill.~~ **Shipped via PR #4100 (2026-04-24).**
- ~~**#4056** — Decide whether to preserve "Send Digest Now" / "Sync Now" / "Digest History" features in the unified page (legacy parity question).~~ **Shipped via PR #4102 (2026-04-25)** — user confirmed regression and approved port. Faithful port of all 3 sections from `EmailDigestPageLegacy` to `EmailDigestPageUnified`: Sync Now button, Send Digest Now button + per-channel delivery status banner (delivered/partial/failed/skipped + Try again retry + Open preferences link), Digest History card with DOMPurify-sanitized HTML expansion. 2 parallel streams + 2 rounds of `/pr-review` (62/62 frontend tests pass).

#### Post-launch defect batch — PR #4100 (2026-04-24)

Two production defects reported the same day the epic shipped. Both fixed via integration PR #4100 (2 parallel streams + 2 rounds of `/pr-review`):

- **#4044 (closed)** — unified page now renders ALL of the parent's kids in "Your kids", not just kids with existing `ParentChildProfile` rows. Adding a school email to a kid without a profile auto-creates the profile via the new `POST /api/parent/child-profiles` endpoint (idempotent dedupe on `(parent_id, student_id)` or `(parent_id, LOWER(first_name))`; race-safe via `IntegrityError` re-fetch).
- **#4098 (closed)** — each school-email row now has a × remove button + confirm modal + dismissable error banner. Closes the gap where parents were stuck with misclassified entries (e.g., `no-reply@classroom.google.com`) seeded by the legacy setup wizard or Stream 1 backfill.

**Quality gates:** `npm run build` clean · `npm run lint` 0 errors · 46/46 frontend tests · 29/29 backend tests for the new POST endpoint · 2 rounds of `/pr-review` (pass 1: 0 Critical + 4 Important + 7 Suggestions, all addressed inline in commit `98642238`; pass 2: APPROVE, no new findings).

**Follow-up #4099** filed (deferred per Option A) for one-time data scrub of misclassified school-email rows; users can self-clean now that the × button ships.

#### Post-launch defect batch — 2026-04-27 (#4327, #4328, #4329; closes #4099)

Three production defects reported the same session, all rooted in the unified-v2 design surface. Fixed via **integration PR `<TBD>`** off `integrate/email-digest-defect-batch-2026-04-27` — three parallel isolated-worktree streams + 2 rounds of `/pr-review`:

- **#4327 (Design Gap)** — monitored-sender rows had only a × button, no Edit. Parents who picked the wrong kid had to delete and re-add (losing typed metadata). Fix: dual-mode `AddSenderModal` accepting `mode: 'add' | 'edit'` + `initialSender`; pre-fills name/label/all-kids/selected kid IDs; renders email input as `readOnly` with helper text since `email_address` is the dedupe key. Submit reuses existing `addMonitoredSender` (POST upsert by email) — zero backend change.
- **#4328 (Bug, closes #4099)** — deleted school-email rows kept reappearing on every Cloud Run cold start. The "idempotent" backfill at `app/db/migrations.py:2636-2655` used a `NOT EXISTS` guard that couldn't tell "never seeded" from "user deleted." Fix: new column `parent_gmail_integrations.unified_v2_backfilled_at` gates the backfill at the integration level (skipped once stamped); denylist regex `(no-?reply|donotreply|mailer-daemon)@` filters junk values at insert time AND drives a one-time data scrub of pre-existing junk rows. Stamp UPDATE intentionally skips denylisted integrations so a parent who later corrects the legacy `child_school_email` to a real value still gets backfilled on the next migration.
- **#4329 (Design Gap)** — Haashini's emails were attributed to Thanushan because Haashini's school email wasn't registered (school email is optional per kid by user clarification). Stage 2 sender-tag fallback over-confidently routed the email to whichever kid happens to share `no-reply@classroom.google.com`. Fix: refactored `attribute_email` into 4 stages — Stage 1 unchanged (registered school-email match), **NEW Stage 2 (parent_direct)** routes emails with no school-looking recipient to a "Sent directly to you" section above per-kid sections (skips sender-tag entirely; an email sent directly to the parent's Gmail can never have been *for* a kid), **Stage 3 sender-tag** runs only when an unregistered school-looking recipient exists and downgrades strict-subset sender matches to all-kids + a `sender_tag_ambiguous` source, Stage 4 unattributed unchanged. Plus an **auto-discovery loop**: `parent_discovered_school_emails` table records observed-but-unregistered school addresses; new GET/POST(assign)/DELETE endpoints let the parent assign each address to a kid in one click; UI banner above "Your kids" surfaces discoveries with `[Assign to a kid]` modal. School-looking heuristic: domain matches `gapps.`, `.edu`, `.k12.` AND local-part is not `no-reply`/`noreply`/`donotreply`/`mailer-daemon`/`postmaster`/`support`/`info`. Conservative — false positives over-attribute (visible everywhere) rather than under-attribute (hidden from the right kid).

**Quality gates:** `npm run build` clean · `npm run lint` 0 errors · 71/71 frontend tests · 266/267 backend digest tests (1 pre-existing test-ordering flake on `test_unified_digest_profiles_api.py::test_delete_email_on_other_parents_profile`, passes in isolation). Three streams merged with **zero conflicts** despite touching `EmailDigestPage.tsx`, `migrations.py`, and `parent_gmail_integration.py` from independent angles. Two rounds of `/pr-review` pending against the integration PR.

**Filed alongside (deferred):** **#4330** — multi-parent digest sync (Option B continuous-shared-with-override). Design doc `docs/design/multi-parent-digest-sync.md`; tracking PR #4331; status `design-review` only. Documented in §6.145.

#### Stream 5 — Unified WhatsApp delivery + flag promoted ON (PR for #4103, 2026-04-24)

The original v2 MVP (PR #4045) shipped with WhatsApp deferred to "Stream 5" — `send_unified_digest_for_parent()` only delivered in_app + email and the `whatsapp` channel was silently dropped. With the flag still OFF by default, multi-kid parents kept hitting the legacy per-integration path, which leaked the wrong child's name into subject + greeting (e.g. Rohini's Haashini digest titled "Email Digest for Thanushan").

**#4103 closes the gap with three coordinated changes:**

1. **`parent.unified_digest_v2` default → ON (`enabled=True, variant="on_100"`)**. `seed_features()` also auto-promotes any existing row still pinned to the original `enabled=False / variant="off"` default; admin overrides (variant other than `"off"`) are preserved untouched.
2. **WhatsApp wired into the unified path** with V2-then-V1-then-freeform fallback. Picks the first integration on the parent with `whatsapp_verified=True` and a phone number (parents share one number across all their integrations), generates a sectioned 3×3 digest across the merged emails (`generate_sectioned_digest(... "your kids" ...)`), then:
   - If `TWILIO_WHATSAPP_DIGEST_CONTENT_SID_V2` is set → 4-variable V2 sectioned template (one message per parent).
   - Else if `TWILIO_WHATSAPP_DIGEST_CONTENT_SID` is set → V1 single-variable template with `_sanitise_whatsapp_var` (`\n\n`→`•`, control-char strip, 1024 cap).
   - Else → freeform `send_whatsapp_message()` body with header/footer (sandbox / session-window only).
3. **WhatsApp added to the unified `outcomes` calculation + `whatsapp_delivery_status` persisted on the synthetic `DigestDeliveryLog`** keyed to `integrations[0]`. Three-valued per-channel convention (#3887) preserved: `True` / `False` / `None` where `None` (whatsapp selected but no integration verified) is excluded from overall-status.

**Effect:** Multi-kid parents now receive exactly ONE digest envelope across in_app + email + WhatsApp, with correct kid attribution everywhere (subject "Email Digest for your kids", per-kid sections inline). When Meta approves the V2 Twilio template (#3987), flipping the env var swaps the V1 `•`-flat formatting for properly sectioned multi-variable rendering — zero further code changes.

**Follow-up — manual "Send Now" endpoint dispatch (#4434):** PR #4104 (the legacy-path retirement that landed alongside this stream) flipped `send_unified_digest_for_parent()` to be the default for the scheduled job but missed the manual trigger at `POST /api/parent/email-digest/integrations/{integration_id}/send-digest`, which kept hard-coding the legacy per-integration path. #4434 closes the gap by routing the endpoint through the same `is_feature_enabled("parent.unified_digest_v2")` check the scheduler uses. Behavioral consequence: when V2 is ON, clicking "Send Now" on any single integration delivers ONE parent-wide digest covering all of that parent's integrations (matches V2's "one digest per parent" semantics — the integration_id in the URL becomes a triggering identity, not a scoping filter). The `create_tasks` query param remains a per-integration legacy concept from the #3929 task-sync pilot; the V2 branch ignores it and emits a warning log, defaults False, and will be removed before public launch per #3929.

**Follow-up — parent-scoped manual Send-Digest-Now route (#4483):** The unified Email Digest page (`/email-digest` with `parent.unified_digest_v2` ON) is parent-scoped — there is no single "active integration" to anchor the URL on. Calls were threading through the legacy per-integration route (`POST /integrations/{id}/send-digest`), which under #4434's flag-dispatch did the right thing but only because the URL `integration_id` had become a no-op identity. #4483 adds an explicit parent-scoped manual trigger: `POST /api/parent/email-digest/send-now` (no `integration_id`, optional `since_hours` query, default 24, capped 1–168). Behavior: V2-flag ON → calls `send_unified_digest_for_parent(parent_id, skip_dedup=True)` once; flag OFF → loops the parent's active integrations and calls `send_digest_for_integration(... create_tasks=False)` per integration, aggregating the result (`delivered` if all delivered, `partial` if some, `failed` if all failed, `skipped` for zero-integration parents). The unified frontend now calls this endpoint exclusively (`sendDigestNowForParent`); the legacy single-integration view still calls `sendDigestNow(integrationId)`. The per-integration route is preserved for back-compat. Rate-limit: 10/minute via `limiter.limit`, RBAC: parent-only (`require_role(UserRole.PARENT)`).

**Follow-up — default `digest_format` flipped from `"full"` to `"sectioned"` (#4484, #4485):** Two bugs collapsed into one model change. (1) `"full"` format AI prompt produced free-form HTML with no per-section item cap and "Quick Note" / Urgent rendered as the LAST section — meaning the most-important item appeared at the bottom of the email (#4485). (2) The 3-item cap + "And N more →" CTA was already implemented in `build_sectioned_digest_email_body` (`app/services/notification_service.py:319-395`) but only used when parents explicitly opted into sectioned format via the wizard — no parent had it on by default (#4484). #4484 changes `ParentDigestSettings.digest_format` model default from `"full"` to `"sectioned"`, plus a startup migration (PG-only, gated `if not sqlite`, `pg_try_advisory_lock(4484)` with 3×5s retry) that updates the column DEFAULT — existing rows keep their value (no backfill, preserves explicit/implicit parent choice). New integrations created post-deploy get sectioned: ≤3 items per section · Urgent first · "And N more →" CTA linking to `/email-digest`. #4485 closes for free since the sectioned path orders Urgent ahead of Announcements + Action Items.

**Follow-up — login redirect preserves intended deep-link path (#4486, #4538):** The "View in ClassBridge" CTA in digest emails dropped users on `/dashboard` after login instead of `/email-digest`. Two layers were silently dropping the intended path: `ProtectedRoute.tsx` redirected unauthenticated users to `/login` with no `state` payload, and `Login.tsx` hard-coded `navigate('/dashboard')` after both password and OAuth flows. #4486 wires `ProtectedRoute` to pass `state={{ from: location }}`; `Login` reads `state.from.pathname` first, falls back to `?redirect=` query param (covers fresh-tab opens where router state is lost), defaults to `/dashboard`. New `frontend/src/utils/sanitizeReturnPath.ts` rejects absolute URLs (`https://evil.com`), protocol-relative (`//evil.com`), embedded protocols (`/path?next=https://evil.com`), and — per #4538 (PR #4537 review pass-1) — auth-page paths (`/login`, `/register`, `/forgot-password`, `/waitlist`) which would otherwise produce an infinite redirect loop on the password-login flow because `?redirect=` survives in the URL across renders.

**Follow-up — V2 sectioned WhatsApp variable sanitization + actual V2→V1→freeform fallback chain (#4502, #4505):** Two compounding bugs in the V2 WhatsApp send path surfaced in production once #4434 routed Send-Now through V2: (1) `_sectioned_section_block` produced `\n`-joined bullets, but **Twilio's Content API rejects `\n` in template variables** (HTTP 400 "The Content Variables parameter is invalid" — same failure mode #3941 fixed for V1; V2 never got the same treatment); (2) PR #4104's commit message claimed a V2→V1→freeform fallback chain but the code shipped as mutually-exclusive `elif` branches keyed on which SID was configured, so a V2 failure never attempted V1. #4502 fixes both: a new `_sanitise_whatsapp_section_block` helper (`app/jobs/parent_email_digest_job.py:146-178`, mirrors `_sanitise_whatsapp_var` but omits the V1 `\n{2,}` → ` • ` substitution since V2 blocks already have `- ` markers) sanitizes each variable at the V2 send boundary; both the legacy per-integration path (lines 519+) and unified `send_unified_digest_for_parent` (lines 1275+) now implement actual try-then-fallback with each layer wrapped in `try/except` so a Twilio raise doesn't break the chain. Transitions logged at WARNING (was INFO) so ops dashboards catch systemic V2/V1 failures rather than masking silent fallback. #4505 folds in 4 polish suggestions from /pr-review pass 1: lazy `flattened` computation in legacy path, defensive HTML scrub in `_sanitise_whatsapp_section_block` (per #4006 pattern), unified WARNING-level logging policy, and DRY refactor of the duplicate `legacy_blob` branching in unified V1+freeform paths. **Twilio Content API contract is now locked across both helpers:** any future Content API integration in this codebase MUST sanitize at the send boundary — newline-free, control-char-free (ASCII 0-31 stripped), within the 1024-char per-variable cap, and HTML-tag-scrubbed defensively.

**Follow-up — conftest reset for `parent.unified_digest_v2` flag pollution (#4542):** PR #4448 added a `_set_unified_v2_flag(db, False)` helper in `tests/test_digest_task_sync_wiring.py` and called it in 4 legacy-pilot tests to pin them to the legacy path. The helper only flips `flag.enabled = False` — it doesn't reset `flag.variant`. After one polluting test runs, the row is `(enabled=False, variant="on_100")`. The auto-promote-back-to-default logic in `app/services/feature_seed_service.py:159-182` only fires when BOTH `variant=="off"` AND `enabled is False` — neither holds for the polluted state, so the seed function leaves it as-is, and the next test that asserts the seeded-ON contract (`test_feature_flags::test_unified_digest_v2_flag_seeded_default_on`) fails. The conftest `_isolate_task_sync_flag` autouse fixture intentionally excluded `parent.unified_digest_v2` with the comment "Default-ON flags are excluded — the leak direction is harmless." That was correct before #4448 introduced the OFF-toggling helper. Now the leak direction (ON → OFF) is harmful. #4542 extends the fixture with a `default_on_keys` tuple covering `parent.unified_digest_v2`; resets to `(enabled=True, variant="on_100")` between tests so the seeded-default contract holds regardless of pytest collection order. **Why it didn't surface earlier:** PR #4448's local full-suite run passed because pytest's collection order on that machine put seeded-default tests *before* the polluting tests; #4448's prod deploy used the default `deploy-only` profile (skips the test job); today's `full`-profile gate was the first time CI's test ordering hit the bad sequence in a deploy gate. Pattern lesson: any default-ON flag toggled OFF by a test must be reset to `(enabled=True, variant=<canonical>)` together — partial drift survives the seed auto-promote.


#### 6.142.3 Phase 1 round-3 + pass-4 review (2026-04-24 evening)

Follow-on to §6.142.1. After 10 feature streams merged, `/pr-review` was run against integration PR #4077:

| Pass | Result |
|---|---|
| Pass 1 (pre-conflict-resolution) | 0 Critical + 8 Important + 5 Suggestion |
| Pass 2 (after 4 round-1 fix streams) | APPROVE — 0 C / 0 I + 5 cosmetic |
| **Pass 3 (fresh independent review)** | 0 Critical + **7 Important** + 7 Suggestion |
| **Pass 4 (after 5 round-3 fix streams)** | **APPROVE — 0 C / 0 I + 4 cosmetic** |

**Pass-3 findings fixed in round-3** (#4083-#4087):
- #4083 **Route hardening** (tutor.py — I-1 unknown conv_id→404 · I-2 flag-before-limit · I-4 15s inter-token stall timeout · I-5 stable history order · S-1 lru_cache)
- #4084 **Moderation fail-CLOSED** (safety_service — new `moderation_fail_mode` setting, distinct `moderation_unavailable` SSE frame code; critical for K-12 when OpenAI moderation is down)
- #4085 **Explicit learning_cycle CREATE TABLE migration** (main.py — pg_try_advisory_lock(4067) pattern parallel to the existing tutor-table block)
- #4086 **TutorChat a11y** (aria-live on message bubble not container; streaming uses instant-scroll behavior; `streamDone` flag guards against token-after-done races in useTutorChat)
- #4087 **Suggestions cleanup** (XP `int(attempt_number)` coercion; LearningCyclePage MOCK_SESSION wrapped in `import.meta.env.DEV`; `test_tutor_routes.py` 515-line file split into `_auth` / `_streaming` / `_moderation` + shared `tutor_helpers.py`)

**Total Phase 1 workflow footprint:**
- **19 issues closed** across 4 review rounds (10 feature: #4063-#4072, 4 round-1: #4078-#4081, 5 round-3: #4083-#4087)
- **14 parallel isolated-worktree streams**
- **170 backend + 59 frontend tests** passing
- **4 `/pr-review` passes** · **2 APPROVE verdicts** (pass 2 and pass 4)
- Integration branch: `integrate/cb-tutor-002-phase-1` (final HEAD `35d2eae3`)
- Single PR to master: #4077

### 6.143 CB-DCI-001 Daily Check-In Ritual (V1 Pain #4) — M0 SHIPPED 2026-04-25 (flag ON, deploy pending)

**Epic:** #4135 · **Design lock:** `docs/design/CB-DCI-001-daily-checkin.md` · **Source PRD:** `CB_DCI_001_PRD_v2.docx` · **Target ship:** Sept 2026 · **M0 ships:** web only · **Master commits:** `78d11091` (design) + `601935b8` (M0) + `22b6f627` (M0-12+M0-13 entry tile + consent routing) + `<this-PR>` (fast-follow batch) · **Live revision:** `classbridge-01142-l58` (M0 only — re-deploy needed for M0-12/M0-13/fast-follow)

**Strategic framing.** DCI is V1 Pain #4 — *the retention engine of the $19/mo AI tier*. It is NOT the primary content-ingestion mechanism (Gmail forwarding + Classroom OAuth cover ~85 %); DCI's job is to fill the last 10 % gap (paper handouts, kid-narrated context) AND to create a 60-second kid-initiated / 4-minute parent-consumed daily loop that converts a Contextual-stage parent into an 8-year Continuous-stage family. Together with CB-ILE-001 study guides (the conversion lever), DCI forms the core economic loop of the AI tier.

**Personas.** Priya (primary buyer · dual-earner Markham parent · 4 min review + 5 min talk per evening) · Haashini-like kid (Grade 5-8 · 60 sec/day) · older sibling (Grade 9+ · 30-60 sec/day) · second parent (3 min × 2/wk async).

**M0 scope (SHIPPED to master):**

- [x] M0-1 (#4136) Design lock — `docs/design/CB-DCI-001-daily-checkin.md` + this section
- [x] M0-2 (#4140) Data model — 6 new tables + ALTER TABLE migrations + advisory lock
- [x] M0-3 (#4141) Feature flag `dci_v1_enabled` (default OFF — flipped ON manually 2026-04-26)
- [x] M0-4 (#4139) `POST /api/dci/checkin` — multipart, sync GPT-4o-mini classify chip ≤ 2 s, async summary job
- [x] M0-5 (#4142) Whisper transcription + Haiku 4.5 sentiment scoring
- [x] M0-6 (#4143) Sonnet 4.6 summary + conversation starter generator (prompt-cached, ≤ $0.04/family/day)
- [x] M0-7 (#4144) Content-policy v0 (counsel review still required before further flag escalation per § 11)
- [x] M0-8 (#4145) Check-in streak — separate stream from study streak; school-day-aware; never guilts
- [x] M0-9 (#4146) Kid web flow `/checkin` — 3 screens
- [x] M0-10 (#4147) Parent evening summary `/parent/today`
- [x] M0-11 (#4148) Consent flow + Bill 194 disclosure + DCI settings section
- [x] M0-12 (#4258) Parent dashboard entry tile — flag-gated `DciEntryCard` linking to `/parent/today` + `/checkin` (PR #4263)
- [x] M0-13 (#4260) `ConsentScreen` route + redirect from `/checkin` and `/parent/today` when consent missing (PR #4265)
- [x] M0 fast-follow batch (PRs #4272 #4273 #4274 #4281): Login test flake fix · DciEntryCard a11y polish · Kid `/checkin/needs-consent` friendly bounce · `useDciConsent` 4xx-no-retry · `useDciSummary` consent-gated · ConsentScreen 600 ms post-save flash · `coerce_subject` helper · drop legacy `DCI_COST_*` constants · suppress SAWarning

**Fast-follow scope (post-M0, tracked in #4149):** Expo mobile (kid + parent · push · camera · voice) · Cross-reference DCI ↔ Gmail/Classroom · Day-7 parent nudge job (invitation-framed, school-day-aware, mute toggle, re-arms after resume) · Lifecycle/purge cron · DCI → CB-TASKSYNC auto-task creation · DCI → CB-ILE-001 study-guide upsell · Content-policy red team + external counsel review · Pattern view (V2 prep) · Telemetry dashboard · DCI → Smart Briefing integration · Priya interviews + PRD §14 Q4-Q6 validation · Q9 missed-7-days UX formalization.

**Success metrics (V1 targets).** 70 %+ kid check-in completion on school days · ≤ 75 s median kid time-on-task (target 60 s) · 60 %+ parent review rate · 30 %+ "I used the conversation starter" feedback · 20-30 % Contextual → Continuous conversion in 90 days · 70 %+ 30-d retention · 50 %+ 90-d retention · NPS 50+ · cost ≤ $0.04/family/day.

**Non-goals (V1).** Not the primary ingestion path · no teacher/admin role · no multi-week pattern view (stub only in V1) · no grading · no kid-to-kid social · **no homework-answering chatbot for kids** (principle-level constraint, not just scope).

**Key resolved decisions (full table in design lock §13).** Sonnet 4.6 + prompt cache for summary (Opus 4.7 reserved as one-flag fallback) · separate `checkin_streak_summary` table (reusing `StreakLog` writes via existing `action_type`) · Day-7 parent nudge invitation-framed + mute toggle (P1 honored without violating P2) · streak monetization NONE (resolves PRD §14 Q8) · content-policy v0 = regex + keyword, fail-closed (ML classifier in fast-follow) · slot in §6.143 (note: §6.142 is duplicated between CB-TUTOR-002 and CB-PEDI-002 — fast-follow renumbering issue).

**Operational state (as of 2026-04-26).** Master HEAD includes M0 + M0-12 + M0-13 + fast-follow batch. Live Cloud Run revision `classbridge-01142-l58` only contains M0 (M0-12/M0-13/fast-follow not yet deployed — separate explicit deploy approval required per global rule). Flag `dci_v1_enabled` is ON in prod; users can already navigate to `/parent/today` via direct URL or via Settings → DCI section. After re-deploy, parents will see `DciEntryCard` on their dashboard and the consent-redirect flow will kick in automatically. Bill 194 audit-logging silent-fail bug fixed in `audit_service.log_action` lazy-import (commit `8b4bce33`, see #4249 + `feedback_lazy_model_imports_in_services.md`). Bill 194 ramp gate `#4192` (production migration for `checkin_settings`) and counsel review of `dci_content_policy.py` keyword tables remain required before further flag escalation.


### 6.144 App-Wide Visual Unification — "Bridge" Theme as Default (CB-THEME-001) — SHIPPED 2026-04-26 + 27

**Epic:** #4155 · **V1 PR:** #4242 (squash `709c8712`) · **Phase 2 PR:** #4300 (squash `605eca48`) · **Feature flag:** `theme.bridge_default` (off by default; ramp `internal_only → staff → on_for_all`)

#### Why this exists
The Parent Hub / Bridge re-skin (CB-BRIDGE-001) introduced a distinctive warmer visual language (ivory surfaces, warm-charcoal ink, rust/pine/amber/sky/rose accents, Fraunces serif headings + DM Sans body) that needed to apply app-wide across every role so the product feels like one product. Pre-shipped, the app used three coexisting palettes (`light`, `dark`, `focus`) plus the page-scoped `[data-landing="v2"]` for marketing.

#### V1 (#4242) — Foundation + 7 streams + a11y audit (8 streams total, 119 files, +2280/-1636)
| Stream | Scope |
|---|---|
| S0 #4156 | Foundation: `[data-theme="bridge"]` token block in `index.css` mapping bridge palette to existing `--color-*` token names + new bridge tokens (`--color-rust`, `--color-pine`, `--color-amber`, `--font-display-serif`, `--font-mono`, `--radius-bridge-*`); `bridge` registered in `ThemeContext` THEMES alongside `light/dark/focus`; force-apply via `BridgeDefaultApplier` when `theme.bridge_default` flag resolves on; FOIT global preload for Fraunces / DM Sans / JetBrains Mono in `index.html`; `frontend/src/THEME.md` documenting the system |
| S1 #4157 | Parent surfaces token-driven reskin (17 files, symmetric +704/-703). Caught + fixed latent ghost-token bug (parent CSS used undefined tokens with hex fallbacks — bridge wasn't applying at all before this) |
| S2 #4158 | Student surfaces token-driven reskin (17 files, symmetric +328/-328). Same ghost-token forensic finding fixed for student/ASGF surfaces |
| S3 #4159 | Teacher surfaces token-driven reskin (6 files) |
| S4 #4160 | Admin surfaces token-driven reskin (6 files, -150 net from removing redundant `[data-theme="dark"]` blocks now handled by semantic tokens) |
| S5 #4161 | **HIGH-risk** shared shell + chrome (DashboardLayout sidebar, Dashboard.css modals, FABs). Dark-pill sidebar active state matches prototype; theme-aware via tokens |
| S6 #4162 | Hardcoded color sweep (68 files, 190 literals replaced; 4 follow-ups filed for the remaining 1,045 literals) |
| S8 #4164 | WCAG 2.1 AA contrast audit. `--color-danger` + `--priority-high` darkened from `#c25b6f` to `#a84458` (4.18 → 5.78 on white) |

S7 (mobile parity) is fast-follow — separate Phase 2 mobile repo.

#### Phase 2 (#4300) — 7 post-GA followups consolidated
| Issue | Fix |
|---|---|
| #4213 | FOWT cache — synchronous bridge force-apply via localStorage cache (eliminates 100-500ms flash on cold-load for users in rollout cohort) |
| #4224 | Add `--color-border-strong` for WCAG 1.4.11 affordance UI (form inputs, button outlines, focusable cards) |
| #4226 | Per-theme recharts palette tokens for AdminSurveyPage (`--chart-series-1` through `--chart-series-6` per theme; resolved at runtime via `getComputedStyle` keyed on active theme) |
| #4235 | Tailwind palette tokens (`--tw-{gray,red,green,blue,yellow}-*` per theme; 38 files swept) |
| #4236 | Standalone shadow-rgba sweep → `--shadow-*` tokens (27 files) |
| #4237 | Inline TSX `style={{ color: '#hex' }}` → `var(--color-*)` migration (5 TSX files) |
| #4238 | Translucent surface tokens `--color-surface-translucent-{low,mid,high}` per theme (16 files; dark/focus use non-white base) |

Phase 2 also bumped jsdom 28 → 29.0.2 (#4290) which removed both unhandled-rejection suppression layers added in V1 once jsdom upstream patched the undici v7 incompatibility (#4257). Plus 6 CI test fixes (#4286) consolidating Login selector update, xdist parent-email collision fix, task-sync `is_feature_enabled` cross-session DB read race monkeypatching, and `retry: 2` flake mitigation.

#### Locked decisions (per planning Q&A)
1. Theme key: `bridge`
2. Force-apply default when flag on (overrides saved localStorage choice)
3. Keep all 4 themes (`light`, `dark`, `focus`, `bridge`) — focus NOT retired
4. Admin pages also unified (no per-role exemption)
5. Mobile (S7) is fast-follow — NOT in initial parallel batch
6. Font loading: FOIT global preload in `index.html`

#### Workflow footprint
- Foundation + 7 parallel streams + A11y stream (V1) → integrate/cb-theme-001 → master
- 7 parallel followup streams + 1 dedicated merge stream + 1 master-rebase stream (Phase 2) → integrate/cb-theme-phase2 → master
- 2× `/pr-review` per stream PR + 2× `/pr-review` on each integration branch before master ask
- 17 issues closed via V1, 7 closed via Phase 2, 6 follow-ups still tracked (#4213 done in Phase 2, others post-GA)
- Multiple master-rebases handled CB-DCI-001 M0, M0-12+13, and HF2 commits that landed during the work

#### Out of scope (still pending)
- S7 mobile parity in Phase 2 mobile repo (`ClassBridgeMobile/`)
- S9 rollout ramp (`theme.bridge_default` flag flips: `internal_only → staff → on_for_all` over ≥2 weeks)
- Renaming `light` theme to `bridge` (deferred until rollout completes)
- Retiring `focus` theme (intentionally kept per locked decision #3)

#### Acceptance status
- [x] Token system shipped to master (V1)
- [x] WCAG 2.1 AA pass on bridge palette critical text-on-surface combos
- [x] All shared chrome + role surfaces token-aware
- [x] Phase 2 follow-ups shipped (FOWT, border-strong, chart palette, Tailwind, shadows, inline TSX, translucent)
- [ ] S9 rollout ramp (pending S9 stream + deploy approval)
- [ ] Mobile parity (post-S9, separate repo)


### 6.145 Avatar colors — per-user Arc variant + kid CHILD_COLORS reorder (CB-AVATAR-COLORS-001) — SHIPPED 2026-04-27

**Epic:** #4311 · **Streams:** A #4312 (Arc per-user variant) · B #4313 (kid color reorder) · C #4318 (test mock fix) · **Integration branch:** `integrate/cb-avatar-colors` · **Status:** Pending master merge approval

#### Why this exists
After CB-THEME-001 shipped (#4242, #4300), Arc the mascot rendered rust/brown in bridge mode because its body gradient referenced `--color-accent` (which the bridge palette overrides to rust). User feedback: "anything but brown — random based on user persona." Separately, the first-added kid hero avatar (Thanushan) defaulted to violet (`#8b5cf6`); user wanted warmer default tones.

#### Locked decisions
1. **Arc randomness** — per-user deterministic hash (option (i) — like Slack avatars; persists across sessions; no backend storage)
2. **Arc palette** — 6 curated tokens: `--color-rose` (pink), `--color-sky` (blue), `--color-pine` (green), `--color-purple` (violet), `--color-amber` (gold), and new `--color-teal` (added per theme)
3. **Arc click target** — N/A (Arc is decorative-only on the tutor surfaces; no click-to-customize for now)
4. **Kid avatars** — option (α): reorder `CHILD_COLORS` array (rose first, violet to index 4). Per-kid override deferred to the future PR that ships `KidPhotoMenu` DELETE UI.
5. **Theme awareness** — Arc variant blocks use explicit hex (NOT `--color-rose` etc.) so each user's Arc color is stable across light/dark/focus/bridge theme switches. Identity > theme adjustment.

#### Implementation summary
- **`frontend/src/index.css`** — added `--color-teal` to all 4 themes; default `--arc-body-color*` tokens bind to `--color-accent*`; 6 `[data-arc="<key>"]` variant blocks override per user
- **`frontend/src/components/arc/util.ts`** (new) — `getArcVariant(userId)` returns one of `ARC_VARIANTS` via `Math.abs(id) % 6`; defaults to `'rose'` for unauthenticated
- **`frontend/src/components/arc/util.test.ts`** (new) — 4 vitest cases (deterministic, distribution, null/undefined, negative)
- **`frontend/src/components/arc/ArcMascot.tsx`** — 3 SVG gradient stop swaps with 3-level fallback `var(--arc-body-color, var(--color-accent, #hex))`
- **6 caller wrappings** — TutorPage, HelpChatbot, FlashTutorSessionPage, CycleResults, CycleTeachBlock, TutorChat each pull `useAuth().user.id` and apply `data-arc={getArcVariant(...)}` to the ArcMascot's container
- **`frontend/src/pages/MyKidsPage.tsx`** — `CHILD_COLORS` reordered: rose `#ec4899` first; violet `#8b5cf6` to index 4
- **Test mock fix (Stream C #4318)** — `vi.mock('AuthContext', ...)` added to `TutorChat.test.tsx` and `LearningCyclePage.test.tsx` since their components now call `useAuth()` via the data-arc wrapper

#### Out of scope (deferred)
- Per-kid color override (parent picks color via UI) — bundles with the future `KidPhotoMenu` DELETE UI followup
- Mobile parity in Phase 2 mobile repo
- Other themes' Arc tinting — variants stay color-stable across themes by design
- Backfill of §6.144 spec for CB-THEME-001 (the V1 + Phase 2 work that shipped earlier in this session) — separate documentation issue

#### Acceptance
- [x] Arc not brown for any user in bridge mode (rust accent decoupled from arc body)
- [x] Same user → same Arc color across reloads (deterministic via Math.abs(id) % 6)
- [x] Different users → good distribution across 6 variants (verified by vitest)
- [x] Kid hero default leads with rose; violet preserved at index 4
- [x] CI green (frontend ✓ 3m37s · backend ✓ 4m1s on rebased branch `7266769f`)
- [x] No new behavior, copy, prop, schema, or backend changes
- [ ] Master-merge approval (pending user)

#### Workflow footprint
- 3 parallel isolated worktrees (Stream A 150 lines, Stream B 5 lines, Stream C test mock fix)
- 1 dedicated merge stream (combined into integration branch with 0 conflicts)
- 1 master-rebase stream (incorporated CB-DCI-001 fast-follow batch 2 from master, 0 conflicts)
- 2× CI verification (initial + post-rebase)
- 1× `/pr-review` pass (APPROVE — 0 Critical, 0 Important, 3 Suggestions)

### 6.146 Kid profile photo upload — click hero avatar to replace initial (CB-KIDPHOTO-001) — SHIPPED 2026-04-26

**Issue:** #4301 · **PR:** #4309 (squash `a54c2e3d`) · **Status:** SHIPPED to master, deploy pending separate approval

#### Why this exists
After CB-BRIDGE-001 + CB-THEME-001 shipped, parents asked for the ability to upload a profile photo for each linked child instead of the auto-generated initial-on-colored-circle avatar. Photo replaces the initial in the My Hub bridge view; small filter pill also displays the photo (non-clickable).

#### Locked decisions (per /defect Q&A)
1. **Click target:** hero avatar ONLY (NOT the small filter pill — too small / awkward)
2. **Visual style:** match bridge token system from CB-THEME-001
3. **Storage:** GCS bucket per existing CB pattern; falls back to `local://` placeholder when `settings.use_gcs=false` (dev/test round-trip without real bucket)
4. **Validation:** jpg/png/webp only, ≤5MB, magic-byte check, EXIF stripped
5. **Image processing:** Pillow resize to max 512×512, re-encoded as JPEG quality=85
6. **Affordances:** hover camera-icon overlay, loading spinner during upload, error toast on failure
7. **Audit log:** parent_uploaded_kid_photo + parent_deleted_kid_photo entries record only student_id + boolean; never log image bytes or PII (MFIPPA)

#### Backend
- New column: `students.profile_photo_url VARCHAR(512) NULL` — idempotent migration with advisory lock 4301 (PG + SQLite paths)
- POST `/api/parent/children/{id}/photo` — RBAC parent-of-student via parent_students join, multipart upload, rate-limited 10/min
- DELETE `/api/parent/children/{id}/photo` — RBAC same, deletes from GCS best-effort, rate-limited 20/min
- New service `app/services/kid_photo_service.py` (validate / process / upload / delete)
- Best-effort previous-photo cleanup AFTER commit so delete failure cannot block upload
- 9 backend tests cover happy paths + every 422/403 branch

#### Frontend
- Type: `profile_photo_url?: string | null` on `ChildSummary`
- `KidHero.tsx`: clickable avatar button, hidden file input, TanStack `useMutation`, hover camera overlay, loading spinner, error toast, optimistic UI update
- `KidRail.tsx`: small avatar shows photo if present (NOT clickable per locked design)
- New `frontend/src/api/kidPhoto.ts` (upload + delete axios wrappers)
- Bridge token-only styling — no new design tokens introduced
- Light vitest coverage on KidHero

#### Out of scope (deferred follow-ups)
- `KidPhotoMenu` kebab (upload + remove dropdown UI) — base UX of "click avatar to replace" covers upload; explicit removal needs separate PR
- Mobile parity in Phase 2 mobile repo
- Per-kid color override UI — bundled with future KidPhotoMenu

#### Known follow-ups (non-blocking)
- Silent GCS-failure fallback in production — currently writes a `local://` placeholder URL when bucket is transiently unavailable + warns; should instead 503 the request so user can retry. Surfaced in /pr-review of #4309 as IMPORTANT-tier; not yet filed as standalone issue.
- Optimistic URL never clears on `child.profile_photo_url` source-of-truth change — minor edge case noted in /pr-review.

#### Acceptance status
- [x] ALTER TABLE migration runs idempotently
- [x] Upload + delete endpoints work, RBAC-gated, audit-logged
- [x] Image validation + EXIF strip + resize work
- [x] Frontend hero-click upload works; photo displays in hero + filter pill
- [x] Bridge styling matches CB-THEME-001 conventions
- [x] CI green (frontend ✓ 3m46s · backend ✓ 3m55s on PR #4309)
- [ ] Deploy to Cloud Run (separate explicit approval required)

### 6.147 Auto-create Tasks from due-date signals — CB-TASKSYNC-001 MVP-1 — SHIPPED 2026-04-23

**Issue/PR:** #3912 + PR #3946 · **Master commit:** `8335ec42` · **Feature flag:** `task_sync_enabled` (default OFF)

#### Why this exists
Parents and students were manually re-creating tasks from assignment due-date signals (Google Classroom syncs, manually-uploaded materials). MVP-1 closes the gap by letting a background job auto-create Task rows from any assignment that has a due-date in a configurable window — no UI changes, just signal → row.

#### Locked decisions (per design docs / PR review history)
1. **Feature gated** — `task_sync_enabled` flag (default OFF) so dev/test can isolate behavior; ramp via the standard flag ladder (`off → internal_only → staff → on_for_all`)
2. **Signal source** — assignments with `due_date` set in a forward-looking window (size: confirm from code)
3. **No auto-creation for past-due** — out-of-window assignments yield 0 Tasks (verified by `tests/test_task_sync_jobs.py`)
4. **Idempotent** — re-runs don't duplicate (deduped on `(student_id, assignment_id, due_date)` or similar — confirm)
5. **Hooks on submit/delete** — `assignments.py` POST submit triggers `handle_assignment_submitted` (auto-completes linked Task); DELETE triggers `handle_assignment_deleted` (soft-cancels linked Task). Both gated on the same flag.

#### Implementation
- `app/services/task_sync_service.py` — service layer for sync_all_upcoming_assignments + handlers
- `app/jobs/task_sync_job.py` — APScheduler job wrapping the service
- `app/api/routes/assignments.py` — POST submit / DELETE delete hooks (gated on flag via `is_feature_enabled("task_sync_enabled")`)
- Test coverage: `tests/test_task_sync_jobs.py` (full job + flag-OFF skip + service exception graceful) and `tests/test_assignments_routes.py` (4 hook tests for the auto-completion + soft-cancel paths)

#### Out of scope (MVP-1)
- Frontend UI for auto-created tasks (rendered identically to manual tasks via existing TasksPage)
- Per-student opt-out
- Sync from external calendar (Google Calendar, etc.)
- MVP-2+ — flag ramp + telemetry + post-rollout follow-ups

#### Acceptance status
- [x] Backend service + job shipped
- [x] Submit/delete hooks gated + tested
- [x] Feature flag registered, default OFF
- [ ] MVP-2: flag ramp + telemetry (post-deploy work)

### 6.148 Re-skin My Kids → Bridge — CB-BRIDGE-001 — SHIPPED 2026-04-25

**Issue/PR:** PR #4123 (squash `cdb1d617`) plus follow-ups: PR #4131 CB-BRIDGE-HF (`e2aface2`) + PR #4169 CB-BRIDGE-HF2 (`5bf09a66`) · **Status:** SHIPPED to master + deployed

#### Why this exists
The original "My Kids" page was a heavy 2,200+ line MyKidsPage.tsx with mixed-density panels and inconsistent visual treatment. Parent-research surfaced low engagement on this page. CB-BRIDGE-001 introduced a new visual language (warm ivory surfaces, rust accent, Fraunces serif headings, dark-pill primary buttons) modeled on a designer's prototype — and decomposed the page into 7 reusable components under `frontend/src/components/bridge/`. The re-skin is the design-foundation layer that CB-THEME-001 (§6.144) later promoted to app-wide.

#### Locked decisions
1. **6-stripe integration** — the PR landed as 6 sequential code stripes for review-friendly atomicity
2. **New components under `frontend/src/components/bridge/`** — BridgeHeader, KidRail, KidHero, KidActionsMenu, ListCard, EmailDigestCard, QuickToolsCard, plus shared `fonts.ts` and `util.ts` helpers
3. **MyKidsPage retains as host** — wraps the new bridge components; no route change
4. **Per-kid color via `CHILD_COLORS` deterministic index** — later refined by CB-AVATAR-COLORS-001 (§6.145)
5. **Initial avatar character via `getInitial(name)` util** — later replaced by photo upload via CB-KIDPHOTO-001 (§6.146)

#### Follow-ups shipped same wave
- **CB-BRIDGE-HF (PR #4131)** — Post-deploy hotfixes: Parent Hub rename, restore lost affordances (per-chip detail, all-kids materials, Dinner Table Talk, GoogleClassroomPrompt, Quick Tools strip, Email Digest navigation)
- **CB-BRIDGE-HF2 (PR #4169)** — Rename Parent Hub → My Hub (#4151), Daily Digest card replaces Best Study Times in all-kids view (#4152), Classes ↔ Class Materials grid swap (#4154)

#### Out of scope (deferred / picked up by other epics)
- App-wide visual unification (rust accent, Fraunces headings everywhere) — done by CB-THEME-001 (§6.144)
- Kid profile photo upload — done by CB-KIDPHOTO-001 (§6.146)
- Per-user Arc mascot color, kid hero avatar palette tuning — done by CB-AVATAR-COLORS-001 (§6.145)

#### Acceptance status
- [x] Bridge components shipped + integrated into MyKidsPage
- [x] HF + HF2 hotfixes shipped
- [x] Deployed (Cloud Run live revision includes the bridge re-skin)
- [x] Foundation for §6.144/§6.145/§6.146 follow-on work
- [ ] Bridge component unit tests (#4124 — still open follow-up, non-blocking)

### 6.149 Multi-Parent Email Digest Sync (CB-PEDI-MULTIPARENT, #4330) — DESIGN-REVIEW (deferred)

**Tracking issue:** #4330 · **Design doc:** `docs/design/multi-parent-digest-sync.md` · **Status:** design-review (not approved for build) · **Filed:** 2026-04-27

#### Why this exists
The CB-PEDI-002 (§6.142) schema is fully parent-scoped — each parent has their own `parent_child_profiles`, `parent_child_school_emails`, `parent_digest_monitored_senders`. But `parent_students` is many-to-many: a student can have multiple linked guardians. So when Parent A configures a kid, Parent B logging in for the same student sees a blank slate and has to redo it from scratch; subsequent edits never propagate either way. Live evidence (2026-04-27 defect): "Theepan" (parent A) had Thanushan + Haashini configured; "Idigital Spider" (parent B) saw both with "No school email configured yet."

User intent (verbatim): *"Your kids and monitor senders should be synched by default across the parents. Second parent shouldn't need to configure again. However, they choose to do it if they like."*

#### Approach (Option B: continuous shared-by-default with per-parent override)
Two scopings were considered with the user; **Option B was chosen** over the simpler one-shot bootstrap (Option A) because continuous sync matches the household mental model — one-shot bootstrap creates silent divergence after day 1.

- **Shared layer (student-scoped):** new tables `student_school_emails`, `student_monitored_senders`, `student_sender_assignments`. Senders keyed by `owner_set_signature` (sha256 of sorted parent_ids in the guardian set) so unrelated households never collide.
- **Override layer (per-parent):** new table `parent_digest_overrides(parent_id, scope, target_id, action)` with `action ∈ {hide, replace}`. The legacy `parent_*` tables continue as the private layer for `replace` overrides.
- **Effective view:** `shared ∪ private − HIDE overrides`, computed per-request.
- **Default writes** mutate shared rows (visible to all guardians); per-row "Make private" creates HIDE+private; wholesale "Use my own list" toggle covers estranged-co-parent opt-out.
- **Audit log** records every shared-row mutation for visibility and dispute backstop.

#### Backfill from existing parent-scoped data
Non-destructive: pick the earliest-configured parent as donor → seed shared rows from their data → non-donor divergence preserved as `replace` overrides. Single-parent students unaffected.

#### Privacy & access control
- Sharing is bounded by `parent_students` membership.
- Counsel review **required** before `on_for_all` ramp — sharing parent-inbox-derived metadata across guardians changes the consent surface.

#### Build stripe plan (when greenlit)
S1 schema+backfill · S2 read pipeline · S3 write pipeline+overrides · S4 UI · S5 audit/observability · S6 privacy review gate. Same workflow shape as CB-PEDI-002 — one isolated worktree per stripe, 2× `/pr-review` rounds, integration branch, single PR to master.

#### Rollout
- New flag `parent.digest_multiparent_sync_v1` (off by default).
- Ramp variant: off → on_5 → on_25 → on_50 → on_100 → on_for_all (after counsel signoff).

#### Open design questions (for review)
1. "Remove for everyone" — require all-guardians consent or trust any guardian's judgment? Default proposal: trust + audit-log visibility.
2. In-app notification when another guardian mutates a shared row? Defer to telemetry.
3. Authored shared rows after a guardian leaves the set — keep or cleanup? Default proposal: keep (others may still need them).

#### Status
- **Not in-progress.** Issue #4330 has the `design-review` label only.
- Awaits user greenlight before any build stripe is opened.
- Filed alongside the 2026-04-27 email-digest defect batch (#4327/#4328/#4329) so the design context is captured while it's fresh; **not bundled** into that batch — multi-parent sync is its own concern, large enough to warrant its own design doc + privacy review.

### 6.150 Curriculum-Aligned Content Generation & MCP Server (CB-CMCP-001) — DRAFT (NOT STARTED) 2026-04-27

**Source PRDs:**
- `Requirement/Claude-ai-generated/CB-CMCP-001-PRD-v1.0.docx` (initial draft)
- `Requirement/Claude-ai-generated/CB-CMCP-001-PRD-v1.1.docx` (authenticity amendments — supersedes v1.0)
- `Requirement/Claude-ai-generated/CB-CMCP-001-DD-v1.0.docx` (design)

**Status:** Draft. NOT started — pending strategic decisions and 1–2 board-coordinator validation interviews. Mentor review of v1.0 surfaced four authenticity gaps; v1.1 binds them as requirements (§6.150.1 below). Eleven other gaps remain open as decision/sub-issues (§6.150.2).

#### Why this exists
ClassBridge already generates AI study materials today (CB-ASGF-001 #3390, CB-UTDF-001, CB-TUTOR-001/002, [study_guides](app/models/study_guide.py) with curriculum_codes / template_key / parent_summary). What's missing — and what every B2B-edu competitor (Magic School AI, Diffit, Khanmigo, Brisk, myBlueprint Lessons) is racing toward — is **provable curriculum alignment to Ontario Ministry expectations** with a structured, auditable graph of OEs/SEs as a guardrail. CB-CMCP-001 builds that Curriculum Expectations Graph (CEG), wraps the generation pipeline in CEG guardrails (CGP), and exposes the resulting catalog via a Model Context Protocol server (CB-MCP) for board / developer-ecosystem access. Strategic motivation: provable alignment is a primary OECM/board-procurement objection that ClassBridge's B2C/AI-tutor stack cannot answer today.

#### Five-layer architecture (per PRD v1.1)
1. **Curriculum Expectations Graph (CEG)** — PostgreSQL + pgvector store of Ontario K-12 OE/SE expectations (paraphrased, not verbatim Ministry prose, for Crown-copyright safety). Phase 1: Grades 1–8 Math, Language, Science, Social Studies / History / Geography.
2. **Content Generation Pipeline (CGP)** — FastAPI service that retrieves SEs from CEG, injects them as guardrails into Claude Sonnet (long-form) or GPT-4o-mini (high-volume short artifacts), runs alignment validation, stores artifacts in `content_artifacts` table.
3. **CB-MCP Server** — separate Cloud Run FastAPI service implementing MCP protocol; serves catalog + coverage maps to board/developer clients via OAuth 2.0 + JWT.
4. **Authenticity Layer (NEW v1.1)** — Class-context blending (A1) + Parent Companion content type (A2) + Arc voice overlay (A3). The differentiating layer that prevents the system from shipping as a "generic AI content factory."
5. **Surface Integration (NEW v1.1)** — Generated artifacts emit derivative payloads for Bridge (CB-BRIDGE-001), Daily Check-In (CB-DCI-001), and Email Digest (CB-PEDI-002). End-user delivery is via these existing parent rituals; MCP is the board / developer surface, not the parent channel.

#### 6.150.1 Authenticity amendments (PRD v1.1) — BINDING

These four amendments are the load-bearing differentiators of CB-CMCP-001. They are not optional polish. Without them, the system is indistinguishable from competitors who can also tag content with curriculum codes.

| ID | Amendment | Binding requirement |
|---|---|---|
| **A1** | **Class-Context Blending (FR-02.5)** | Generation MUST blend CEG SE list with a class-context envelope drawn from teacher-uploaded `course_contents`, parsed Google Classroom announcements (last 14 days), parsed teacher-email digest summary (last 30 days), and the teacher's existing approved-artifact library. Reuses CB-ASGF-001 ingestion pipeline. Fallback to CEG-only mode when no class context exists, with explicit "generic — no class-vocab anchoring" badge in UI. Acceptance: ≥70% of generations carry a populated envelope by M3. |
| **A2** | **Parent Companion Content Type (FR-02.6)** | Distinct artifact shape (NOT worksheet-without-answer-key). Contains: plain-language SE explanation, 3–5 talking points, coaching prompts, "how to help without giving the answer" guidance, deep-links into the parent's Bridge view. Self-service exempt from teacher review queue. Delivered via DCI + Digest. Acceptance: every approved student artifact has a Parent Companion derivative within 60s; Parent Companion adoption ≥30% within 7 days of approval. |
| **A3** | **Arc Brand Voice Layer (FR-02.7)** | Versioned prompt module overlay (`arc_voice_v1.txt`, ...) applied AFTER curriculum-guardrail and class-context layers. Student-facing artifacts SHALL carry Arc voice (warm, encouraging, growth-mindset, consistent with CB-TUTOR-001/002). Teacher-facing artifacts SHALL NOT (neutral professional tone). Parent Companion uses warm coaching tone but is NOT Arc-led — Arc is the student's pedagogical companion. Voice version bumps MUST NOT require code deploy. |
| **A4** | **Surface Integration (FR-04.5)** | Every approved artifact emits three derivative payloads: (1) Daily Check-In coach card (CB-DCI-001), (2) Email Digest summary block (CB-PEDI-002), (3) Bridge entry (CB-BRIDGE-001). MCP is NOT the primary parent/student delivery channel — it is the board + developer-ecosystem surface. Acceptance: ≥80% of approved artifacts surface in DCI within 24h; Bridge entry CTR ≥15%. |

#### 6.150.2 Strategic-decision items (NOT addressed in v1.1 — open issues)

These eleven gaps from the mentor review require user-level decisions before requirement-level commitment. Each is tracked as a separate decision or sub-issue under the new CB-CMCP-001 epic.

- One MCP server (role-scoped) vs. two deployments (board + end-user)?
- `content_artifacts` vs. existing `study_guides` table — extend or run parallel?
- Self-study path (no teacher review for self-initiated) vs. teacher-review-only?
- Alignment validator: add second-pass embedding similarity check?
- CEG extraction quality: two-pass extraction + curriculum-expert SLA + headcount line item?
- Latency NFRs: per-content-type SLAs + streaming UX (8s P95 unrealistic for Sonnet long-form)?
- Board surface: REST + signed-CSV + LTI primary, MCP secondary?
- Cost model: $/artifact, monthly burn at 3 volume tiers?
- CEG version cascade: change-severity classifier to avoid mass teacher re-review?
- IEP / differentiation: in CB-CMCP-001 scope or deferred?
- 1–2 board curriculum coordinator validation interviews BEFORE M0 commit?

#### Existing ClassBridge work that CB-CMCP-001 builds on (NOT replaces)
- **CB-ASGF-001 (#3390)** — Ask-a-Question to Flash Study; class-context ingestion pipeline (load-bearing for A1).
- **CB-UTDF-001** — Unified template + detection framework; artifact templating.
- **CB-TUTOR-001 (shipped Apr 23)** — Arc mascot, voice reference patterns (load-bearing for A3).
- **CB-TUTOR-002 Phase 1 (in progress, epic #4062)** — short-learning-cycle pedagogy.
- **CB-BRIDGE-001 (shipped Apr 25)** — Parent Hub surface (load-bearing for A4).
- **CB-DCI-001 (M0 shipped Apr 25)** — Daily Check-In ritual (load-bearing for A4).
- **CB-PEDI-002 (shipped Apr 23)** — Unified Email Digest V2 (load-bearing for A4).
- **#571 Ontario Curriculum Management** — precursor to the CEG (will be subsumed once epic opens).
- **#903 Phase 2 EPIC: MCP Protocol Integration** — end-user/Claude-Desktop MCP vision; different audience than CB-CMCP-001's board MCP.
- **#2191 Epic: Port MCP Implementation from class-bridge-phase-2** — ~50% MCP scaffold; auth + transport reused.
- **#959 Epic: AI Exam & Assessment Engine** — overlaps FR-02.1 Sample Test.
- **#3021 [CB-UTDF] resolve contradictory answer key storage design** — DD §3.5 `content_artifacts.content_json` JSONB resolution.
- **#802 / #803 VASP / DTAP compliance** — board-pilot non-technical predecessor; without a board partner, M4 has nowhere to land.

#### Acceptance status
- [x] PRD v1.0 drafted (`CB-CMCP-001-PRD-v1.0.docx`, Apr 27)
- [x] Mentor review pass complete (Apr 27 — see plan `nifty-crunching-squid.md`)
- [x] PRD v1.1 amendments document (`CB-CMCP-001-PRD-v1.1.docx`, Apr 27) — binds A1–A4 as requirements
- [x] Requirements section §6.149 (this entry) added
- [ ] CB-CMCP-001 epic opened on GitHub
- [ ] Four authenticity gap sub-issues opened (A1–A4)
- [ ] Eleven strategic-decision issues opened
- [ ] Board-coordinator validation interviews complete
- [ ] M0 (CEG build) NOT STARTED — gated on decisions + interviews

### 6.151 My Hub — Daily Digest Panel First + Embedded 5-Recent History (#4349) — INTEGRATION READY 2026-04-27

**Issue/PR:** Epic #4349 · Stream PRs: #4358 (A — shared component), #4360 (M — My Hub reorder + embed), #4372 (E — EmailDigestPage refactor) · Final integration PR: #4378 · **Status:** IMPLEMENTED on `integrate/4349-my-hub-digest-history`, deploy pending

#### Why this exists
The My Hub all-kids view rendered Class Materials before Daily Digest, and the Daily Digest card itself was a thin summary that linked out to `/email-digest` for history. Parents wanted the digest hub more prominent (it's the daily-touchpoint feature) and wanted to see the most recent digests inline without leaving the page. The dedicated `/email-digest` page already had a 50-item Digest History section that duplicated the JSX (~440 lines across legacy + unified renderers). This work reorders the panels, embeds a 5-recent collapsible panel inline, and dedupes the history JSX into one shared component used by both surfaces.

#### Files changed
- **New:** `frontend/src/components/parent/DigestHistoryPanel.{tsx,css}` + `__tests__/DigestHistoryPanel.test.tsx` (Stream A)
- **Modified:** `frontend/src/pages/MyKidsPage.{tsx,css}`, `frontend/src/components/bridge/EmailDigestCard.tsx`, `frontend/src/components/bridge/__tests__/EmailDigestCard.test.tsx` (Stream M)
- **Modified:** `frontend/src/pages/parent/EmailDigestPage.{tsx,test.tsx,css}` (Stream E)

#### Streams
- **Stream A** — Shared `DigestHistoryPanel` component (`limit`, `heading`, `collapsible`, `defaultCollapsed`, `className` props; query key `['email-digest','logs','panel',limit]`; status badge + DOMPurify content render; 8 tests).
- **Stream M** — My Hub all-kids panel reorder; `EmailDigestCard.showRecentHistory` prop renders embedded panel below footer when integration exists.
- **Stream E** — `EmailDigestPage` refactor — both legacy + unified now consume `<DigestHistoryPanel limit={50} />`; ~440 lines of dup JSX/CSS removed.

#### Acceptance Criteria
- [x] My Hub all-kids view: Daily Digest card renders before Class Materials card
- [x] My Hub child view: Daily Digest card already renders first; embedded history added there too
- [x] Embedded panel shows up to 5 recent digests with date · email count · status · expand-to-content
- [x] Embedded panel is collapsible (header click toggles list)
- [x] `/email-digest` Digest History section is visually + behaviorally identical to before (limit unchanged at 50)
- [x] No backend changes (no schema migration, no new endpoint, no new env var)

#### Per-child filtering — explicitly out of scope
The unified v2 data model stores ONE digest delivery per parent per send (covering all kids); `digest_delivery_log` table has no `child_profile_id`/`student_id` column. The 5-recent panel shows the same parent-level entries in both all-kids and child-filter modes. True per-child digest history would require either a backend filter that scans `digest_content` for the child's section or a new join via `SenderChildAssignment` — deferred to a follow-up if usage data shows demand.

#### Tracking
Epic issue **#4349**. PRs: **#4358** (Stream A), **#4360** (Stream M), **#4372** (Stream E). Final integration PR: **#4378**.

#### Deploy note
Frontend-only change. Ship in next routine deploy after `/pr-review` 2× passes.
