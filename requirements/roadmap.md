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
- [x] **Calendar drag-and-drop** — Drag tasks to reschedule due dates in month/week views with optimistic UI; touch DnD in week/3-day views (#859) (IMPLEMENTED)
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
- [x] **Flat (non-gradient) default style** — Replace 30+ gradient declarations across 13 CSS files with solid accent colors; make flat the default, gradient opt-in (#486, #487) (IMPLEMENTED)
- [x] **Mobile: Remove gradient from login button** — Replace expo-linear-gradient with solid colors.primary (#488) (IMPLEMENTED)
- [x] **Gradient/flat style toggle** — Optional `[data-style="gradient"]` for users who prefer gradients; ThemeContext extension (#489) (IMPLEMENTED)
- [x] **Make student email optional** — parent can create child with name only (no email, no login) (IMPLEMENTED)
- [x] **Parent creates child** endpoint (`POST /api/parent/children/create`) — name required, email optional (IMPLEMENTED)
- [x] **Parent creates courses** — allow PARENT role to create courses (private to their children) (IMPLEMENTED)
- [x] **Parent assigns courses to children** — `POST /api/parent/children/{student_id}/courses` (IMPLEMENTED)
- [x] **Student creates courses** — allow STUDENT role to create courses (visible to self only) (IMPLEMENTED)
- [x] **Add `created_by_user_id` and `is_private` to Course model** (IMPLEMENTED)
- [x] **Disable auto-sync jobs by default** — all Google Classroom/Gmail sync is manual, on-demand only (IMPLEMENTED)
- [x] **Multi-role support Phase A** — `roles` column, role switcher, ProtectedRoute checks all roles (#211) (IMPLEMENTED)
- [x] **Security hardening Phase 2** — Rate limiting, security headers, LIKE injection fix (#140, #141, #184) (IMPLEMENTED)
- [x] **Multi-file OCR rate limit fix (#1003)** — `/upload/extract-text` rate limit raised from 5→30/min; frontend switched from concurrent `Promise.all()` to sequential processing to prevent 429 errors on multi-file uploads (IMPLEMENTED, PR #1004)
- [x] **Task reminders** — Daily in-app notifications for upcoming task due dates (#112) (IMPLEMENTED)
- [x] **Password reset flow** — Email-based JWT token reset with forgot-password UI (#143) (IMPLEMENTED)
- [x] **Enhanced password management** — OAuth/invite users can use forgot-password; parents can reset child passwords from My Kids (#673) (IMPLEMENTED)
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
- [x] **Manual course creation for teachers** — Teachers can create courses (#42) (IMPLEMENTED)
- [x] **Manual assignment creation for teachers** — Covered by manual assignment CRUD (#49) (IMPLEMENTED)
- [x] Multi-Google account support for teachers — TeacherGoogleAccount model, connect/list/label/delete/set-primary endpoints, multi-account course sync via account_id param, inline label editing in TeacherDashboard (IMPLEMENTED)
- [x] Auto-send invite email to shadow teachers on creation (#946) (IMPLEMENTED — Phase 1.5)
- [x] Teacher Dashboard course management view with source badges (#947) (IMPLEMENTED — Phase 1.5)
- [x] **Admin broadcast messaging** — Send message + email to all users (#258) (IMPLEMENTED)
- [x] **Admin individual messaging** — Send message + email to specific user (#259) (IMPLEMENTED)
- [x] **Inspirational messages in emails** — Add role-based inspiration quotes to all outgoing emails (#260) (IMPLEMENTED)
- [x] **Simplified registration** — Remove role selection from signup form, collect only name/email/password (#412) (IMPLEMENTED — Phase 1.5)
- [x] **Post-login onboarding** — Role selection + teacher type after first login (#413, #414) (IMPLEMENTED)
- [x] **Welcome email on registration** — Branded welcome email with feature highlights sent after signup (#509) (IMPLEMENTED)
- [x] **Verification acknowledgement email** — Marketing email with feature showcase sent after email verification (#510) (IMPLEMENTED)
- [x] **Parent Dashboard v3: Persistent sidebar** — Replace hamburger with always-visible sidebar on desktop (#541) (IMPLEMENTED — PR #545)
- [x] **Parent Dashboard v3: Alert banner + child pills** — Unified alert banner (overdue/invites/messages) + single child filter pills replacing redundant tabs and cards (#542) (IMPLEMENTED — PR #545)
- [x] **Parent Dashboard v3: Quick Actions + Student Detail Panel** — Always-visible action bar (+ Material, + Task, + Child, + Course) + urgency-grouped tasks panel per child (#543) (IMPLEMENTED — PR #545)
- [x] **Parent Dashboard v3: Calendar default collapsed + cleanup** — Calendar defaults to collapsed; delete dead ParentSidebar/ParentActionBar code; fix #536 (#544) (IMPLEMENTED — PR #545)
- [x] **Calendar moved to Tasks page** — Calendar section relocated from Parent Dashboard to Tasks page for better contextual relevance (#691, PR `a35a329`) (IMPLEMENTED)
- [x] **+ icon popover pattern** — Replace standalone action buttons with a shared `AddActionButton` component across Dashboard (#692), Tasks (#692), My Kids (#700), and Course Material Detail (#698) pages (IMPLEMENTED — PRs #693, #699, #701)
- [x] **Remove "All Kids" from child selector** — Toggle-deselect replaces explicit "All" button (#688) (IMPLEMENTED)
- [x] **Tasks page layout improvements** — Consistent button layout, vertical filter alignment, edit icon on hover, consolidated edit/delete into modal (#686-#690) (IMPLEMENTED)
- [x] **Course Material Detail back button** — Add `showBackButton` to DashboardLayout on Course Material Detail page (#696, PR #697) (IMPLEMENTED)
- [x] **Calendar styles fix on Tasks page** — Copy calendar-collapse CSS from ParentDashboard.css to TasksPage.css after Calendar move (#694, PR #695) (IMPLEMENTED)
- [x] **Print & Download PDF export** — Print and Download PDF buttons on all 4 Course Material Detail tabs (Document, Study Guide, Quiz, Flashcards); html2pdf.js dynamic import; static print views for quiz/flashcards (#764, PR #763) (IMPLEMENTED)
- [x] **Focus prompt history + content moderation** — Persist `focus_prompt` on study guide records; pre-populate focus field from last saved focus on Course Material Detail; Claude Haiku K-12 safety check on all generation paths (#1001) (IMPLEMENTED — PR #1002)
- [x] **File upload security hardening** — Reduce per-file limit to 20 MB (configurable via `MAX_UPLOAD_SIZE_MB`), magic bytes validation to prevent extension spoofing, 10-file session cap in upload modal (#1006) (IMPLEMENTED)

#### Phase 1 New Workflow (§6.51) — #546-#552
- [x] **Phase 0 Foundation** — Models, migrations, notification service, schemas (IN PROGRESS)
- [x] **Student registration with username + parent email** — Username login, parent linking on register (#546) (IMPLEMENTED)
- [x] **Parent-Student LinkRequest approval** — Bidirectional approval workflow for linking (#547) (IMPLEMENTED)
- [x] **Multi-channel notifications + ACK** — In-app + email + message, persistent reminders, suppress (#548) (IMPLEMENTED)
- [x] **Parent request assignment completion** — Parent requests student complete assignment (#549) (IMPLEMENTED)
- [x] **Google Classroom school vs private** — classroom_type, download restriction (#550) (IMPLEMENTED)
- [x] **Student/teacher invites + course enrollment** — Student invite teacher, teacher invite student/parent (#551) (IMPLEMENTED)
- [x] **Upload with AI tool selection** — AI tool dropdown during upload, custom prompt (#552) (IMPLEMENTED)

#### Architecture Foundation (Tier 0)
- [x] **Split api/client.ts** — Break 794-LOC monolith into domain-specific API modules (#127) (IMPLEMENTED)
- [x] **Extract backend services** — Move business logic from route handlers to domain service layer (#128) (IMPLEMENTED)
- [x] **Repository pattern** — Introduce data access layer abstracting SQLAlchemy queries (#129) — BaseRepository[T], TaskRepository (8 methods), CourseContentRepository (8 methods), StudyGuideRepository (10 methods); tasks.py fully adopted; get_task_repo/get_course_content_repo/get_study_guide_repo deps in deps.py (IMPLEMENTED)

#### Feature Flag System
- [x] **Admin Feature Flags** — FeatureFlag model (global/tier/role/user/beta scopes); UserFeatureOverride (per-user overrides with expiry); FeatureFlagService evaluation engine with rollout % support; admin CRUD API + override management; AdminFeatureFlagsPage at /admin/feature-flags; useFeatureFlag React hook (60s cache); 8 predefined flags seeded (ai_email_agent, tutor_marketplace, lesson_planner, ai_personalization, brightspace_lms, stripe_billing, mcp_tools, beta_features) (IMPLEMENTED)
- [x] **Split ParentDashboard** — Break 1668-LOC component into composable sub-components (#130, #657) ✅ (extracted useParentDashboard hook + TodaysFocusHeader + AlertBanner + StudentDetailPanel + QuickActionsBar; ParentDashboard.tsx now 544 LOC)
- [x] **Activate TanStack Query** — Replace manual useState/useEffect data fetching with React Query hooks (#131) (IMPLEMENTED)
- [ ] **Backend DDD modules** — Reorganize into bounded context directories (#132)
- [ ] **Frontend DDD modules** — Reorganize into domain directories (#133)
- [x] **Domain events** (#134) — Lightweight synchronous in-process EventBus; DomainEvent base class; 15+ typed events (StudyGuideGenerated, QuizCompleted, SubscriptionChanged, TutorBookingRequested, LMSSyncCompleted, etc.); default handlers for cross-context reactions (quiz→mastery invalidation, subscription→onboarding, booking→notification); admin events API (recent events, stats, test publish); 15+ tests (IMPLEMENTED)

#### Security & Hardening (Tier 0)
- [x] **Authorization gaps** — `list_students()` returns ALL students to any auth user; `get_user()` has no permission check; `list_assignments()` not filtered by course access (#139) (IMPLEMENTED)
- [x] **Rate limiting** — No rate limiting on AI generation, auth, or file upload endpoints; risk of brute force and API quota abuse (#140) (IMPLEMENTED)
- [x] **CORS hardening** — ~~Currently allows `*` origins; tighten to known frontend domains (#64)~~ ✅ Fixed in #177
- [x] **Security headers** — Add X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security, CSP (#141) (IMPLEMENTED)
- [x] **Input validation** — Field length limits, whitespace stripping, URL validation on all endpoints (#142) (IMPLEMENTED — Phase 1.5)
- [x] **Password reset flow** — Forgot Password link + email-based reset (#143) — see §6.26

#### Data Integrity & Performance (Tier 0)
- [x] **Missing database indexes** — Add indexes on StudyGuide(assignment_id), StudyGuide(user_id, created_at), Task(created_by_user_id, created_at), Invite(email, expires_at), Message(conversation_id) (#73) (IMPLEMENTED in #244)
- [x] **N+1 query patterns** — ~~`_task_to_response()` does 3-4 extra queries per task; `list_children()` iterates students; assignment reminder job loads all users individually (#144)~~ ✅ Fixed with selectinload/batch-fetch in tasks.py, messages.py, parent.py (#241)
- [x] **CASCADE delete rules** — ~~Task, StudyGuide, Assignment FKs lack ON DELETE CASCADE/SET NULL; orphaned records possible (#145)~~ ✅ Fixed in #187
- [x] **Unique constraint on parent_students** — ~~No unique constraint on (parent_id, student_id); duplicate links possible (#146)~~ ✅ Fixed in #187

#### Frontend UX Gaps (Tier 1)
- [x] **Global error boundary** — React ErrorBoundary wraps all routes; catches render errors with Try Again / Reload Page (#147) ✅
- [x] **Toast notification system** — Global ToastProvider with success/error/info types, auto-dismiss, click-to-dismiss (#148) ✅
- [x] **Token refresh** — JWT tokens expire without refresh mechanism; users lose work and get silently redirected to login (#149) (IMPLEMENTED)
- [x] **Loading skeletons** — Reusable Skeleton components (Page, Card, List, Detail) replace Loading... text across 12 pages (#150) ✅
- [x] **Accessibility (A11Y)** — ARIA labels on icon buttons, keyboard navigation for interactive elements, skip-to-content link, focus indicators (#151, #247) ✅ (IMPLEMENTED - Feb 2026, commit 120e065)
- [x] **Accessibility Phase 2 (WCAG 2.1 AA)** — Priority indicator shapes, focus traps on 25+ modals, emoji aria-hidden, sr-only labels, 44px touch targets, 4.5:1 contrast (#829) ✅
- [x] **Mobile responsiveness** — Calendar not optimized for mobile; tables don't scroll; modals overflow on small screens (#152) (IMPLEMENTED)
- [x] **FlashcardsPage stale closure bug** — Fixed with useRef-based stable keyboard event handler (#153) ✅

#### Testing Gaps (Tier 1)
- [x] **Frontend unit tests** — 258 tests across 18 files (vitest) (#154) ✅
- [x] **Missing route tests** — No tests for: google_classroom, study, messages, notifications, teacher_communications, admin, invites, course_contents routes (#155) (IMPLEMENTED)
- [x] **PostgreSQL test coverage** — --pg CLI flag in conftest.py; 7 pg-specific compat tests (nullable email, enum roundtrip, LIKE injection, FK types, booleans, timestamp precision, RETURNING clause) (#156) (IMPLEMENTED)

### Phase 1.5 (Calendar Extension, Content, Mobile & School Integration)
- [x] Mobile-responsive web application (fix CSS gaps, breakpoints, touch support) (IMPLEMENTED)
- [x] Student email identity merging (personal + school email on same account) (#941) (IMPLEMENTED)
- [ ] School board email integration (when DTAP approved) (#942 — phase-1.5)
- [x] Extend calendar to Student and Teacher dashboards with role-aware data (#45) (IMPLEMENTED)
- [x] Google Calendar push integration — sync tasks to Google Calendar; GET/POST/DELETE /api/google/calendar/* endpoints; calendar hooks in task CRUD (IMPLEMENTED)
- [x] Central document repository — GET /api/documents/ with RBAC; DocumentsPage with search/filter/type tabs; Documents nav item for all roles (IMPLEMENTED)
- [x] Manual content upload with OCR (enhanced) — #523 ✅
- [x] Background periodic Google Classroom course/assignment sync for teachers (opt-in) (#53) (IMPLEMENTED)
- [x] **Input validation** — Field length limits + whitespace stripping across all endpoints (#142) (IMPLEMENTED)
- [x] **Simplified registration** — Role-free signup form (#412) (IMPLEMENTED)
- [x] **Message search** — Full-text search with pagination, date filtering, in-thread search (#836) (IMPLEMENTED)
- [x] **UI polish** — Sidebar labels, mobile quote hiding, muted active nav (#669-#671) (IMPLEMENTED)
- [x] **Course Material Detail redesign** — Page layout polish + sub-component refactor (#734, #735) (IMPLEMENTED)
- [x] **Unlinked materials tagging** — Tag and streamline parent-to-child assignment (#623) (IMPLEMENTED)
- [x] **Focus prompt behavior** — Preserve per-tab state and fix keyboard conflicts (#736) (IMPLEMENTED)
- [x] **Auto-invite shadow teachers** — 30-day debounce auto-invite email (#946) (IMPLEMENTED)
- [x] **Teacher course management** — Source badges, comprehensive view (#947) (IMPLEMENTED)

#### Parent UX Simplification (Phase 1.5)
- [x] Issue #201: Parent UX: Single dashboard API endpoint ✅
- [x] Issue #202: Parent UX: Status-first dashboard ✅
- [x] Issue #203: Parent UX: One-click study material generation ✅
- [x] Issue #204: Parent UX: Fix filter cascade on Course Materials page ✅
- [x] Issue #205: Parent UX: Reduce modal nesting ✅
- [x] Issue #206: Parent UX: Parent navigation — restored Courses & Course Materials to sidebar (#529, #530) ✅
- [x] Issue #207: Parent Dashboard: Collapsible/expandable calendar section (IMPLEMENTED — defaults to collapsed, #544)

### Phase 2
- [x] **TeachAssist Integration (#46)** — TeachAssist-compatible lesson planning tool for Ontario teachers; LessonPlan model (LRP/Unit/Daily types, 3-part lesson, Ontario curriculum expectations, assessment strategies, differentiation); AI-generate learning goals + 3-part lesson (GPT-4o-mini); TeachAssist XML/CSV import parser; LessonPlannerPage at /teacher/lesson-plans; template system (IMPLEMENTED)
- [x] **Performance Analytics Dashboard** — Grade tracking, trends, AI insights, weekly reports (#469-#474) — IMPLEMENTED
- [x] **Advanced notifications** — per-type in-app/email toggles, daily digest mode with configurable hour, NotificationPreferencesPage, digest APScheduler job (#966) — IMPLEMENTED
- [x] **Notes & project tracking tools** — Color-coded note cards (masonry grid, pinnable, linkable), Project tracker with milestone checklists and progress bars (IMPLEMENTED)
- [x] **Data privacy & user rights** — Account deletion (#964) with 30-day grace period + anonymization job, data export (#965) with JSON download, consent on feature/phase-2 (IMPLEMENTED)
- [x] **FAQ / Knowledge Base** — Community-driven Q&A with admin approval (#437-#444) (IMPLEMENTED)
- [x] **Admin email template management** — View, edit, preview, and reset email templates from Admin Dashboard (#513) (IMPLEMENTED)
- [x] **Broadcast history reuse & resend** — View full broadcast details, reuse as template, resend to all users (#514) (IMPLEMENTED)
- [x] **Course Materials Storage (#572)** — Local filesystem adapter (GCS-ready interface); FileStorageService with per-user quotas (500 MB free / 5 GB premium); StoredDocument model; GET /api/storage/files/{key} serve endpoint; storage usage + quota APIs; StorageUsageBar component in Account Settings; documents upload now persists raw files (IMPLEMENTED)
- [x] **Parent AI Insights (#581)** — Holistic child academic analysis (strengths, concerns, subject trends, learning style note, parent action items); GPT-4o-mini powered; on-demand generation; insight history; Parent Dashboard quick action widget; /insights page for parents (IMPLEMENTED)
- [x] **Quiz Results History** — Persist quiz attempts with per-question answers; track retries, score trends, child selector for parents. Inline quiz save from Course Material detail page + dedicated Quiz page. View History link on quiz completion. (#574, #621)
- [x] **User-Provided AI API Key (BYOK)** — Users bring their own OpenAI key; AES-256 encrypted storage (Fernet), seamless fallback to platform key; `/settings/account` page (#578) (IMPLEMENTED)
- [x] **Premium accounts + admin-configurable limits** — `subscription_tier` column on users; Admin Dashboard toggle; premium users get higher file size (50 MB), session (25 files), and study guide (500) limits; configurable via env vars (#1007) (IMPLEMENTED)
- [x] **Study Guide Repository & Reuse** — Cross-student dedup via content hashing + fuzzy matching; shared study guide pool saves 67% AI costs (#573) (IMPLEMENTED)
- [x] **AI Mock Exam Generator** — GPT-4o-mini generates N MCQ questions per topic/difficulty; teacher preview/edit, save, bulk-assign to students; countdown timer ExamPage with question navigator; score reveal + per-question explanation; student dashboard Assigned Exams section; `/teacher/exams` dedicated page; anti-cheat correct_index hiding (#667) (IMPLEMENTED)
- [x] **Student Progress & Report Card Analysis** — Report card upload + AI mark extraction (#663) implemented; grade entry (#665) implemented; consolidated analytics dashboard at `/progress` with quiz performance bars, teacher grade cards, report card trend, AI insights (24h cache), study streak, assignment stats, parent child-selector (#960 IMPLEMENTED — consolidated from #575, #581, #663)
- [x] **UI Polish Bundle** — Sidebar labels, mobile quote, CourseMaterial redesign (#961 — consolidated from #669-#671, #734-#735) (IMPLEMENTED — verified done in Phase 1.5 and feature/phase-2)
- [x] **Re-enable Analytics & FAQ nav links** (#962 — consolidated from #476, #479) (IMPLEMENTED)
- [x] **Admin Analytics Dashboard** — Overview stats (users/content/engagement/privacy), user growth chart (30 days), content breakdown, engagement metrics, privacy compliance summary; admin-only at /admin/analytics (IMPLEMENTED)

#### Phase 2 — On `feature/phase-2` Branch (Implemented, Not Yet in Production)
- [x] **Progressive account lockout** — 5/10/15 failed login thresholds with escalating lockout durations; admin unlock (#796)
- [x] **httpOnly cookie authentication** — Cookie-based JWT with Bearer header fallback for XSS mitigation (#788)
- [x] **Cookie consent & MFIPPA age-based consent** — CookieConsentBanner, ConsentGateway, under-16/16-17/18+ rules (#797, #783)
- [x] **Deep linking & session persistence** — URL query params for child/conversation/student; useSessionState hook (#885, #886)
- [x] **Bulk folder import** — 5-step wizard, upload progress bars, multi-file drag-and-drop (#877, #883)
- [x] **AI task extraction** — Extract tasks from uploaded documents using Claude; TaskExtractionModal (#878)
- [x] **Task templates & comments** — Reusable task templates, recurring tasks, per-task comment threads (#880, #881)
- [x] **MCP foundation** — fastapi-mcp integration with role-based tool access; 24 tests (#904, #905)
- [x] **MCP Student Academic Context Resources (#906)** — profile, assignments, study-history, weak-areas resources + get_student_summary + identify_knowledge_gaps tools (IMPLEMENTED)
- [x] **MCP Google Classroom Tools (#907)** — list courses, assignments, materials, grades, sync trigger, sync status (IMPLEMENTED)
- [x] **MCP Study Material Generation Tools (#908)** — list, get, search, generate guide/quiz/flashcards, convert; content_hash dedup; rate limiting (IMPLEMENTED)
- [x] **MCP AI Tutor Agent (#909)** — create_study_plan (auto-creates Tasks), get_study_recommendations, analyze_study_effectiveness; aggregates all student context (IMPLEMENTED)
- [x] **Message search** — Full-text search with pagination, date filtering, in-thread search (#836)
- [x] **Course Material Detail redesign** — Polished layout with sub-components (#734, #735)
- [x] **Teacher course management** — Source badges, comprehensive view (#947)
- [x] **Auto-invite shadow teachers** — 30-day debounce auto-invite (#946)

#### UI/UX Audit — Phase 1 Improvements (#668)

**Audit Report:** [design/UI_AUDIT_REPORT.md](../design/UI_AUDIT_REPORT.md)

**Tier 1 — High Impact (Sprint-ready):**
- [x] **Student Dashboard: Today's Focus header** — Urgency badges, greeting, inspiration quote (#646) ✅
- [x] **Student Dashboard: Assignment urgency sorting** — Color-coded due dates, urgency grouping (#647) ✅
- [x] **Teacher Dashboard: Activity summary** — Class activity overview, recent messages, upcoming deadlines (#648) ✅
- [x] **Auto-task after study guide generation** — Post-generation task creation prompt with pre-filled dates (#649) ✅
- [x] **Teacher Dashboard: Upload Material quick action** — Upload with course/type selection from dashboard (#650) ✅
- [x] **Student onboarding card** — Step-by-step guide for material upload from external platforms (#651) ✅

**Tier 2 — Medium Impact (Next sprint):**
- [x] **Enhanced empty states with CTAs** — Contextual actions and guidance in all empty states (#652) ✅
- [x] **Admin Dashboard: Trend indicators** — "+N this week" badges and recent activity feed (#653) ✅
- [x] **Calendar first-visit onboarding** — Expanded by default on first visit with tooltip (#654) ✅
- [x] **Filter state URL persistence** — Persist task/material/course filters in URL params (#655) ✅
- [x] **Notification center page** — "View All" page with full notification history (#656) ✅
- [x] **Refactor ParentDashboard.tsx** — Extract hook + components, 1668→544 LOC (#657) ✅
- [x] **Navigation consistency** — Standardize nav items and SVG icons across all roles (#658) ✅
- [x] **Loading state consistency** — Inline spinners, last-synced timestamps, retry buttons (#659) ✅

**Tier 3 — Polish (Backlog):**
- [x] **Micro-interactions** — Button press, card hover, section collapse animations with prefers-reduced-motion (#660) ✅
- [x] **Breadcrumb navigation** — Hierarchical trail for deep pages, mobile back-link (#661) ✅
- [x] **Mobile touch improvements** — Long-press drag, swipe navigation, modal scrolling (#662) ✅

#### Phase 2 — New Feature Requirements (#668)

- [x] **Report Card Upload & AI Analysis** — OCR extraction, trend tracking, AI observations per child per term (#663) (IMPLEMENTED)
- [x] **Parent-assigned quizzes with complexity levels** — Easy/Medium/Hard difficulty, notification + tracking (#664) IMPLEMENTED
- [x] **Teacher grade & feedback entry** — Spreadsheet-style bulk grading per student per term with feedback (#665) (IMPLEMENTED)
- [x] **Unified teacher material upload with type classification** — Notes/Test/Lab/Assignment/Report Card types (#666) IMPLEMENTED
- [x] **AI Mock Exam Generator** — Teacher generates + bulk-assigns AI-powered exams to students (#667) (IMPLEMENTED)

#### UI/UX HCD Assessment — Phase 2 Improvements (#827)

**Assessment Report:** [docs/ClassBridge_UI_UX_Assessment_Report.docx](../docs/ClassBridge_UI_UX_Assessment_Report.docx)

**Tier 1 — Critical:** ✅ COMPLETE
- [x] **Design tokens** — Expanded CSS variable system (shadows, radii, z-index, status colors for all 3 themes), replaced 150+ hard-coded values across 30 files (#828) ✅
- [x] **WCAG 2.1 AA accessibility** — Priority indicator shapes, focus traps on 25+ modals, emoji aria-hidden, sr-only labels, 44px touch targets, 4.5:1 contrast (#829) ✅
- [x] **All Children tab** — SVG group icon tab in parent child selector, mobile scroll indicators with ResizeObserver (#830) ✅
- [x] **Responsive breakpoints** — Standardized 33 breakpoints across 22 CSS files to 480/768/1024px tiers (#831) ✅
- [x] **Progressive disclosure** — CollapsibleSection component with smooth animation, Simplified/Full view toggle, localStorage persistence (#832) ✅

**Tier 2 — Important:**
- [x] **Empty states** — Shared EmptyState component (default/compact variants), replaced 22 inline empty states across 10 pages (#835) ✅
- [x] **Teacher dashboard enhancement** — Quick stats bar (courses/students/due/messages), recent announcements section with expand/collapse (#833) (IMPLEMENTED)
- [x] **Student engagement** — Backend streak tracking (study_streak_days, last_study_date, longest_streak), streak-at-risk banner, Due for Review section (#834) (IMPLEMENTED)
- [x] **Message search** — Search and communication improvements (#836) (IMPLEMENTED)
- [x] **Quick action paradigm** — Unify quick actions across Parent, Student, Teacher roles (#837) (IMPLEMENTED)

**Tier 3 — Backlog:**
- [x] **Grade integration** — Display grades from Google Classroom (#838) -- IMPLEMENTED
- [x] **Assignment submission** — Allow students to submit work (#839) -- IMPLEMENTED

#### 6.28 FAQ / Knowledge Base (Phase 2) -- COMPLETE

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
- [x] **Push notifications (Firebase)** — FCM HTTP v1 API; PushToken model (web/iOS/Android); service account OAuth2 auth; send_to_token/user/users/multicast; auto-deactivate invalid tokens; POST /api/push/register + unregister + tokens; admin send + stats endpoints; WebPushService (frontend); PushNotificationSetup banner component; integrated with notification creation flow (#314-#318)
- API versioning — Issue #311 (not needed when you control both clients)
- File uploads — Issues #319-#320, #333
- App Store / Play Store submission — Issues #343-#346
- Student & teacher mobile screens — Issues #379-#380
- Offline mode — Issue #337

**GitHub Issues:** #364-#380 (pilot MVP + post-pilot)

### Phase 2+ (Push Notifications Foundation)

- [x] **Push Notifications Foundation** — Firebase Cloud Messaging (FCM) push notifications for web + mobile; PushToken model (web/iOS/Android platforms, device_name, app_version, is_active, last_used_at); PushNotificationService with OAuth2 service account auth; FCM HTTP v1 API; send_to_token/user/users/multicast methods; auto-deactivate invalid tokens on 404/UNREGISTERED; POST /api/push/register (upsert), DELETE /api/push/unregister, GET /api/push/tokens; admin POST /api/admin/push/send (multi-user) + GET /api/admin/push/stats (by platform); WebPushService frontend class (dynamic Firebase JS SDK import, VAPID key, onMessage handler); PushNotificationSetup banner component (permission request, localStorage dismiss/enable tracking, success/denied states); send_push_for_notification() integration hook; Firebase env vars documented in frontend/.env.example; FIREBASE_PROJECT_ID / FIREBASE_SERVICE_ACCOUNT_JSON / FIREBASE_VAPID_PUBLIC_KEY in backend config (IMPLEMENTED)

### Phase 2+ (Multi-LMS Integration) — #22-#29

Multi-LMS provider support enabling students to connect to multiple learning management systems simultaneously (Google Classroom, Brightspace, and future providers).

| # | Feature | Issue | Phase | Value Add | Dependencies |
|---|---------|-------|-------|-----------|-------------|
| 1 | **Feasibility Study: Brightspace Integration** | #29 | 2+ | **Research** — Confirm API capabilities for materials, announcements, grades, assignments download. Documented: FULLY FEASIBLE. | None |
| 2 | **Multi-LMS Provider Framework** | #22 | 2+ | **Infrastructure** — LMSConnection model, LMSInstitution model, generic lms_provider/lms_external_id columns on Course/Assignment/CourseContent, provider registry. Foundation for all multi-LMS work. | Existing #775/#776 |
| 3 | **Multi-LMS Connection Management API** | #23 | 2+ | **Core** — OAuth flows, CRUD endpoints for connections, provider discovery, institution search. Universal callback handler. | #22 |
| 4 | **Brightspace OAuth2 Service** | #24 | 2+ | **Integration** — Brightspace-specific OAuth2 + REST API client (`app/services/brightspace.py`). Handles per-institution URLs, pagination, rate limiting. | #22 |
| 5 | **Brightspace LMSProvider Adapter** | #25 | 2+ | **Integration** — Implements LMSProvider interface for Brightspace. Translates Brightspace API → canonical models. Registered in provider registry. | #24, #22 |
| 6 | **Multi-LMS Connection Manager UI** | #26 | 2+ | **UX** — Settings page to manage connections, connect flow with institution selector, provider badges on courses, filter by provider. | #23, #25 | In Progress — tracked in #52 (Canvas adapter + UI, Batch 10) |
| 7 | **Multi-LMS Sync Orchestration** | #27 | 2+ | **Infrastructure** — Unified background sync across all providers, per-connection status tracking, stale detection, deduplication. | #22, #25 |
| 8 | **Admin LMS Institution Management** | #28 | 2+ | **Admin** — Admin page to register school board Brightspace instances, manage OAuth credentials, seed Ontario boards. | #22 |

**Implementation Status:**
- [x] **Multi-LMS Provider Framework (#22)** — LMSConnection + LMSInstitution models, provider registry (Google Classroom, Brightspace stub, Canvas stub), seeded 5 Ontario Brightspace institutions (TDSB/PDSB/YRDSB/HDSB/OCDSB), lms_provider/lms_external_id columns on Course/Assignment/CourseContent (IMPLEMENTED)
- [x] **Multi-LMS Connection Management API (#23)** — List providers, list/create/update/delete connections, LMS Connections UI at /settings/lms (IMPLEMENTED)
- [x] **Brightspace OAuth2 Service (#24)** — BrightspaceOAuthClient (auth URL, code exchange, token refresh) + BrightspaceAPIClient (courses, assignments, materials, grades, announcements); httpx with retry + rate limiting (IMPLEMENTED)
- [x] **Brightspace LMSProvider Adapter (#25)** — Full BrightspaceAdapter implementing LMSProvider protocol; sync_courses/assignments/materials/grades; registered in provider registry; 15+ tests (IMPLEMENTED)
- [x] **Admin LMS Institution Management (#28)** — Admin page at /admin/lms: create/edit/deactivate institutions, view all user connections by institution, connection stats by provider, manual sync trigger (IMPLEMENTED)
- [x] **Multi-LMS Sync Orchestration (#27)** — 15-minute APScheduler job syncing all active connections; per-connection sync with error tracking; stale detection (7-day threshold); manual trigger endpoint /api/admin/lms/sync/trigger (IMPLEMENTED)
- [x] **Multi-LMS Connection Manager UI (#26)** — Provider catalog grid (Google/Brightspace/Canvas cards) with connection status, course count, last sync time; institution selector modal for Brightspace with search and pre-seeded Ontario boards (TDSB/PDSB/YRDSB/HDSB/OCDSB); OAuth connect flow with redirect (Google → /api/google/connect, Brightspace → /api/lms/brightspace/connect); Sync Now / Disconnect actions with confirmation; connected provider detail panel slide-in with synced courses count, error display, and sync feedback; per-connection sync trigger (POST /api/lms/connections/{id}/sync); lmsConnectionsApi.syncConnection() + searchInstitutions() added to frontend API client (IMPLEMENTED)
- [x] **Canvas LMS Adapter** — CanvasOAuthClient (auth URL, code exchange, token refresh); CanvasAPIClient (courses, modules, assignments, grades, announcements, files); link-header pagination; full CanvasAdapter implementing LMSProvider; OAuth2 endpoints /canvas/connect + /callback + /refresh; registered in provider registry; 15+ tests (IMPLEMENTED)
- [x] **Moodle LMS Adapter** — MoodleOAuthClient (token-based auth via /login/token.php, validate_token via core_webservice_get_site_info, get_auth_url for manual token entry flow); MoodleAPIClient (get_site_info, get_courses via core_enrol_get_users_courses, get_assignments via mod_assign_get_assignments, get_grades via gradereport_overview_get_course_grade, get_announcements via mod_forum_get_forum_discussions, get_files via core_course_get_contents); Moodle error response handling (HTTP 200 with exception body); full MoodleAdapter implementing LMSProvider with sync_courses/assignments/materials/grades; Unix timestamp parsing (parse_unix_timestamp); module content type mapping (map_module_content_type); token-based connect endpoints GET+POST /moodle/connect + POST /moodle/{id}/refresh; registered in provider registry; 30+ tests (IMPLEMENTED)

**Recommended implementation order:**
1. **#29** Feasibility Study (research — DONE in issue body)
2. **#22** Multi-LMS Provider Framework (infrastructure prerequisite)
3. **#23** Multi-LMS Connection API (backend endpoints)
4. **#24** Brightspace OAuth2 Service (Brightspace-specific)
5. **#25** Brightspace Adapter (canonical model translation)
6. **#28** Admin Institution Management (admin config)
7. **#26** Multi-LMS UI (frontend) — tracked in #52 (Canvas adapter + UI, Batch 10, IN PROGRESS)
8. **#27** Multi-LMS Sync Orchestration (background jobs)

**User Story (Student):**
> As a student, I can connect to multiple LMS providers from my Settings page:
> 1. Connect my school's Google Classroom (TDSB)
> 2. Connect my school's Brightspace (PDSB)
> 3. Connect my private tutor's Google Classroom (Mr. Khan)
> 4. Connect any other supported LMS provider
> All courses, assignments, grades, and materials from all providers appear unified in my dashboard.

---

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
- [x] **Ontario Curriculum Management** — Store Ontario curriculum expectations, serve via REST API, curriculum-anchored AI study guide generation, CurriculumPage at /curriculum, collapsible panel in CourseDetailPage (#571) — **IMPLEMENTED**
- [x] **Exam Preparation Engine** — AI-powered personalized prep plans combining curriculum + quiz history + test records (#576) — **IMPLEMENTED**
- [x] **School Board Integration** — Board-specific course catalogs, student ↔ board linking, board selection in Edit Child modal; seed 5 Ontario boards (TDSB, PDSB, YRDSB, HDSB, OCDSB) (#511, depends on #113) — **IMPLEMENTED**
- [x] **Course Catalog Model** — Board-scoped high school course database with prerequisites, credits, grade levels, subject areas, streams, specialized programs (IB/AP/SHSM); seed per-board Ontario OSSD courses (#500) — **IMPLEMENTED**
- [x] **Academic Plan Model** — Multi-year course plan per student (Grade 9-12) with semester breakdown, planned/in-progress/completed statuses; parent + student CRUD with RBAC (#501) — **IMPLEMENTED**
- [x] **Prerequisite & Graduation Requirements Engine** — Validate plans against OSSD rules (30 credits, 18 compulsory), prerequisite chain checks, completion scoring, gap detection (#502) — **IMPLEMENTED**
- [x] **AI Course Recommendations** — Board-specific personalized guidance using student grades, goals, and analytics; on-demand generation (gpt-4o-mini); pathway analysis and risk alerts (#503) — **IMPLEMENTED**
- [x] **Semester Planner UI** — Course selection per semester with prerequisite indicators, credit counter, workload balance, real-time validation (#504) — **IMPLEMENTED**
- [x] **Multi-Year Planner UI** — Visual Grade 9-12 grid with course cards, prerequisite arrows, subject color coding, graduation progress dashboard, drag-and-drop (#505) — **IMPLEMENTED**
- [x] **University Pathway Alignment** — Map plans to post-secondary program admission requirements; gap analysis, multi-program comparison; seed top Ontario university programs (#506) — **IMPLEMENTED**
- [x] **Course Planning Navigation & Dashboard Integration** — Nav links, landing page, My Kids integration, Parent Dashboard quick actions (#507) — **IMPLEMENTED**
- [x] **Course Planning Tests** — 20+ backend route tests, 10+ frontend component tests (#508) — **IMPLEMENTED**
- [x] **Sample Exams/Tests Upload + AI Assessment (#577)** — Teacher uploads exam (PDF/doc); AI assesses quality (overall score 0-100, strengths/weaknesses, difficulty distribution, curriculum coverage, question quality); is_public toggle for student practice mode; SampleExamsPage with assessment modal and practice mode (IMPLEMENTED)
- [x] **API Key Management UI** — Create/list/revoke API keys for MCP access; bcrypt-hashed keys with cbk_ prefix; one-time key display with copy button; APIKeysPage at /settings/api-keys; Account Settings Developer section link; nav item for all roles (IMPLEMENTED)
- [x] **Multi-language support foundation** — i18n system with English + French (Canadian); t() function + useTranslation hook; 70+ translated strings across navigation, actions, dashboard, auth, errors, API keys; LanguageToggle EN/FR button in DashboardLayout header; locale stored in localStorage + user profile DB column; /api/profile/locale endpoint (IMPLEMENTED)
- [x] **Advanced AI Personalization (#47)** — PersonalizationProfile per student (learning style with AI detection, preferred difficulty/session length/time); SubjectMastery scoring (quiz*0.4 + grade*0.4 + study_freq*0.2) with beginner/developing/proficient/advanced levels + trend; AdaptiveDifficulty (consecutive correct/incorrect adjustment); AI-generated study recommendations; PersonalizationPage with mastery bars, learning style card, recommendations panel; parent view of child mastery (IMPLEMENTED)
- [x] **Admin analytics** — See Admin Analytics Dashboard above (IMPLEMENTED)

### Phase 4 (Tutor Marketplace)
- [x] **Tutor Marketplace Foundation** — TutorProfile model (bio, subjects, rates, availability, verified status, ratings); TutorBooking model (request → accept/decline → review flow); search/filter API; TutorMarketplacePage with filter bar + booking modal; TutorProfilePage with reviews; Teacher TutorDashboardPage with request management (IMPLEMENTED)
- [x] **AI tutor matching** — TutorMatchingEngine with weighted scoring (subject coverage 35%, grade match 20%, rating 20%, learning style 15%, price 10%); personalization integration (SubjectMastery weak areas + learning style); AI-generated match explanations; TutorMatchPage at /tutors/match with match score bars; TutorMatchPreference model; parent view of child matches (IMPLEMENTED)
- [x] **Payment integration (Stripe)** — SubscriptionPlan + UserSubscription models; StripeService wrapper (customer, checkout session, billing portal, cancel, webhook); Stripe Checkout for monthly/yearly premium; Billing Portal for self-service management; webhook handler (checkout.completed, subscription.updated/deleted, invoice.failed); BillingPage at /settings/billing; AdminBillingPage at /admin/billing with MRR stats; 7-day free trial (IMPLEMENTED)

- [x] **AI email sending** — AI-drafted email composition (GPT-4o-mini via Anthropic Claude); tone selection (formal/friendly/concise/empathetic); EN/FR; improve draft instructions; send via SendGrid; EmailThread + EmailMessage models (IMPLEMENTED)
- [x] **Reply ingestion** — SendGrid Inbound Parse webhook; thread matching by Message-ID/subject; EmailMessage records for inbound (IMPLEMENTED)
- [x] **AI summaries** — Thread-level AI summaries (2-4 sentences); action item extraction; reply suggestions (IMPLEMENTED)
- [x] **Searchable archive** — Full-text search across threads/messages; filter by from/to/date; tab-based inbox UI (Inbox/Sent/Drafts/Archived) (IMPLEMENTED)

---

### Batch 10 (In Progress) — #50-#54

| # | Feature | Issue | Status |
|---|---------|-------|--------|
| 1 | AI Tutor Matching | #50 | In Progress |
| 2 | Admin Feature Flag System | #51 | In Progress |
| 3 | Canvas LMS Adapter + Multi-LMS Connection Manager UI (#26) | #52 | In Progress |
| 4 | Domain Events System | #53 | In Progress |
| 5 | Firebase Push Notifications | #54 | In Progress |

- [ ] **AI tutor matching (#50)** — TutorMatchingEngine with weighted scoring (subject expertise, availability, rating, price, learning style compatibility); PersonalizationProfile integration; TutorMatchPage at /student/find-tutor
- [ ] **Admin feature flag system (#51)** — FeatureFlag model, FeatureFlagService with in-memory cache, require_feature() backend dependency, public /api/features/enabled endpoint, AdminFeatureFlagsPage, useFeatureFlag hook and FeatureGate component; guards for Tutor Marketplace, Brightspace LMS, MCP integration, School Board integration (issues #33-#43)
- [ ] **Canvas LMS adapter + Multi-LMS Connection Manager UI (#52)** — CanvasOAuthClient, CanvasAPIClient, CanvasAdapter implementing LMSProvider; OAuth2 flow endpoints; Multi-LMS Connection Manager UI with provider catalog, institution selector, connection status dashboard (addresses #26)
- [ ] **Domain events system (#53)** — EventBus with async publish/subscribe, 15+ typed domain events (AssignmentCreated, GradeSynced, UserEnrolled, etc.), cross-context handlers, admin events API for audit trail
- [ ] **Firebase push notifications (#54)** — PushToken model, PushNotificationService with FCM HTTP v1, WebPushService frontend (service worker, permission flow), PushNotificationSetup component in user settings (addresses #314-#318)

---

