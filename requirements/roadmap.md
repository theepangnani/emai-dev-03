## 8. Phased Roadmap

### Phase 1 (MVP) - CURRENT
- [x] Google Classroom integration (on-demand only)
- [x] Parent & Student dashboards
- [x] AI study tools (guides, quizzes, flashcards)
- [x] Secure parent-teacher messaging
- [x] Notification system (in-app + email reminders)
- [x] Teacher email monitoring (Gmail + Classroom announcements)
- [x] Role-based dashboards (Student, Parent, Teacher, Admin)
- [x] Parent-child linking (by email + Google Classroom discovery)
- [x] File upload with content extraction
- [x] Logging framework
- [x] Many-to-many parent-student relationship (migrate from single parent_id)
- [x] Parent registers child from Parent Dashboard (via invite flow)
- [x] Student invite email flow (set password via invite link)
- [x] Update parent linking endpoints for many-to-many
- [x] Auto-create Teacher record at registration
- [x] Shadow + invite flow for non-EMAI school teachers
- [x] Teacher type distinction (school_teacher vs private_tutor)
- [x] Unified invite system (shared invites table for student + teacher invites)
- [x] Teacher Google Classroom course sync (set teacher_id on synced courses)
- [x] Parent-student-Google sync flow (onboarding banner, parent-triggered sync, teacher info)
- [x] Study guide storage limits (100/student, 200/parent, configurable)
- [x] Study guide versioning and duplicate detection
- [x] Course-labeled study guide categorization
- [x] Role-based study guide visibility
- [x] Study guide list/management UI for parents and students
- [x] Study guide course assignment (PATCH endpoint + CourseAssignSelect component)
- [x] **Parent Dashboard calendar-centric redesign (v1)** — calendar views (Day/3-Day/Week/Month), action bar, sidebar, course color-coding, assignment popover
- [x] **Parent Dashboard v2: Left navigation** — move Add Child, Add Course, Create Study Guide, Add Task to DashboardLayout left nav; compact header padding (IMPLEMENTED)
- [x] **Parent Dashboard v2: Child filter toggle** — click/unclick child tabs; "All" mode merges all children's data + parent tasks; child-name labels in All mode (IMPLEMENTED)
- [x] **Parent Dashboard v2: Edit Child modal** — edit child details, manage course assignments, setup reminders (IMPLEMENTED)
- [x] **Parent Dashboard v2: Day Detail Modal** — click date to open modal with CRUD for all tasks/assignments on that date (IMPLEMENTED)
- [x] **Parent Dashboard v2: Dedicated Courses page** — `/courses` route with full CRUD, multi-child assignment, study guide creation from course (IMPLEMENTED)
- [x] **Parent Dashboard v2: Dedicated Study Guides page** — `/study-guides` route with full CRUD, course assignment, filtering (IMPLEMENTED)
- [x] **Task system: Backend** — `tasks` table, CRUD API endpoints (`/api/tasks/`), cross-role assignment (IMPLEMENTED)
- [x] **Task system: Frontend** — Dedicated Tasks page, task entries on calendar, task editing (IMPLEMENTED)
- [x] **Task system: Calendar integration** — tasks appear alongside assignments on calendar, Day Detail Modal with sticky note cards (IMPLEMENTED)
- [x] **Task archival** — Soft-delete, restore, permanent delete, auto-archive on completion (IMPLEMENTED)
- [x] **Calendar sticky notes** — Priority-colored task cards with expandable details in Day Detail Modal (IMPLEMENTED)
- [x] **Study guide formatting** — Markdown rendering with GFM support for study guide view (IMPLEMENTED)
- [x] **Task status filters fix** — Task dropdown filters on Tasks page working correctly (IMPLEMENTED)
- [x] **Calendar drag-and-drop** — Drag tasks to reschedule due dates in month/week views with optimistic UI (IMPLEMENTED)
- [x] **Calendar child filter fix** — Tasks now properly filtered by selected child in calendar view (IMPLEMENTED)
- [x] **Course page CTA** — Create Course entry point added to Courses page (IMPLEMENTED)
- [x] **Tasks page modal** — Create New Task converted to well-formatted modal (IMPLEMENTED)
- [x] **Task entity linking** — Link tasks to courses, course content, and study guides; +Task buttons on Study Guides and Course Detail pages; reusable CreateTaskModal; linked entity badges on Tasks page (IMPLEMENTED)
- [x] **Study guide conversion** — Convert existing study guides to quizzes or flashcards from Study Guides list page (IMPLEMENTED)
- [x] **Duplicate study guide prevention** — useRef guards on frontend + 60-second backend dedup via content_hash (IMPLEMENTED)
- [x] **AI generation confirmations** — All AI generation actions require user confirmation dialog before API call (IMPLEMENTED)
- [x] **Robust AI response parsing** — Strip markdown code fences from AI JSON responses to prevent parse failures (IMPLEMENTED)
- [x] **Clickable entity badges** — Task linked entity badges navigate to study guide/quiz/flashcards/course detail page on click (IMPLEMENTED)
- [x] **Non-blocking AI generation** — Study material generation closes modal immediately, shows pulsing placeholder in list, generates in background; works from Study Guides page and Parent Dashboard (IMPLEMENTED)
- [x] **Calendar quick-action buttons** — "+ Create Study Guide" and "View Study Guides" buttons above calendar on Parent Dashboard (IMPLEMENTED)
- [x] **Fix users.email nullable in PostgreSQL** — Startup migration to DROP NOT NULL on users.email for parent-created child accounts without email (IMPLEMENTED)
- [x] **Styled confirmation modals** — Replace all 13 native `window.confirm()` calls with custom ConfirmModal component; promise-based useConfirm hook; danger variant for destructive actions; consistent app-styled design across all pages (IMPLEMENTED)
- [x] **Lazy chunk retry on deploy** — `lazyRetry()` wrapper around `React.lazy()` catches stale chunk 404s after deployment and auto-reloads once (sessionStorage guard prevents infinite loops) (IMPLEMENTED)
- [x] **Course materials restructure** — Refactor Study Guides page to list course materials (course_contents) with tabbed detail view (Original Document / Study Guide / Quiz / Flashcards); add `course_content_id` FK to study_guides; parent child+course filters; default "My Materials" course per user (IMPLEMENTED)
- [x] **Audit logging** — `audit_logs` table with admin API and UI; logs login, register, task CRUD, study guide CRUD, course CRUD, message send, parent child access, Google sync; configurable retention (IMPLEMENTED)
- [x] **Task Detail Page** — Dedicated `/tasks/:id` page with info card, actions, linked resources; `GET /api/tasks/{task_id}` endpoint; clickable task titles in calendar popover (IMPLEMENTED)
- [x] **Task Detail Page: Link/unlink resources** — Icon buttons to link course, material, or study guide; searchable tabbed modal; unlink (×) button on each resource card; fixed `tasksApi.update()` type signature (IMPLEMENTED)
- [x] **Task Detail Page: Inline edit mode (#210)** — Edit button toggles task card into inline form with title, description, due date, priority, and assignee fields; responsive layout; Save/Cancel with loading state (IMPLEMENTED)
- [x] **Calendar task popover: See Task Details button** — Icon buttons in popover (clipboard=task details, book=create study guide, graduation cap=go to course, books=view study guides) with title tooltips; fixed task ID offset bug where navigation used calendar-internal offset ID instead of real task ID (IMPLEMENTED)
- [x] **Ungrouped study guide categorization** — Folder icon button on ungrouped guides opens "Move to Course" modal with searchable course list and inline "Create new course" option; backend PATCH auto-creates CourseContent via ensure_course_and_content() (IMPLEMENTED)
- [x] **Theme system with Light/Dark/Focus modes** — 50+ CSS custom properties, ThemeContext with useTheme() hook, ThemeToggle in header, OS preference auto-detection, localStorage persistence (IMPLEMENTED)
- [x] **Color theme system: Hardcoded color cleanup** — Converted hardcoded hex/rgba values to CSS variables across all CSS files (IMPLEMENTED)
- [x] **Color theme system: Dark mode** — Deep dark palette with purple glow in `[data-theme="dark"]`, ThemeContext, ThemeToggle in header (IMPLEMENTED)
- [x] **Color theme system: Focus mode** — Warm muted tones in `[data-theme="focus"]` for study sessions (IMPLEMENTED)
- [ ] **Flat (non-gradient) default style** — Replace 30+ gradient declarations across 13 CSS files with solid accent colors; make flat the default, gradient opt-in (#486, #487)
- [ ] **Mobile: Remove gradient from login button** — Replace expo-linear-gradient with solid colors.primary (#488)
- [ ] **Gradient/flat style toggle** — Optional `[data-style="gradient"]` for users who prefer gradients; ThemeContext extension (#489, low priority)
- [x] **Make student email optional** — parent can create child with name only (no email, no login) (IMPLEMENTED)
- [x] **Parent creates child** endpoint (`POST /api/parent/children/create`) — name required, email optional (IMPLEMENTED)
- [x] **Parent creates courses** — allow PARENT role to create courses (private to their children) (IMPLEMENTED)
- [x] **Parent assigns courses to children** — `POST /api/parent/children/{student_id}/courses` (IMPLEMENTED)
- [x] **Student creates courses** — allow STUDENT role to create courses (visible to self only) (IMPLEMENTED)
- [x] **Add `created_by_user_id` and `is_private` to Course model** (IMPLEMENTED)
- [x] **Disable auto-sync jobs by default** — all Google Classroom/Gmail sync is manual, on-demand only (IMPLEMENTED)
- [x] **Multi-role support Phase A** — `roles` column, role switcher, ProtectedRoute checks all roles (#211) (IMPLEMENTED)
- [x] **Security hardening Phase 2** — Rate limiting, security headers, LIKE injection fix (#140, #141, #184) (IMPLEMENTED)
- [x] **Task reminders** — Daily in-app notifications for upcoming task due dates (#112) (IMPLEMENTED)
- [x] **Password reset flow** — Email-based JWT token reset with forgot-password UI (#143) (IMPLEMENTED)
- [x] **Course materials lifecycle** — Soft delete, archive, retention policies, auto-archive (#212) (IMPLEMENTED)
- [x] **Message email notifications** — Email on new message with dedup (#213) (IMPLEMENTED)
- [x] **Parent-to-teacher linking** — Manual link via MyKidsPage, email notifications (#219-#224, #234, #235) (IMPLEMENTED)
- [x] **Teacher course roster management** — Add/remove students, assign teacher by email (#225-#227) (IMPLEMENTED)
- [x] **Manual assignment CRUD** — Teachers create/edit/delete assignments on CourseDetailPage (#49) (IMPLEMENTED)
- [x] **My Kids page** — Dedicated parent page with child cards, sections, teacher linking (#236, #237) (IMPLEMENTED)
- [x] **JWT token refresh** — Auto-refresh on 401 with 30-day refresh tokens (#149) (IMPLEMENTED)
- [x] **Loading skeletons** — Animated skeleton screens for all major pages (#150, #218) (IMPLEMENTED)
- [x] **Mobile responsive CSS** — Breakpoints for 5+ pages (#152) (IMPLEMENTED)
- [x] **Backend test expansion** — 288+ route tests (#155) (IMPLEMENTED)
- [x] **Inspirational messages** — Role-based dashboard greetings with admin CRUD (#230-#233) (IMPLEMENTED)
- [x] **My Kids visual overhaul** — Colored avatars, task progress bars, next-deadline countdowns, quick action buttons (#301) (IMPLEMENTED)
- [ ] Manual course creation for teachers
- [ ] Manual assignment creation for teachers
- [ ] Multi-Google account support for teachers
- [ ] Auto-send invite email to shadow teachers on creation
- [ ] Teacher Dashboard course management view with source badges
- [x] **Admin broadcast messaging** — Send message + email to all users (#258) (IMPLEMENTED)
- [x] **Admin individual messaging** — Send message + email to specific user (#259) (IMPLEMENTED)
- [ ] **Inspirational messages in emails** — Add role-based inspiration quotes to all outgoing emails (#260)
- [ ] **Simplified registration** — Remove role selection from signup form, collect only name/email/password (#412)
- [ ] **Post-login onboarding** — Role selection + teacher type after first login (#413, #414)
- [ ] **Welcome email on registration** — Branded welcome email with feature highlights sent after signup (#509)
- [ ] **Verification acknowledgement email** — Marketing email with feature showcase sent after email verification (#510)
- [x] **Parent Dashboard v3: Persistent sidebar** — Replace hamburger with always-visible sidebar on desktop (#541) (IMPLEMENTED — PR #545)
- [x] **Parent Dashboard v3: Alert banner + child pills** — Unified alert banner (overdue/invites/messages) + single child filter pills replacing redundant tabs and cards (#542) (IMPLEMENTED — PR #545)
- [x] **Parent Dashboard v3: Quick Actions + Student Detail Panel** — Always-visible action bar (+ Material, + Task, + Child, + Course) + urgency-grouped tasks panel per child (#543) (IMPLEMENTED — PR #545)
- [x] **Parent Dashboard v3: Calendar default collapsed + cleanup** — Calendar defaults to collapsed; delete dead ParentSidebar/ParentActionBar code; fix #536 (#544) (IMPLEMENTED — PR #545)

#### Phase 1 New Workflow (§6.51) — #546-#552
- [x] **Phase 0 Foundation** — Models, migrations, notification service, schemas (IN PROGRESS)
- [ ] **Student registration with username + parent email** — Username login, parent linking on register (#546)
- [ ] **Parent-Student LinkRequest approval** — Bidirectional approval workflow for linking (#547)
- [ ] **Multi-channel notifications + ACK** — In-app + email + message, persistent reminders, suppress (#548)
- [ ] **Parent request assignment completion** — Parent requests student complete assignment (#549)
- [ ] **Google Classroom school vs private** — classroom_type, download restriction (#550)
- [ ] **Student/teacher invites + course enrollment** — Student invite teacher, teacher invite student/parent (#551)
- [ ] **Upload with AI tool selection** — AI tool dropdown during upload, custom prompt (#552)

#### Architecture Foundation (Tier 0)
- [ ] **Split api/client.ts** — Break 794-LOC monolith into domain-specific API modules (#127)
- [ ] **Extract backend services** — Move business logic from route handlers to domain service layer (#128)
- [ ] **Repository pattern** — Introduce data access layer abstracting SQLAlchemy queries (#129)
- [x] **Split ParentDashboard** — Break 1222-LOC component into composable sub-components (#130) (PARTIAL — extracted AlertBanner, StudentDetailPanel, QuickActionsBar; ~1494 LOC remains in ParentDashboard but logic is delegated to sub-components)
- [ ] **Activate TanStack Query** — Replace manual useState/useEffect data fetching with React Query hooks (#131)
- [ ] **Backend DDD modules** — Reorganize into bounded context directories (#132)
- [ ] **Frontend DDD modules** — Reorganize into domain directories (#133)
- [ ] **Domain events** — Add event system for cross-context communication (#134)

#### Security & Hardening (Tier 0)
- [ ] **Authorization gaps** — `list_students()` returns ALL students to any auth user; `get_user()` has no permission check; `list_assignments()` not filtered by course access (#139)
- [ ] **Rate limiting** — No rate limiting on AI generation, auth, or file upload endpoints; risk of brute force and API quota abuse (#140)
- [x] **CORS hardening** — ~~Currently allows `*` origins; tighten to known frontend domains (#64)~~ ✅ Fixed in #177
- [ ] **Security headers** — Add X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security, CSP (#141)
- [ ] **Input validation** — Missing field length limits, URL validation, and sanitization on multiple endpoints (#142)
- [x] **Password reset flow** — Forgot Password link + email-based reset (#143) — see §6.26

#### Data Integrity & Performance (Tier 0)
- [ ] **Missing database indexes** — Add indexes on StudyGuide(assignment_id), StudyGuide(user_id, created_at), Task(created_by_user_id, created_at), Invite(email, expires_at), Message(conversation_id) (#73)
- [x] **N+1 query patterns** — ~~`_task_to_response()` does 3-4 extra queries per task; `list_children()` iterates students; assignment reminder job loads all users individually (#144)~~ ✅ Fixed with selectinload/batch-fetch in tasks.py, messages.py, parent.py (#241)
- [x] **CASCADE delete rules** — ~~Task, StudyGuide, Assignment FKs lack ON DELETE CASCADE/SET NULL; orphaned records possible (#145)~~ ✅ Fixed in #187
- [x] **Unique constraint on parent_students** — ~~No unique constraint on (parent_id, student_id); duplicate links possible (#146)~~ ✅ Fixed in #187

#### Frontend UX Gaps (Tier 1)
- [x] **Global error boundary** — React ErrorBoundary wraps all routes; catches render errors with Try Again / Reload Page (#147) ✅
- [x] **Toast notification system** — Global ToastProvider with success/error/info types, auto-dismiss, click-to-dismiss (#148) ✅
- [ ] **Token refresh** — JWT tokens expire without refresh mechanism; users lose work and get silently redirected to login (#149)
- [x] **Loading skeletons** — Reusable Skeleton components (Page, Card, List, Detail) replace Loading... text across 12 pages (#150) ✅
- [x] **Accessibility (A11Y)** — ARIA labels on icon buttons, keyboard navigation for interactive elements, skip-to-content link, focus indicators (#151, #247) ✅ (IMPLEMENTED - Feb 2026, commit 120e065)
- [ ] **Mobile responsiveness** — Calendar not optimized for mobile; tables don't scroll; modals overflow on small screens; no touch drag-drop (#152)
- [x] **FlashcardsPage stale closure bug** — Fixed with useRef-based stable keyboard event handler (#153) ✅

#### Testing Gaps (Tier 1)
- [x] **Frontend unit tests** — 258 tests across 18 files (vitest) (#154) ✅
- [ ] **Missing route tests** — No tests for: google_classroom, study, messages, notifications, teacher_communications, admin, invites, course_contents routes (#155)
- [ ] **PostgreSQL test coverage** — Tests run on SQLite only; misses NOT NULL, Enum, and type divergences (e.g., users.email bug) (#156)

### Phase 1.5 (Calendar Extension, Content, Mobile & School Integration)
- [ ] Mobile-responsive web application (fix CSS gaps, breakpoints, touch support)
- [ ] Student email identity merging (personal + school email on same account)
- [ ] School board email integration (when DTAP approved)
- [ ] Extend calendar to Student and Teacher dashboards with role-aware data
- [ ] Google Calendar push integration (sync tasks/reminders to Google Calendar)
- [ ] Central document repository
- [x] Manual content upload with OCR (enhanced) — #523 ✅
- [ ] Background periodic Google Classroom course/assignment sync for teachers (opt-in)

#### Parent UX Simplification (Phase 1.5)
- [x] Issue #201: Parent UX: Single dashboard API endpoint ✅
- [x] Issue #202: Parent UX: Status-first dashboard ✅
- [x] Issue #203: Parent UX: One-click study material generation ✅
- [x] Issue #204: Parent UX: Fix filter cascade on Course Materials page ✅
- [x] Issue #205: Parent UX: Reduce modal nesting ✅
- [x] Issue #206: Parent UX: Parent navigation — restored Courses & Course Materials to sidebar (#529, #530) ✅
- [x] Issue #207: Parent Dashboard: Collapsible/expandable calendar section (IMPLEMENTED — defaults to collapsed, #544)

### Phase 2
- [ ] TeachAssist integration
- [x] **Performance Analytics Dashboard** — Grade tracking, trends, AI insights, weekly reports (#469-#474) — IMPLEMENTED
- [ ] Advanced notifications
- [ ] Notes & project tracking tools
- [ ] Data privacy & user rights (account deletion, data export, consent)
- [ ] **FAQ / Knowledge Base** — Community-driven Q&A with admin approval (#437-#444)
- [ ] **Admin email template management** — View, edit, preview, and reset email templates from Admin Dashboard (#513)
- [ ] **Broadcast history reuse & resend** — View full broadcast details, reuse as template, resend to all users (#514)
- [ ] **Course Materials Storage** — GCS-based persistent file storage for uploaded materials; signed URLs, per-user quotas, lifecycle policies (#572)
- [x] **Quiz Results History** — Persist quiz attempts with per-question answers; track retries, score trends, child selector for parents. Inline quiz save from Course Material detail page + dedicated Quiz page. View History link on quiz completion. (#574, #621)
- [ ] **User-Provided AI API Key (BYOK)** — Users bring their own OpenAI key; encrypted storage, seamless fallback to platform key (#578)
- [ ] **Study Guide Repository & Reuse** — Cross-student dedup via content hashing + fuzzy matching; shared study guide pool saves 67% AI costs (#573)
- [ ] **Student Progress Analysis** — Upload graded tests (photo/PDF), OCR score extraction, manual mark entry, AI recommendations (#575)
- [ ] **Sample Exams/Tests Upload** — Teacher uploads with AI difficulty assessment, topic coverage, curriculum alignment, practice mode (#577)
- [ ] **Parent AI Insights** — Student interest profiling, academic health score, semester reports, engagement analysis (#581)

#### 6.28 FAQ / Knowledge Base (Phase 2)

Community-driven help center where users ask questions, provide answers, and admins curate approved content.

**Data Model:**
- `faq_questions` — User-submitted questions with category, status (open/answered/closed), optional error_code mapping, is_pinned, view_count, soft delete
- `faq_answers` — Answers to questions with admin approval workflow (pending → approved/rejected), is_official flag, reviewer audit trail

**Categories:** getting-started, google-classroom, study-tools, account, courses, messaging, tasks, other

**Core Behaviors:**
- All authenticated users can browse FAQ, ask questions, and submit answers
- Submitted answers are **hidden from non-admin users** until approved by an admin
- Admin approval workflow: admins see pending queue, approve/reject with one click, author notified of outcome
- Admin can pin important questions (appear first), mark answers as official/accepted
- Admin can create "official FAQ" entries (auto-approved Q+A in one shot)
- Global search (Ctrl+K) includes FAQ questions alongside courses, tasks, and materials
- Error-to-FAQ references: backend errors can include a `faq_code` that maps to a FAQ entry; frontend shows contextual "Need help? See FAQ" link
- Markdown rendering for answer content (reuse existing ReactMarkdown)
- Seed 10-15 initial how-to entries before launch

**API Endpoints:**
- Public: `GET/POST /api/faq/questions`, `GET/PATCH/DELETE /api/faq/questions/{id}`, `POST /api/faq/questions/{id}/answers`, `PATCH /api/faq/answers/{id}`
- Admin: `GET /api/faq/admin/pending`, `PATCH /api/faq/admin/answers/{id}/approve|reject|mark-official`, `PATCH /api/faq/admin/questions/{id}/pin`, `POST /api/faq/admin/questions`
- Search: `GET /api/search?types=faq`
- Error hint: `GET /api/faq/by-error-code/{code}`

**Frontend Pages:**
- `/faq` — List page with search, category filters, pinned-first ordering
- `/faq/:id` — Detail page with approved answers, submit answer form
- `/admin/faq` — Admin approval queue + question management

**GitHub Issues:** #437 (models), #438 (schemas), #439 (API routes), #440 (search), #441 (error references), #442 (frontend), #443 (tests), #444 (seed data)

### Phase 2 (Mobile App — March 6 Pilot MVP) - IN PROGRESS

See §9 Mobile App Development for detailed specification.

**Status:** Parent-only MVP complete (8 screens built). Device testing and pilot launch pending.

**Approach:** Lightweight parent-only mobile app for March 6, 2026 pilot. No backend API changes needed — mobile calls the same `/api/*` endpoints as the web frontend. Distributed via Expo Go (no App Store/Play Store submission for pilot).

**Timeline:** 2 weeks (Feb 15 - Mar 5, 2026)
- Week 1 (Feb 15-21): Foundation + all 8 screens ✅
- Week 2 (Feb 22-28): Polish + device testing
- Mar 1-5: Final testing + pilot prep

**Deliverables:**
- [x] Mobile app foundation (Expo SDK 54, React Native 0.81.5, TypeScript)
- [x] API client with AsyncStorage token management + refresh interceptor
- [x] Auth context + login screen
- [x] Navigation (auth-gated stack + bottom tabs)
- [x] 8 parent screens: Dashboard, Child Overview, Calendar, Messages List, Chat, Notifications, Profile
- [x] UI polish: pull-to-refresh, tab bar badges, empty states, loading spinners
- [ ] Device testing (iOS + Android via Expo Go)
- [ ] Pilot launch (March 6)

**Deferred to Phase 3+ (post-pilot):**
- Push notifications (Firebase) — Issues #314-#318, #334-#335
- API versioning — Issue #311 (not needed when you control both clients)
- File uploads — Issues #319-#320, #333
- App Store / Play Store submission — Issues #343-#346
- Student & teacher mobile screens — Issues #379-#380
- Offline mode — Issue #337

**GitHub Issues:** #364-#380 (pilot MVP + post-pilot)

### Phase 2+ (AI Intelligence & Data Platform) — #571-#581

New features that deepen ClassBridge's AI capabilities, build a data foundation for student insights, and reduce platform costs.

| # | Feature | Issue | Phase | Value Add | Dependencies |
|---|---------|-------|-------|-----------|-------------|
| 1 | **Ontario Curriculum Management** | #571 | 2→3 | **Strategic** — Enables curriculum-aligned analytics, gap analysis, and exam prep. Foundation for Course Planning (Phase 3). Differentiates ClassBridge from generic education tools by being Ontario-specific. | #500, #114 |
| 2 | **Course Materials Storage** | #572 | 2 | **Infrastructure** — Prerequisite for file reuse, download, and audit. Without persistent storage, users re-upload constantly. Unlocks Study Guide Repository and test upload features. GCS is 8-10x cheaper than DB BLOBs. | #114 |
| 3 | **Study Guide Repository & Reuse** | #573 | 2 | **Cost Savings** — Eliminates redundant AI calls when 30 students in the same class upload the same handout. Estimated 67% reduction in AI generation costs at scale (~$1,000/yr savings per 1,000 users). | #572 |
| 4 | **Quiz Results History** | #574 | 2 | **Core Learning** — ~~Currently quizzes are stateless (results lost on page close).~~ IMPLEMENTED (#621): Quiz results persisted, retry tracking, score trends, parent child selector, inline + dedicated quiz save. | Analytics §6.5 |
| 5 | **Student Progress Analysis (Test Uploads)** | #575 | 2 | **Parent Engagement** — Makes ClassBridge the single source of truth for ALL grades (not just Google Classroom). Parents can photograph paper tests and track everything in one place. Critical for schools without Google Classroom. | #572, Analytics §6.5 |
| 6 | **Exam Preparation Engine** | #576 | 2→3 | **Student Outcomes** — Directly impacts academic performance by creating personalized prep plans. Connects curriculum + quiz history + test records into actionable study plans. High perceived value for parents evaluating the platform. | #571, #574, #575 |
| 7 | **Sample Exams/Tests Upload + AI Assessment** | #577 | 2 | **Teacher Engagement** — Gives teachers a reason to use ClassBridge actively (not just passively). AI assessment of exam quality is unique — helps teachers improve their assessments. Practice mode drives student engagement. | #572, #574 |
| 8 | **User-Provided AI API Key (BYOK)** | #578 | 2 | **Cost Sustainability** — Shifts AI costs from platform to power users. Essential for scaling beyond 500 users without unsustainable API bills. Common pattern in AI SaaS. Low effort, high impact on unit economics. | None |
| 9 | **Parent AI Insights** | #581 | 2→3 | **Premium Differentiator** — The "wow factor" feature. Parents see a holistic view of their child's trajectory, interests, and actionable guidance. Drives retention and word-of-mouth. Could be a premium/paid tier feature. | #574, #575, #571 |

**Recommended implementation order:**
1. **#572** Course Materials Storage (infrastructure prerequisite)
2. **#574** Quiz Results History (core data — feeds everything else)
3. **#578** BYOK AI Key (quick win — reduces costs immediately)
4. **#573** Study Guide Repository (cost savings)
5. **#575** Student Progress Analysis (parent engagement)
6. **#577** Sample Exams Upload (teacher engagement)
7. **#571** Ontario Curriculum (strategic, feeds Phase 3)
8. **#581** Parent AI Insights (premium differentiator, needs data from #574 + #575)
9. **#576** Exam Prep Engine (capstone — combines all data sources)

### Phase 3 (Course Planning & Guidance)
- [ ] **Ontario Curriculum Management** — Download, parse, and serve Ontario curriculum data; curriculum-aligned analytics and AI anchoring (#571)
- [ ] **Exam Preparation Engine** — AI-powered personalized prep plans combining curriculum + quiz history + test records (#576)
- [ ] **School Board Integration** — Board-specific course catalogs, student ↔ board linking, board selection in Edit Child modal; seed 5 Ontario boards (TDSB, PDSB, YRDSB, HDSB, OCDSB) (#511, depends on #113)
- [ ] **Course Catalog Model** — Board-scoped high school course database with prerequisites, credits, grade levels, subject areas, streams, specialized programs (IB/AP/SHSM); seed per-board Ontario OSSD courses (#500)
- [ ] **Academic Plan Model** — Multi-year course plan per student (Grade 9-12) with semester breakdown, planned/in-progress/completed statuses; parent + student CRUD with RBAC (#501)
- [ ] **Prerequisite & Graduation Requirements Engine** — Validate plans against OSSD rules (30 credits, 18 compulsory), prerequisite chain checks, completion scoring, gap detection (#502)
- [ ] **AI Course Recommendations** — Board-specific personalized guidance using student grades, goals, and analytics; on-demand generation (gpt-4o-mini); pathway analysis and risk alerts (#503)
- [ ] **Semester Planner UI** — Course selection per semester with prerequisite indicators, credit counter, workload balance, real-time validation (#504)
- [ ] **Multi-Year Planner UI** — Visual Grade 9-12 grid with course cards, prerequisite arrows, subject color coding, graduation progress dashboard, drag-and-drop (#505)
- [ ] **University Pathway Alignment** — Map plans to post-secondary program admission requirements; gap analysis, multi-program comparison; seed top Ontario university programs (#506)
- [ ] **Course Planning Navigation & Dashboard Integration** — Nav links, landing page, My Kids integration, Parent Dashboard quick actions (#507)
- [ ] **Course Planning Tests** — 20+ backend route tests, 10+ frontend component tests (#508)
- [ ] Multi-language support
- [ ] Advanced AI personalization
- [ ] Admin analytics

### Phase 4 (Tutor Marketplace)
- [ ] Private tutor profiles (availability, rates, subjects)
- [ ] Parent/student tutor search and discovery
- [ ] AI tutor matching
- [ ] Booking workflow
- [ ] Ratings & reviews
- [ ] Payment integration

### Phase 5 (AI Email Agent)
- [ ] AI email sending
- [ ] Reply ingestion
- [ ] AI summaries
- [ ] Searchable archive

---

