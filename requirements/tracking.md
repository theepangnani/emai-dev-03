## 12. GitHub Issues Tracking

Current feature issues are tracked in GitHub:

### Phase 1 - Completed
- Issue #2: ~~Google Classroom OAuth flow~~ (CLOSED)
- Issue #3: ~~Parent/Student dashboard~~ (CLOSED)
- Issue #4: ~~AI study guide generation~~ (CLOSED)
- Issue #5: ~~Assignment alerts and notifications~~ (CLOSED)
- Issue #6: ~~Frontend React application~~ (CLOSED)
- Issue #8: ~~Parent-teacher secure messaging~~ (CLOSED)
- Issue #15: ~~OpenAI/Vertex AI integration~~ (CLOSED)
- Issue #16: ~~Study guide generation API~~ (CLOSED)
- Issue #17: ~~Quiz generation API~~ (CLOSED)
- Issue #18: ~~Flashcard generation API~~ (CLOSED)
- Issue #19: ~~AI study tools frontend~~ (CLOSED)
- Issue #20: ~~Notification model and API~~ (CLOSED)
- Issue #21: ~~Email notification service~~ (CLOSED)
- Issue #22: ~~Assignment reminder background job~~ (CLOSED)
- Issue #23: ~~Notification UI~~ (CLOSED)
- Issue #32: ~~Role-based dashboards~~ (CLOSED)
- Issue #33: ~~Teacher email monitoring~~ (CLOSED)
- Issue #34: ~~Parent-child linking via Google Classroom discovery~~ (CLOSED)
- Issue #35: ~~Migrate parent-student to many-to-many relationship~~ (CLOSED)
- Issue #36: ~~Parent registers child from Parent Dashboard~~ (CLOSED — via invite flow)
- Issue #37: ~~Student invite email flow~~ (CLOSED)
- Issue #38: ~~Update parent linking endpoints for many-to-many~~ (CLOSED)
- Issue #39: ~~Auto-create Teacher record at registration~~ (CLOSED)
- Issue #40: ~~Shadow + invite flow for non-EMAI school teachers~~ (CLOSED)
- Issue #43: ~~Teacher type distinction (school_teacher vs private_tutor)~~ (CLOSED)
- Issue #48: ~~Unified invite system (shared invites table)~~ (CLOSED)
- Issue #44: ~~Google Classroom courses auto-sync for students~~ (CLOSED)
- Issue #47: ~~Student enrollment in courses~~ (CLOSED)
- Issue #52: ~~Teacher Google Classroom course sync (set teacher_id on synced courses)~~ (CLOSED)
- Issue #56: ~~Parent-student-Google sync flow (onboarding, parent sync, teacher info)~~ (CLOSED)

### Phase 1 - Implemented (Parent-First Platform Revision)
- Issue #60: ~~Parent registers child directly (name, email, grade, school)~~ (CLOSED)
- Issue #82: ~~Study guide model: add version, parent_guide_id, content_hash~~ (CLOSED)
- Issue #83: ~~Role-based study guide limits~~ (CLOSED)
- Issue #84: ~~Study guide duplicate detection endpoint~~ (CLOSED)
- Issue #85: ~~Study guide versioning~~ (CLOSED)
- Issue #86: ~~Role-based study guide visibility~~ (CLOSED)
- Issue #87: ~~Frontend study guide management UI~~ (CLOSED)
- Issue #88: ~~Update REQUIREMENTS.md with study guide management~~ (CLOSED)
- Issue #90: ~~Make student email optional — parent creates child with name only~~ (CLOSED)
- Issue #91: ~~Allow parents and students to create courses~~ (CLOSED)
- Issue #92: ~~Parent assigns courses to linked children~~ (CLOSED)
- Issue #93: ~~Add `created_by_user_id` and `is_private` fields to Course model~~ (CLOSED)
- Issue #94: ~~Disable auto-sync jobs — all Google/Gmail sync must be manual and on-demand~~ (CLOSED)
- Issue #95: ~~Parent Dashboard: course management UI (create, assign, view)~~ (CLOSED)
- Issue #97: ~~Parent Dashboard calendar-centric redesign v1~~ (CLOSED)
- Issue #98: ~~Study guide course assignment — PATCH endpoint + CourseAssignSelect component~~ (CLOSED)
- Issue #99: ~~Parent Dashboard v2: Left navigation + Edit Child modal + child filter toggle~~ (CLOSED)
- Issue #100: ~~Task system: backend model, CRUD API, cross-role assignment~~ (CLOSED)
- Issue #101: ~~Parent Dashboard v2: Day Detail Modal + task calendar integration~~ (CLOSED)
- Issue #102: ~~Parent Dashboard v2: Dedicated Courses page (`/courses`)~~ (CLOSED)
- Issue #103: ~~Parent Dashboard v2: Dedicated Study Guides page (`/study-guides`)~~ (CLOSED)
- Issue #104: ~~Cross-role task assignment — backend model & API~~ (CLOSED)
- Issue #105: ~~Dedicated Tasks page~~ (CLOSED)
- Issue #106: ~~Tasks displayed in calendar~~ (CLOSED)
- Issue #107: ~~Task archival — soft-delete, restore, permanent delete, auto-archive~~ (CLOSED)
- Issue #108: ~~Calendar sticky note cards — priority-colored, expandable~~ (CLOSED)
- Issue #115: ~~Study Guide: Improve formatting and readability~~ (CLOSED)
- Issue #117: ~~Bug: Task status dropdown filters are not working~~ (CLOSED)
- Issue #118: Calendar: Enable editing task due date via drag-and-drop (IMPLEMENTED)
- Issue #123: ~~Bug: Calendar tasks not filtered by selected child in Calendar view~~ (CLOSED)
- Issue #124: ~~Course Page: Add Create Course CTA and flow entry point~~ (CLOSED)
- Issue #125: ~~Tasks Page: Convert Create New Task into a well-formatted modal~~ (CLOSED)
- Issue #51: ~~Deprecate POST /api/courses/ endpoint~~ (SUPERSEDED — endpoint now serves all roles)
- Issue #135: ~~Task entity linking: link tasks to courses, content, and study guides~~ (CLOSED)
- Issue #136: ~~Study guide conversion and duplicate prevention~~ (CLOSED)
- Issue #137: ~~Fix AI response JSON parsing (strip markdown code fences) + confirmation dialogs~~ (CLOSED)
- Issue #138: ~~Clickable entity badges on Tasks page~~ (CLOSED)
- Issue #157: ~~Non-blocking AI study material generation with progress placeholder~~ (CLOSED)
- Issue #158: ~~Add calendar quick-action buttons on Parent Dashboard~~ (CLOSED)
- Issue #159: ~~Fix: make users.email nullable in PostgreSQL for parent-created students~~ (CLOSED)
- Issue #160: ~~Replace native window.confirm with styled ConfirmModal component~~ (CLOSED)
- Issue #161: ~~Add lazy import retry to auto-recover from stale chunks after deploy~~ (CLOSED)
- Issue #162: ~~Backend: Add course_content_id FK to study_guides and is_default to courses~~ (CLOSED)
- Issue #163: ~~Backend: Auto-create default course + CourseContent on study guide generation~~ (CLOSED)
- Issue #164: ~~Frontend: Course Material tabbed detail view (Original / Study Guide / Quiz / Flashcards)~~ (CLOSED)
- Issue #165: ~~Frontend: Refactor Study Guides page to list course materials with child/course filters~~ (CLOSED)

### Phase 1 - Implemented (Teacher & Parent Enhancements)
- ~~Issue #187: Add cascading deletes and unique constraints~~ ✅
- ~~Issue #211: Multi-role support: allow users to hold multiple roles (Phase A)~~ ✅
- ~~Issue #212: Course materials lifecycle management (soft delete, archive, retention)~~ ✅
- ~~Issue #213: Message email notifications with dedup~~ ✅
- ~~Issue #218: Add loading skeleton preloaders to remaining pages~~ ✅
- ~~Issue #219-#224: Manual parent-to-teacher linking~~ ✅
- ~~Issue #225: Teacher adds/removes students from courses~~ ✅
- ~~Issue #226: Assign teacher to course during creation/editing~~ ✅
- ~~Issue #227: Teacher invite via course context~~ ✅
- ~~Issue #230-#233: Role-based inspirational messages~~ ✅
- ~~Issue #234: Teacher linking: send email notification to new teacher~~ ✅
- ~~Issue #235: Teacher linking: send email notification to existing teacher~~ ✅
- ~~Issue #236: MyKids: Add quick stats (course count, active tasks) to child overview cards~~ ✅
- ~~Issue #237: MyKids: Add icons to section headers and remove Courses from parent nav~~ ✅

### Phase 1 - Implemented (Feb 11-12 Sprint)
- ~~Issue #49: Manual assignment creation for teachers~~ ✅
- ~~Issue #112: Task reminders: daily in-app notifications for upcoming task due dates~~ ✅
- ~~Issue #140: Add rate limiting to auth, AI generation, and file upload endpoints~~ ✅
- ~~Issue #141: Add security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)~~ ✅
- ~~Issue #143: Add password reset flow (Forgot Password)~~ ✅
- ~~Issue #149: Implement JWT token refresh mechanism~~ ✅
- ~~Issue #152: Mobile responsive web: CSS breakpoints for 5+ pages~~ ✅
- ~~Issue #155: Add backend route tests for google, study, messages, notifications, admin, invites~~ ✅
- ~~Issue #181: HIGH: Fix RBAC gaps on students, assignments, courses, users, and content routes~~ ✅
- ~~Issue #182: HIGH: Secure logging endpoint and parent-created student passwords~~ ✅
- ~~Issue #184: MEDIUM: Fix LIKE pattern injection in search and study guide routes~~ ✅
- ~~Issue #206: Parent UX: Consolidated parent navigation via My Kids page~~ ✅
- ~~Issue #207: Parent Dashboard: Collapsible/expandable calendar (now defaults to collapsed — #544)~~ ✅
- ~~Issue #208: Fix overdue/due-today count mismatch between dashboard and TasksPage~~ ✅
- ~~Issue #209: Add assignee filter to TasksPage for filtering by student~~ ✅
- ~~Issue #210: Task Detail Page: Inline edit mode with all fields~~ ✅
- ~~Issue #255-#257: Multi-role support Phase B requirements and issues created~~ (PLANNED)
- ~~Issue #258: Admin broadcast messaging: send message + email to all users~~ ✅
- ~~Issue #259: Admin individual messaging: send message + email to a specific user~~ ✅
- Issue #260: Inspirational messages in emails: add role-based quotes to all outgoing emails (PLANNED)
- ~~Issue #261: Notification click opens popup modal with full message content~~ ✅
- ~~Issue #262: Messages page: show all admin messages for every user~~ ✅
- ~~Issue #263: User-to-admin messaging: any user can message admin, all admins get email~~ ✅

### Phase 1 - Implemented (Feb 14 Sprint)
- ~~Issue #144: Fix N+1 query patterns in task list, child list, and reminder job~~ ✅ (fixed in #241)
- ~~Issue #180: HIGH: Add JWT token revocation and rate limiting~~ ✅
- ~~Issue #186: MEDIUM: Fix N+1 queries in messages, tasks, and parent routes~~ ✅ (fixed in #241)
- ~~Issue #241: Performance: Fix N+1 queries in tasks, messages, and parent dashboard~~ ✅
- ~~Issue #246: UX: Parent-first flow improvements~~ ✅
- ~~Issue #250: Student self-enrollment: add browse/enroll/unenroll UI~~ ✅
- ~~Issue #251: Add visibility check to student self-enrollment endpoint~~ ✅
- ~~Issue #252: Teacher invites parent to ClassBridge~~ ✅
- ~~Issue #261: Notification click opens popup modal with full message content~~ ✅
- ~~Issue #262: Messages page: show all admin messages for every user~~ ✅
- ~~Issue #263: User-to-admin messaging: any user can message admin, all admins get email~~ ✅

### Phase 1 - Implemented (Feb 15: CI + Mobile MVP Sprint)
- ~~Issue #247: Accessibility: ARIA labels, keyboard navigation, skip-to-content~~ ✅
- ~~Issue #273: CI hardening: verify test job blocks deploy on failure~~ ✅ (deploy.yml already properly structured; 305 backend + 183 frontend tests passing)
- ~~Issue #308: Update ClassBridge logo and favicon assets~~ ✅
- ~~Issue #309: Admin endpoint to update user email with cascade to invites~~ ✅
- ~~Issue #256: Auto-create profiles on registration~~ ✅
- ~~Issue #257: Multi-role registration with checkbox UI~~ ✅

### Phase 1 - Implemented (Feb 15: Bug Fixes, Test Expansion & Backup Infrastructure)
- ~~Issue #153: Fix FlashcardsPage stale closure bug in keyboard handler~~ ✅ (useRef pattern for stable keyboard event handler)
- ~~Issue #154: Add frontend unit tests (vitest)~~ ✅ (75 new tests: FlashcardsPage 27, QuizPage 15, StudyGuidePage 14, TasksPage 20; total 253 frontend tests)
- ~~Issue #353: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅ (daily backups 02:00 UTC, PITR 7-day, log-based metric + alert policy, 4 scripts + runbook)
- ~~Issue #411: Improve landing page logo clarity and hero branding~~ ✅
- Fix CI test failures: Add `pyproject.toml` with `testpaths = ["tests"]` and update `deploy.yml` — `scripts/load_test.py` matched pytest's `*_test.py` pattern, causing secret key mismatch in test environment ✅

### Phase 1 - Implemented (Feb 15: UI Polish)
- ~~Issue #420: Add show/hide password toggle to all auth pages~~ ✅ (eye icon toggle on Login, Register, Reset Password, Accept Invite)
- ~~Issue #427: Reduce whitespace around logo and increase size~~ ✅ (CSS negative margins to crop built-in PNG padding on auth pages, landing nav/hero, dashboard header)

### Phase 1 - Implemented (Feb 16: Bug Fix)
- ~~Issue #429: Fix study guide 404 for parents (guide ID 8)~~ ✅ (add logging to distinguish "not found" vs "access denied"; exclude archived guides from duplicate detection; change enforce_study_guide_limit to soft-delete instead of hard-delete; improve frontend 404 error message with navigation links)

### Phase 1 - Implemented (Feb 16: Courses Page Fix)
- ~~Issue #435: Courses page: missing styles and course materials not displayed~~ ✅ (add .child-selector/.child-tab CSS to CoursesPage.css; implement inline course content expansion on course cards for parent and student views)

### Phase 1 - Implemented (Feb 16: Hover Buttons Fix)
- ~~Issue #446: Missing hover edit button on course tiles and assign-to-course on material tiles~~ ✅ (add edit ✏️ button to parent child-course tiles and student enrolled-course tiles; add move-to-course 📂 button to course material rows on StudyGuidesPage with course selector modal; add `course_id` to `CourseContentUpdate` schema for reassignment)

### Phase 1 - Implemented (Feb 17: Docx OCR + Math-Aware AI Prompts)
- ~~Issue #532: Word doc embedded screenshots not OCR'd + study guide should solve math problems~~ ✅ (always OCR all embedded images in .docx regardless of text length; enhance study guide/quiz/flashcard AI prompts to detect math problems and provide step-by-step solutions; 7 new unit tests for OCR logic)

### Phase 1 - Implemented (Feb 17: Inline Generation Loading)
- ~~Issue #527: Quiz/Flashcard generation should show inline loading in content area instead of blocking spinner~~ ✅ (replace full-screen overlay with inline spinner + pulsing message in content area on CourseMaterialDetailPage; auto-switch to target tab on generation; tabs remain navigable during generation)

### Phase 1 - Implemented (Feb 17: Navigation & Back Button Fix)
- ~~Issue #529: Missing back button on Course Materials and Courses pages~~ ✅ (add `showBackButton` prop to DashboardLayout; back button uses `navigate(-1)` for true browser history back; enabled on all sub-pages: Courses, Course Materials, CourseDetail, CourseMaterialDetail, MyKids, Tasks, Help, FAQ)
- ~~Issue #530: Parent sidebar missing Courses and Course Materials navigation links~~ ✅ (restore Courses and Course Materials to parent nav items in DashboardLayout sidebar)

### Phase 1 - Implemented (Feb 18: Dashboard Simplification — #540, PR #545)
- ~~Issue #540: Parent Dashboard Simplification — Single Hub with Urgency-First Layout~~ ✅
- ~~Issue #541: Dashboard: Persistent sidebar navigation (replace hamburger)~~ ✅
- ~~Issue #542: Dashboard: Alert banner + unified child filter pills~~ ✅
- ~~Issue #543: Dashboard: Quick Actions bar + Student Detail Panel with urgency-grouped tasks~~ ✅
- ~~Issue #544: Dashboard: Calendar default collapsed + dead code cleanup~~ ✅

### Phase 1 - Implemented (Feb 18: Dashboard UX Polish — #557)
- ~~Issue #557: Parent Dashboard UX: Today's Focus header, icon-only sidebar, collapsible detail panel~~ ✅ (removed redundant status cards; simplified AlertBanner to overdue + invites only; added Today's Focus header with urgency badges and "All caught up!" state; converted sidebar to always icon-only with bigger icons and hover tooltips; made StudentDetailPanel collapsible with summary header; redesigned QuickActionsBar with primary/secondary action hierarchy)

### Phase 1 - Implemented (Feb 21: UI/UX Audit — Phase 1 Improvements, #668)

**Round 1 (Parallel Streams A/B/C):**
- ~~Issue #646: Student Dashboard: Today's Focus header with urgency badges~~ ✅
- ~~Issue #647: Student Dashboard: Assignment urgency sorting with color-coded due dates~~ ✅
- ~~Issue #648: Teacher Dashboard: Class activity summary & at-a-glance overview~~ ✅
- ~~Issue #650: Teacher Dashboard: Upload Material quick action~~ ✅
- ~~Issue #651: Student onboarding card for material upload workflow~~ ✅
- ~~Issue #653: Admin Dashboard: Trend indicators & recent activity feed~~ ✅

**Round 2 (Parallel Streams A/B/C):**
- ~~Issue #649: Auto-create task prompt after study guide generation~~ ✅
- ~~Issue #652: Enhanced empty states with contextual CTAs across all dashboards~~ ✅
- ~~Issue #654: Calendar first-visit expanded state with onboarding tooltip~~ ✅
- ~~Issue #655: Persist filter state in URL query parameters~~ ✅
- ~~Issue #656: Notification center — "View All" page & persistent history~~ ✅
- ~~Issue #658: Standardize navigation items & SVG icons across all roles~~ ✅
- ~~Issue #660: Micro-interactions (button press, card hover, section collapse)~~ ✅

**Round 3 (Parallel Streams A/B/C/D):**
- ~~Issue #657: Refactor ParentDashboard.tsx — extract useParentDashboard hook + TodaysFocusHeader (1668→544 LOC)~~ ✅
- ~~Issue #659: Consistent loading states, last-synced timestamps, retry buttons~~ ✅
- ~~Issue #661: Breadcrumb navigation for all detail pages (desktop trail + mobile back-link)~~ ✅
- ~~Issue #662: Mobile touch: long-press drag, swipe calendar nav, modal scroll fix~~ ✅

### Phase 1 - Implemented (Feb 21: Student Dashboard Redesign — #708, PR #709)
- ~~Issue #708: Student Dashboard: "Focused Command Center" redesign~~ ✅ (hero greeting with urgency pills + stat chips, notification alerts for parent/teacher requests, quick action cards, Coming Up timeline merging assignments + tasks, recent materials, course chips, create course modal, onboarding card, `sd-` CSS prefix scoping, 27 tests updated)

### Phase 1 - Implemented (Feb 22: Print & PDF Export — #764, PR #763)
- ~~Issue #764: Print and Download PDF for study materials~~ ✅ (Print + Download PDF buttons on all 4 Course Material Detail tabs; html2pdf.js dynamic import; static print views for quiz all-questions and flashcards all-cards; shared `exportUtils.ts` utility)

### Phase 1 - Open (Parent Dashboard Redesign — Epic #710)
- Issue #710: Epic: Parent Dashboard Visual Redesign
- Issue #711: Parent Dashboard: Visual refresh with distinctive design language
- Issue #712: Parent Dashboard: Add "Coming Up" timeline for selected child
- Issue #713: Parent Dashboard: Multi-child comparison cards in All Children mode
- Issue #714: Parent Dashboard: Clean up dead CSS and scope with `pd-` prefix
- Issue #715: Parent Dashboard: Refactor useParentDashboard into focused sub-hooks
- Issue #716: Parent Dashboard: Enhanced onboarding for first-time parents
- Issue #717: Parent Dashboard: Make urgency overview persistent (non-dismissible)
- Issue #718: Parent Dashboard: Add course activity feed for selected child
- Issue #719: Parent Dashboard: Accessibility improvements (ARIA, keyboard, focus)

### Phase 1 - Open
- Issue #41: Multi-Google account support for teachers
- Issue #42: Manual course creation for teachers
- Issue #57: Auto-send invite email to shadow teachers on creation
- Issue #58: Add is_platform_user flag to Teacher model
- Issue #59: Teacher Dashboard course management view with source badges
- Issue #61: Content privacy controls and version history for uploads
- Issue #62: teacher_google_accounts table for multi-account OAuth
- Issue #89: Auto-create student account when parent links by email
- Issue #109: AI explanation of assignments
- Issue #110: Add assignment/test to task (link tasks to assignments) — courses, content, and study guides now linkable; assignment linking pending
- ~~Issue #111: Student self-learn: create and manage personal courses~~ ✅
- Issue #114: Course materials: file upload and storage (GCS) — upload + text extraction done, GCS pending
- ~~Issue #116: Courses: Add structured course content types + reference/Google Classroom links~~ ✅
- Issue #119: Recurring Tasks: Feasibility + implementation proposal
- ~~Issue #126: Calendar Task Actions: Add quick links beyond Create Study Guide~~ ✅
- ~~Issue #166: Audit logging: persistent audit trail with admin API and UI~~ ✅
- ~~Issue #167: Task Detail Page with full task info and actions~~ ✅
- ~~Issue #168: Calendar task popover: icon buttons + task detail navigation fix~~ ✅
- ~~Issue #172: Fix ungrouped study guide categorization (Move to Course)~~ ✅
- ~~Issue #173: Move to Course: searchable dropdown + create new course~~ ✅
- ~~Issue #174: Global search: backend unified search endpoint~~ ✅
- ~~Issue #175: Global search: frontend search component in DashboardLayout~~ ✅
- ~~Issue #183: Task Detail Page: link/unlink resources (courses, materials, study guides)~~ ✅
- ~~Issue #193: Task list: click task row to navigate to task detail page~~ ✅
- Issue #194: Rename 'Study Guide' to 'Course Material' across UI and navigation
- ~~Issue #420: Frontend: Add show/hide password toggle to all auth pages~~ ✅
- Issue #509: Send welcome email after user registration
- Issue #510: Send acknowledgement email after email verification
- ~~Issue #169: Color theme: Clean up hardcoded CSS colors (prerequisite for themes)~~ ✅
- ~~Issue #170: Color theme: Dark mode (ThemeContext, ThemeToggle, dark palette)~~ ✅
- ~~Issue #171: Color theme: Focus mode (muted warm tones for study sessions)~~ ✅

### Phase 1.5 - Calendar Extension, Content, Search, Mobile & School Integration
- ~~Issue #174: Global search: backend unified search endpoint~~ ✅
- ~~Issue #175: Global search: frontend search component in DashboardLayout~~ ✅
- ~~Issue #152: Mobile responsive web: CSS breakpoints for 5+ pages~~ ✅
- ~~Issue #308: Update ClassBridge logo and favicon assets~~ ✅
- Issue #195: AI auto-task creation: extract critical dates from generated course materials
- Issue #96: Student email identity merging (personal + school email)
- Issue #45: Extend calendar to other roles (student, teacher) with role-aware data (parent calendar done in #97)
- Issue #46: Google Calendar push integration for tasks
- ~~Issue #25: Manual Content Upload with OCR (enhanced) — document upload + text extraction done; image OCR for embedded images in .docx~~ ✅ (#523)
- Issue #28: Central Document Repository
- Issue #53: Background periodic Google Classroom sync for teachers
- Issue #113: School & School Board model
- ~~Issue #201: Parent UX: Single dashboard API endpoint~~ ✅
- ~~Issue #202: Parent UX: Status-first dashboard~~ ✅
- ~~Issue #203: Parent UX: One-click study material generation~~ ✅
- ~~Issue #204: Parent UX: Fix filter cascade on Course Materials page~~ ✅
- ~~Issue #205: Parent UX: Reduce modal nesting~~ ✅
- ~~Issue #206: Parent UX: Consolidated parent navigation via My Kids page~~ ✅
- ~~Issue #207: Parent Dashboard: Collapsible/expandable calendar (now defaults to collapsed — #544)~~ ✅

### Phase 2
- Issue #26: Performance Analytics Dashboard (umbrella — broken into #469-#474)
- Issue #27: Notes & Project Tracking Tools
- Issue #29: TeachAssist Integration
- Issue #50: Data privacy & user rights (FERPA/PIPEDA compliance)

### Phase 2 — Performance Analytics (#26) ✅ COMPLETE
- ~~Issue #469: Analytics: Grade data pipeline (GradeRecord model, sync service, seed service)~~ ✅
- ~~Issue #470: Analytics: Backend aggregation service and API endpoints~~ ✅
- ~~Issue #471: Analytics: Frontend dashboard with Recharts (LineChart, BarChart, summary cards)~~ ✅
- ~~Issue #472: Analytics: AI-powered performance insights (on-demand via OpenAI)~~ ✅
- ~~Issue #473: Analytics: Weekly cached progress reports (ProgressReport model, 24h TTL)~~ ✅
- Issue #474: Analytics: Test expansion (14 backend + 6 frontend tests written; more coverage possible)

### Phase 2 — Admin Email & Broadcast Management
- Issue #513: Admin: View and edit email templates from dashboard
- Issue #514: Admin: Broadcast email history with reuse and resend

### Phase 2 — FAQ / Knowledge Base
- Issue #437: FAQ: Backend models — FAQQuestion + FAQAnswer tables
- Issue #438: FAQ: Pydantic schemas for request/response validation
- Issue #439: FAQ: Backend API routes — CRUD + admin approval workflow
- Issue #440: FAQ: Integrate FAQ into global search
- Issue #441: FAQ: Error-to-FAQ reference system
- Issue #442: FAQ: Frontend pages — FAQ list, detail, and admin management
- Issue #443: FAQ: Backend + frontend tests
- Issue #444: FAQ: Seed initial how-to entries for pilot

### March 6 Pilot — Mobile MVP (Completed)
- ~~Issue #364: Mobile MVP: API client & auth modules (AsyncStorage, refresh tokens)~~ ✅
- ~~Issue #365: Mobile MVP: AuthContext & LoginScreen~~ ✅
- ~~Issue #366: Mobile MVP: Navigation setup (auth-gated stack + bottom tabs)~~ ✅
- ~~Issue #367: Mobile MVP: ParentDashboardScreen~~ ✅
- ~~Issue #368: Mobile MVP: ChildOverviewScreen~~ ✅
- ~~Issue #369: Mobile MVP: CalendarScreen (read-only)~~ ✅
- ~~Issue #370: Mobile MVP: MessagesListScreen~~ ✅
- ~~Issue #371: Mobile MVP: ChatScreen (read & reply)~~ ✅
- ~~Issue #372: Mobile MVP: NotificationsScreen~~ ✅
- ~~Issue #373: Mobile MVP: ProfileScreen (view & logout)~~ ✅
- ~~Issue #374: Mobile MVP: UI polish (loading, empty states, pull-to-refresh, tab badges)~~ ✅
- ~~Issue #357: Web: Update CORS config for mobile app origins~~ ✅ (Not needed — CORS is browser-only, React Native bypasses it)

### March 6 Pilot — Web Production Readiness (In Progress)
- ~~Issue #354: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅
- ~~Issue #353: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅ (duplicate of #354)
- ~~Issue #355: API Versioning Strategy: Options & Decision~~ ✅ (Decision: no versioning needed for pilot; mobile calls same `/api/*` endpoints)
- Issue #358: Web: End-to-end testing on production — smoke test script created (`scripts/smoke-test.py`), needs credentials for full run
- ~~Issue #359: Web: Performance validation with 50+ simulated users~~ ✅
- ~~Issue #360: Web: Create pilot user accounts and demo data~~ ✅
- ~~Issue #361: Web: Monitoring and alerting setup for production~~ ✅
- ~~Issue #362: Web: Pilot onboarding prep (welcome email, quick-start guide)~~ ✅
- ~~Issue #363: Web: Deploy freeze and dress rehearsal~~ ✅
- ~~Issue #385: Create privacy policy and terms of service pages~~ ✅
- Issue #265: Go live: Production deployment with custom domains
- Issue #375: Mobile MVP: Device testing (iOS + Android via Expo Go) — code quality prep done, physical testing pending
- ~~Issue #376: March 6 Pilot Launch: Go-Live Checklist~~ ✅

**Pilot prep subtasks (parallelizable):**
- Issue #396: Register custom domains with Cloud Run (depends on DNS access)
- ~~Issue #397: Update Google OAuth redirect URIs for production domain (depends on #396)~~ ✅
- Issue #398: Create pilot user accounts and verify login
- Issue #399: Run smoke-test.py against production with all 4 roles (depends on #398)
- Issue #400: Verify SendGrid email delivery from production
- ~~Issue #388: Launch day: Monitoring and incident response plan~~ ✅
- ~~Issue #401: Set Cloud Run min-instances=1 to avoid cold starts~~ ✅
- ~~Issue #402: Prepare Expo Go access instructions for pilot parents~~ ✅
- ~~Issue #406: Update documentation with production URL (classbridge.ca)~~ ✅
- ~~Issue #386: Create pilot user accounts and seed demo data~~ ✅
- ~~Issue #387: Pilot onboarding: Welcome email and setup guide~~ ✅
- ~~Issue #389: Marketing: Landing page for limited launch~~ ✅
- ~~Issue #409: Email branding: Add ClassBridge logo to all email templates~~ ✅
- ~~Issue #410: Email branding: Unify color theme across all email templates~~ ✅
- ~~Issue #321: Enhance health endpoint with version info~~ ✅
- ~~Issue #359: Performance validation with load test script~~ ✅
- ~~Issue #363: Deploy freeze and dress rehearsal~~ ✅
- ~~Issue #376: March 6 Pilot Launch: Go-Live Checklist~~ ✅
- ~~Issue #408: Email format validation on all input fields~~ ✅

### Mobile App — Post-Pilot (Phase 3-4, Open)
- Issue #377: Phase 3: Add notification polling to mobile app
- Issue #378: Phase 3: React Query offline caching for mobile
- Issue #379: Phase 4: Student mobile screens (dashboard, assignments, study viewer)
- Issue #380: Phase 4: Teacher mobile screens (messages, notifications, quick view)

### Mobile App — Original Full Plan (Deferred, Open)

**Backend API Preparation (#311-#322) — Deferred to post-pilot as needed:**
- ~~Issue #311: Backend: Implement API Versioning (v1)~~ (CLOSED — not needed for pilot; mobile calls same `/api/*` endpoints)
- Issue #312: Backend: Add Pagination to All List Endpoints
- Issue #313: Backend: Implement Structured Error Responses
- Issue #314: Backend: Set Up Firebase Admin SDK
- Issue #315: Backend: Create DeviceToken Model and Registration Endpoints
- Issue #316: Backend: Implement Push Notification Service
- Issue #317: Backend: Integrate Push Notifications with Key Events
- Issue #318: Backend: Assignment Reminder Background Job
- Issue #319: Backend: Profile Picture Upload Endpoint
- Issue #320: Backend: Assignment File Upload Endpoint
- Issue #321: Backend: Enhance Health Endpoint with Version Info
- Issue #322: Backend: Integration Tests for v1 API

**Mobile App Screens (#323-#340) — Superseded by pilot MVP issues #364-#374:**
- Issue #323-#340: Original full mobile plan screens (many superseded by simpler pilot MVP)

**Testing & Deployment (#341-#346):**
- Issue #340: Testing: Manual Testing - iOS
- Issue #341: Testing: Manual Testing - Android
- Issue #343: Deployment: Beta Testing with TestFlight (iOS) — Phase 3+
- Issue #344: Deployment: Beta Testing with Google Play Internal Testing — Phase 3+
- Issue #345: Deployment: Prepare App Store Submission - iOS — Phase 4
- Issue #346: Deployment: Prepare Google Play Submission - Android — Phase 4

**Documentation (#347-#349) & Risk (#350-#352):**
- Issue #347-#349: Mobile documentation (deferred)
- Issue #350: RISK: Push Notification Delivery Failures
- Issue #351: RISK: File Upload Storage Costs
- Issue #352: Infrastructure: Set Up CI/CD for Mobile Builds — Phase 4

### Phase 2+ (Future)
- Issue #192: ~~Native mobile apps~~ → SUPERSEDED by #364-#380

### Phase 3 — Course Planning & Guidance (#500-#511)
- Issue #511: School Board Integration — board-specific catalogs, student ↔ board linking (depends on #113)
- Issue #500: Course Catalog Model — board-scoped high school course database with prerequisites, credits, grade levels
- Issue #501: Academic Plan Model — multi-year high school course plan per student
- Issue #502: Prerequisite & Graduation Requirements Engine — validate plans against OSSD rules
- Issue #503: AI Course Recommendations — board-specific personalized guidance based on student profile and goals
- Issue #504: Semester Planner UI — select and arrange courses per semester
- Issue #505: Multi-Year High School Planner UI — visual Grade 9-12 course map
- Issue #506: University Pathway Alignment — map course plans to post-secondary program requirements
- Issue #507: Course Planning Navigation & Dashboard Integration
- Issue #508: Course Planning Tests — backend + frontend test coverage

### Phase 4+
- Issue #30: Tutor Marketplace
- Issue #31: AI Email Communication Agent

### Security & Hardening (Codebase Analysis — Feb 2026)
- ~~Issue #139: Security: Fix authorization gaps in list_students, get_user, list_assignments~~ ✅
- ~~Issue #140: Add rate limiting to auth, AI generation, and file upload endpoints~~ ✅
- ~~Issue #141: Add security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)~~ ✅
- Issue #142: Add input validation and field length limits across all endpoints
- ~~Issue #143: Add password reset flow (Forgot Password)~~ ✅
- ~~Issue #144: Fix N+1 query patterns in task list, child list, and reminder job~~ ✅ (fixed in #241)
- ~~Issue #145: Add CASCADE delete rules to FK relationships~~ ✅ (fixed in #187)
- ~~Issue #146: Add unique constraint on parent_students (parent_id, student_id)~~ ✅ (fixed in #187)
- ~~Issue #147: Add React ErrorBoundary for graceful error handling~~ ✅
- ~~Issue #148: Add global toast notification system for user feedback~~ ✅
- ~~Issue #149: Implement JWT token refresh mechanism~~ ✅
- ~~Issue #150: Add loading skeletons to replace text loading states~~ ✅
- Issue #151: Accessibility audit: aria labels, keyboard nav, skip-to-content
- ~~Issue #152: Mobile responsive web: CSS breakpoints for 5+ pages~~ ✅
- ~~Issue #153: Fix FlashcardsPage stale closure bug in keyboard handler~~ ✅
- ~~Issue #154: Add frontend unit tests (vitest)~~ ✅ (258 frontend tests across 18 files)
- ~~Issue #155: Add backend route tests for google, study, messages, notifications, admin, invites~~ ✅
- Issue #156: Add PostgreSQL test environment to CI for cross-DB coverage

### Risk Audit (Full Application Review — Feb 2026)
- ~~Issue #176: CRITICAL: Fix admin self-registration and password validation~~ ✅
- ~~Issue #177: CRITICAL: Fix CORS wildcard and secure authentication tokens~~ ✅
- ~~Issue #178: CRITICAL: Secure Google OAuth flow~~ ✅
- ~~Issue #179: CRITICAL: Fix hardcoded JWT secret key~~ ✅
- ~~Issue #180: HIGH: Add JWT token revocation and rate limiting~~ ✅
- ~~Issue #181: HIGH: Fix RBAC gaps on students, assignments, courses, users, and content routes~~ ✅
- ~~Issue #182: HIGH: Secure logging endpoint and parent-created student passwords~~ ✅
- ~~Issue #184: MEDIUM: Fix LIKE pattern injection in search and study guide routes~~ ✅
- Issue #185: MEDIUM: Add database migration tooling (Alembic)
- ~~Issue #186: MEDIUM: Fix N+1 queries in messages, tasks, and parent routes~~ ✅ (fixed in #241)
- ~~Issue #187: MEDIUM: Add cascading deletes and unique constraints~~ ✅
- Issue #188: LOW: Replace deprecated dependencies (python-jose, PyPDF2, datetime.utcnow)
- ~~Issue #189: LOW: Add deployment pipeline tests and database backup strategy~~ ✅ (backup strategy in #354, CI test gating verified)
- Issue #190: LOW: Improve health check endpoint to verify database connectivity
- ~~Issue #191: LOW: Fix audit log silent failure and invite token reuse~~ ✅ (audit SAVEPOINT in #392, invite with_for_update in #392)

### Architecture & DDD Migration
- Issue #127: Split api/client.ts into domain-specific API modules
- Issue #128: Extract backend domain services from route handlers
- Issue #129: Introduce repository pattern for data access
- ~~Issue #130: Split ParentDashboard into sub-components~~ ✅ (AlertBanner, StudentDetailPanel, QuickActionsBar extracted in #540; useParentDashboard hook + TodaysFocusHeader extracted in #657; now 544 LOC)
- Issue #131: Activate TanStack Query for server state management
- Issue #132: Reorganize backend into domain modules (DDD bounded contexts)
- Issue #133: Reorganize frontend into domain modules
- Issue #134: Add domain events for cross-context communication

### Infrastructure & DevOps
- Issue #10: Pytest unit tests
- Issue #11: ~~GitHub Actions CI/CD~~ (CLOSED)
- Issue #12: PostgreSQL + Alembic migrations
- Issue #13: ~~Deploy to GCP~~ (CLOSED)
- Issue #14: Google OAuth verification
- Issue #24: Register classbridge.ca domain
- ~~Issue #353: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅

### Security & Hardening
- ~~Issue #63: Require SECRET_KEY and fail fast if missing~~ ✅ (fixed in #179)
- ~~Issue #64: Fix CORS configuration for credentials~~ ✅ (fixed in #177)
- Issue #65: Protect frontend log ingestion endpoints
- Issue #66: Introduce Alembic migrations and remove create_all on startup
- Issue #67: Prevent duplicate APScheduler jobs in multi-worker deployments
- Issue #68: Encrypt Google OAuth tokens at rest
- Issue #69: Revisit JWT storage strategy to reduce XSS risk

### UI & Theming
- Issue #486: Flat (non-gradient) UI theme — replace gradients with solid colors (parent tracking)
- Issue #487: Web: Replace all CSS gradient backgrounds with solid accent colors (13 CSS files)
- Issue #488: Mobile: Remove gradient from login button and use solid theme colors
- Issue #489: Add gradient/flat style toggle to theme system (low priority)

### Observability & Quality
- Issue #70: Populate request.state.user_id for request logs
- ~~Issue #71: Add baseline test suite (auth, RBAC, core routes)~~ ✅
- Issue #72: Roll out new design system across remaining pages
- Issue #73: Add migration for new DB indexes
- Issue #74: Add pagination for conversations/messages list
- Issue #75: Introduce lightweight caching for read-heavy endpoints
- Issue #76: Document local seed + load testing workflow
- Issue #77: Design system + perf + local testing tools

### Testing
- Issue #78: Manual test scenarios: backend API
- Issue #79: Manual test scenarios: frontend UX
- Issue #80: Add E2E smoke tests (Playwright or Cypress)

---

## 13. Development Setup

See individual skill files for development commands:
- `/start` - Start development servers
- `/build` - Build for production
- `/test` - Run test suite
- `/status` - Check project status
- `/db-reset` - Reset development database
- `/feature` - Create feature branch
- `/new-endpoint` - Scaffold new API endpoint
