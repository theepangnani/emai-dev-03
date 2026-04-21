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
- [ ] Multi-Google account support for teachers
- [x] **Auto-send invite email to shadow teachers on creation** — 30-day debounce (#946) (IMPLEMENTED)
- [x] **Teacher Dashboard course management view with source badges** (#947) (IMPLEMENTED)
- [x] **Admin broadcast messaging** — Send message + email to all users (#258) (IMPLEMENTED)
- [x] **Admin individual messaging** — Send message + email to specific user (#259) (IMPLEMENTED)
- [x] **Inspirational messages in emails** — Add role-based inspiration quotes to all outgoing emails (#260) (IMPLEMENTED)
- [x] **Simplified registration** — Remove role selection from signup form, collect only name/email/password (#412) (IMPLEMENTED)
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
- [x] **File upload security hardening** — 30 MB per-file limit (configurable via `MAX_UPLOAD_SIZE_MB`), magic bytes validation to prevent extension spoofing, 10-file session cap in upload modal (#1006) (IMPLEMENTED, PR #1008)
- [x] **Multi-file selection in Upload Documents modal** — Select up to 10 files at once; each file creates a separate course material; drag-and-drop zone; sequential OCR extraction runs in background (#991) (IMPLEMENTED, PR #977)
- [x] **Multi-file upload extended to Student and Teacher dashboards** — Upload Documents modal with multi-file support and background OCR available to all roles (was Parent-only) (#1015) (IMPLEMENTED, PR #1017)
- [x] **Clickable dashboard header label CTAs** — Summary stat labels (Assignments, Study Guides, etc.) on all role dashboards navigate to the relevant page with contextual filters pre-applied (#1012) (IMPLEMENTED, PR #1013)
- [x] **'All Children' filter button on Tasks and My Kids pages** — Dedicated "All" button in child filter row (Tasks page, My Kids page) clears individual child selection and shows aggregated data (#1016) (IMPLEMENTED, PR #1018)
- [x] **Move Grades section from Parent Dashboard to My Kids page** — Grade history cards relocated to My Kids page per child for better contextual grouping (#980) (IMPLEMENTED)
- [x] **ClassBridge logo v6.1 in dashboard header** — Updated header logo across all role dashboards (#981) (IMPLEMENTED)
- [x] **Student UX Simplification** — Unified Study Hub (/study) merging Classes + Materials + Quiz History; nav reduced 8→5; quote on dashboard only; task urgency grouping (#1022-#1029, #1032-#1035) (IMPLEMENTED)
- [x] **Show today's date on all role dashboards** (#1037) (IMPLEMENTED, PR #1038)
- [x] **My Kids page reorder + Reset Password to + menu** (#1039) (IMPLEMENTED, PR #1040)
- [x] **Inspiration message on all dashboard pages** — Show on all pages, not just /dashboard (#1041) (IMPLEMENTED, PR #1042)
- [x] **Class material titles as clickable links** on CoursesPage (#1043) (IMPLEMENTED, PR #1044)
- [x] **Case-insensitive email login** (#1045) (IMPLEMENTED, PR #1046)
- [x] **Coming Up timeline shows tasks** — Tasks now appear alongside assignments in Coming Up section, matching header overdue/due-today counts (#1047) (IMPLEMENTED, PR #1048)
- [x] **Coming Up timeline clickable rows** — Entire timeline item row is clickable, not just the View/Study button (#1049) (IMPLEMENTED, PR #1050)
- [x] **Coming Up task detail navigation** — Clicking a task navigates to `/tasks/:id` detail page (#1051) (IMPLEMENTED, PR #1052)
- [x] **Google Classroom environment toggle** — `GOOGLE_CLASSROOM_ENABLED` env var to disable Google Classroom UI globally; `gcEnabled` feature toggle in frontend via `/api/feature-toggles` endpoint (#1054) (IMPLEMENTED, PR #1055)
- [x] **AI quiz generation reliability fixes** — Handle unhandled AI API exceptions (#1059), scale max_tokens dynamically with question/card count (#1060), update Claude model to claude-sonnet-4-6 with diagnostic logging (#1061), extract question count from focus prompt instead of hardcoding 5 (#1063) (IMPLEMENTED, PRs #1059-#1063, fixes #1058 and #1062)
- [x] **Quiz difficulty levels** — Easy/Medium/Hard segmented toggle on QuizTab; backend `difficulty` param on quiz generation; prompt engineering for difficulty-appropriate questions; difficulty passed through all generation paths including file upload and text+images (#1064) (IMPLEMENTED, PR #1064)
- [x] **Multi-tool upload bug fix** — Selecting multiple AI tools (study guide + quiz + flashcards) during upload now creates 1 course material with all tabs, not 3 separate materials; pre-creates shared CourseContent before dispatching parallel generation calls (#1064) (IMPLEMENTED, PR #1064)
- [x] **Course material tab reorder** — Default active tab changed from Document to Study Guide; tab order: Study Guide → Quiz → Flashcards → Document (#1064) (IMPLEMENTED, PR #1064)
- [x] **Darker study guide container** — StudyGuideTab card has subtly darker background (`--color-surface-alt`) to visually distinguish from other tabs (#1064) (IMPLEMENTED, PR #1064)
- [x] **Quiz/flashcard count cap at 50** — Focus prompt regex clamps requested count to `min(count, 50)` instead of ignoring values over limit; matches "quizzes" pattern in addition to "questions"; frontend `num_cards` max changed from 100 to 50 (#1066) (IMPLEMENTED, PR #1067)
- [x] **Difficulty toggle CSS fix** — Removed `overflow: hidden` that clipped "Hard" button label; applied explicit `border-radius` to first/last buttons (#1066) (IMPLEMENTED, PR #1067)
- [x] **Task datetime picker fix** — Split `datetime-local` input into separate `date` and `time` inputs for better UX; native date picker now applies date on click without needing an OK button (#1068) (IMPLEMENTED, PR #1069)
- [x] **Standardized CTA icon+plus buttons** — New `.title-add-btn` CSS pattern (32px circle with "+" badge overlay) applied to page titles across Class Materials, Tasks, and Classes pages; replaces text-based "New" buttons with consistent icon-based CTAs (#1070, #1071) (IMPLEMENTED, PR #1072)
- [x] **Study guide PDF download button** — Added PDF download button with `downloadAsPdf` to individual study guide page (`/study/guide/:id`); wrapped content in `ref` for html2pdf capture (#1073) (IMPLEMENTED, PR #1075)
- [x] **Hide Connect Google for students** — Removed "Connect Google" button from StudyPage sidebar and Google Classroom banner from StudentDashboard for student role (#1074) (IMPLEMENTED, PR #1075)
- [x] **Student classes page icon+plus CTA** — Added `title-add-btn` to student's "My Classes" tab area on CoursesPage (#1075) (IMPLEMENTED, PR #1075)
- [x] **Mobile responsive layout fixes** — Suppress welcome section on detail sub-pages (CourseMaterialDetailPage, TaskDetailPage, StudyPage); add 480px header breakpoint (compact logo, truncated username); mobile GlobalSearch sizing; MaterialContextMenu dropdown repositioning; toolbar horizontal scroll at 768px (#1098) (IMPLEMENTED, PR #1099)
- [x] **Teacher Resource Links** — Auto-extract YouTube videos and URLs from uploaded documents and teacher communications; Videos & Links tab on Course Material Detail; YouTube embed player with topic grouping; CRUD API; link extraction service (§6.57, #1319-#1326) (IMPLEMENTED)
- [x] **Image Retention in Study Guides** — Extract, store, and re-embed images from uploaded PDF/DOCX/PPTX into AI-generated study guides; ContentImage model; image serving endpoint; AI prompt integration with `{{IMG-N}}` markers; authenticated frontend rendering; fallback "Additional Figures" section; +5-10% cost per generation (§6.58, #1308-#1313) (IMPLEMENTED)
- [x] **AI Help Chatbot** — RAG-powered floating chatbot on all pages; searches FAQ/help/video knowledge base; role-aware + context-aware responses; inline YouTube/Loom video embeds; 30 req/hr rate limit; in-memory vector store; gpt-4o-mini + text-embedding-3-small (§6.59, #1355-#1363) (IMPLEMENTED — #1355-#1363)
- [x] **Help Chatbot: Global Search integration** — Unified chatbot handles both help queries and platform data search (courses, materials, tasks, FAQ); SQL ILIKE search; intent routing; action cards (§6.59.9, #1630, PR #1684) (IMPLEMENTED)
- [x] **Activity History page** — `/activity` page for parents with full paginated activity log, child filter, type filter, load more (§6.92, #1547, PR #1683) (IMPLEMENTED)
- [x] **AI token cost + regeneration tracking** — `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost_usd`, `is_regeneration` added to `ai_usage_history`; admin panel shows cost breakdown (#1650, #1651, PR #1682) (IMPLEMENTED)
- [x] **GCS file storage migration** — Source files and content images migrated from PostgreSQL blobs to GCS (`gs://classbridge-files`); backfill run in prod; `file_data`/`image_data` columns dropped (#1697/#1704) (§6.93, #1643, PRs #1689 #1691 #1704) (COMPLETE — 2026-03-14)
- [x] **Chatbot search entity parity** — Assignments and Children entities added to unified search; chatbot now searches Courses, Materials, Tasks, FAQ, Assignments, Children (#1696, PR #1700) (IMPLEMENTED)
- [x] **Deprecate GlobalSearch component** — Remove standalone `GlobalSearch.tsx`, `GlobalSearch.css`, `/api/search` endpoint; chatbot is now the sole search surface (§6.17 → §6.59.9, #1698) (PENDING — blocked by #1706)
- [x] **Teacher Dashboard v2** — Student Alerts + My Classes layout with SVG icons and dynamic counts (§6.65.3, #1418) (IMPLEMENTED)
- [x] **Admin Dashboard v2** — Platform Health + Recent Activity + Quick Actions with trend indicators (§6.65.4, #1419) (IMPLEMENTED)
- [x] **Upload wizard cleanup + tests** — ReplaceDocumentModal updated, old upload modal removed, wizard frontend tests added (§6.28, #1272, #1273, PR #1685) (IMPLEMENTED)
- [x] **Scroll-to-top button** — Floating button on Course Material Detail page using IntersectionObserver; bottom-left, no conflict with FABs (§6.94, #1686, PRs #1687 #1692) (IMPLEMENTED)
- [x] **Pre-Launch Survey System** — Public role-specific survey (Parent/Student/Teacher question sets); emoji likert scale; admin analytics dashboard with Recharts charts, filters, CSV export; rate-limited public + admin APIs (§6.102, #1890, PR #1895) (COMPLETE)

#### Waitlist System & AI Usage Limits (§6.53, §6.54) — Pre-Launch — #1106-#1124
- [x] **Waitlist data model** — `waitlist` table with status tracking, invite tokens, email validation (IMPLEMENTED — #1107)
- [x] **Waitlist API endpoints** — Public join + token verify; Admin list/approve/decline/remind (IMPLEMENTED — #1108, #1109)
- [x] **Launch Landing Page** — New `/` with "Join Waitlist" + "Login" CTAs, hero section, branding (IMPLEMENTED — #1111)
- [x] **Waitlist Form Page** — `/waitlist` with name, email, role checkboxes, success confirmation (IMPLEMENTED — #1112)
- [x] **Login page update** — Replace "Sign Up" with "Join Waitlist" CTA (IMPLEMENTED — #1113)
- [x] **Token-gated registration** — `/register?token=` validates invite token, pre-fills user data (IMPLEMENTED — #1114)
- [x] **Waitlist email templates** — Confirmation, admin notification, approval/invitation, decline, reminder (IMPLEMENTED — #1110)
- [x] **Admin Waitlist Panel** — `/admin/waitlist` with stats, filterable table, approve/decline/remind actions (IMPLEMENTED — #1115)
- [x] **AI usage limits data model** — `ai_usage_limit`/`ai_usage_count` on users, `ai_limit_requests` table (IMPLEMENTED — #1117)
- [x] **AI usage enforcement** — Count AI generations, block at limit, show remaining credits in UI (IMPLEMENTED — #1118)
- [x] **AI usage request flow** — User requests more credits, admin approves/declines (IMPLEMENTED — #1119)
- [x] **Admin AI Usage Panel** — Usage stats, pending requests, manual limit adjustment (IMPLEMENTED — #1121)
- [x] **`WAITLIST_ENABLED` feature flag** — Env var to toggle waitlist mode on/off (revert for Phase 2) (IMPLEMENTED — #1124)
- [x] **Backend tests** — Waitlist + AI limits route tests (IMPLEMENTED — #1122)
- [x] **Frontend tests** — Waitlist + AI limits component tests (IMPLEMENTED — #1123)

#### Phase 1 New Workflow (§6.51) — #546-#552
- [x] **Phase 0 Foundation** — Models, migrations, notification service, schemas (IMPLEMENTED)
- [x] **Student registration with username + parent email** — Username login, parent linking on register (#546) (IMPLEMENTED)
- [x] **Parent-Student LinkRequest approval** — Bidirectional approval workflow for linking (#547) (IMPLEMENTED)
- [x] **Multi-channel notifications + ACK** — In-app + email + message, persistent reminders, suppress (#548) (IMPLEMENTED)
- [x] **Parent request assignment completion** — Parent requests student complete assignment via multi-channel notification (#549) (IMPLEMENTED)
- [x] **Google Classroom school vs private** — classroom_type, download restriction (#550) (IMPLEMENTED)
- [x] **Student/teacher invites + course enrollment** — Student invite teacher, teacher invite student/parent, course enrollment (#551) (IMPLEMENTED)
- [x] **Upload with AI tool selection** — AI tool dropdown during upload, custom prompt (#552) (IMPLEMENTED)

#### Architecture Foundation (Tier 0)
- [x] **Split api/client.ts** — Break 794-LOC monolith into domain-specific API modules (#127) (IMPLEMENTED)
- [x] **Extract backend services** — Move business logic from route handlers to domain service layer (#128) (IMPLEMENTED)
- [ ] **Repository pattern** — Introduce data access layer abstracting SQLAlchemy queries (#129)
- [x] **Split ParentDashboard** — Break 1668-LOC component into composable sub-components (#130, #657) ✅ (extracted useParentDashboard hook + TodaysFocusHeader + AlertBanner + StudentDetailPanel + QuickActionsBar; ParentDashboard.tsx now 544 LOC)
- [x] **Activate TanStack Query** — Replace manual useState/useEffect data fetching with React Query hooks (#131) (IMPLEMENTED)
- [ ] **Backend DDD modules** — Reorganize into bounded context directories (#132)
- [ ] **Frontend DDD modules** — Reorganize into domain directories (#133)
- [ ] **Domain events** — Add event system for cross-context communication (#134)

#### Security & Hardening (Tier 0)
- [x] **Authorization gaps** — `list_students()` returns ALL students to any auth user; `get_user()` has no permission check; `list_assignments()` not filtered by course access (#139) (IMPLEMENTED)
- [x] **Rate limiting** — No rate limiting on AI generation, auth, or file upload endpoints; risk of brute force and API quota abuse (#140) (IMPLEMENTED)
- [x] **CORS hardening** — ~~Currently allows `*` origins; tighten to known frontend domains (#64)~~ ✅ Fixed in #177
- [x] **Security headers** — Add X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security, CSP (#141) (IMPLEMENTED)
- [x] **Input validation** — Field length limits, whitespace stripping on multiple endpoints (#142) (IMPLEMENTED)
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
- [ ] **PostgreSQL test coverage** — Tests run on SQLite only; misses NOT NULL, Enum, and type divergences (e.g., users.email bug) (#156)
- [x] **Integration tests** — Auth flow, course visibility, parent-child linking (14 tests) (#2805, PR #2816)

#### Codebase Review — Security & Quality Hardening (March 31, 2026, PR #2816) ✅ DEPLOYED

Full codebase review resolved 22 issues across security, correctness, performance, and DB consistency.
Deployed to production April 1, 2026. All issues closed.

**Security (Critical):**
- [x] **Configurable rate limiting** — Switch from in-memory to Redis-backed storage for Cloud Run (#2221)
- [x] **OAuth token encryption** — Fernet encryption at rest + column widening (#2781)
- [x] **Refresh token blacklisting** — Logout revokes both access and refresh tokens (#2784)
- [x] **Token blacklist cache fix** — TTL-based eviction replaces clear-all at 10K (#2785)
- [x] **Password reset single-use** — JTI blacklisting prevents token reuse (#2790)
- [x] **Prevent user enumeration** — Generic error messages on login/register (#2791)
- [x] **Rate limit gaps** — Added to verify-email and unsubscribe endpoints (#2792)
- [x] **Configurable security params** — Token TTLs and lockout thresholds via env vars (#2802)
- [x] **Email verify TTL** — Reduced from 24h to 4h (configurable) (#2804)
- [x] **Audit logging** — Token refresh endpoint now logged (#2803)
- [x] **Password reset enumeration** — Uniform error messages, reordered checks (#2820)
- [x] **Security scanning** — Restored PR trigger on CI workflow (#2821)

**Correctness:**
- [x] **Parent course visibility** — Parents with no children no longer see all public courses (#2786)
- [x] **Safe JSON.parse** — QuizPage/FlashcardsPage crash on malformed content fixed (#2787)
- [x] **AnalyticsPage stale closures** — Fixed useEffect dependency arrays (#2789)
- [x] **Frontend correctness** — Token parsing, silent errors, NaN handling across 6 pages (#2795)

**Performance:**
- [x] **Pagination** — Added to courses, admin broadcast, teacher/student search (#312)
- [x] **N+1 queries** — Fixed in message fan-out and delivery log listing (#2793)

**DB Consistency:**
- [x] **Enum→String migration** — 4 columns migrated for PostgreSQL compatibility (#2788)
- [x] **Model consistency** — DateTime timezone, 8 FK indexes, cascade rules (#2794)
- [x] **Boolean defaults** — Standardized to lowercase text("false") (#2801)

**Unfixed Suggestions (tracked):**
- [ ] Extract migrations from main.py (#2824)
- [ ] Integration test fixtures (#2825)
- [ ] Redundant decrypt_token optimization (#2826)
- [ ] CSRF on onboarding endpoint (#2827)
- [ ] Add updated_at to ~14 models (#2828)
- [ ] CASCADE on DigestDeliveryLog FK (#2829)
- [ ] Compound index on link_requests (#2830)
- [ ] Validate timezone/delivery_time in digest settings (#2831)
- [ ] Validate digest_format with Literal type (#2832)
- [ ] Complete auth audit logging (#2833)
- [ ] JWT localStorage XSS risk (#69, updated)
- [ ] list_conversations pagination (#2807)
- [ ] Remaining Enum columns (#2809)

### Phase 1.5 (Calendar Extension, Content, Mobile & School Integration)
- [x] Mobile-responsive web application (fix CSS gaps, breakpoints, touch support) (IMPLEMENTED)
- [x] Student email identity merging (personal + school email on same account) (#941) (IMPLEMENTED)
- [ ] School board email integration (when DTAP approved)
- [x] Extend calendar to Student and Teacher dashboards with role-aware data (#45) (IMPLEMENTED)
- [ ] Google Calendar push integration (sync tasks/reminders to Google Calendar)
- [ ] Central document repository
- [x] Manual content upload with OCR (enhanced) — #523 ✅
- [x] Background periodic Google Classroom course/assignment sync for teachers (opt-in) (#53) (IMPLEMENTED)

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
- [ ] **Contextual Notes System** — Side-panel note-taking on course materials with WYSIWYG editor, image support (paste/upload/camera), auto-save, task linking, parent read-only child access, global search integration (§6.7, #1084-#1090)
- [x] **Data privacy & user rights** — Account deletion with data anonymization (#964), user data export for PIPEDA right of access (#965) (IMPLEMENTED)
- [x] **FAQ / Knowledge Base** — Community-driven Q&A with admin approval (#437-#444) (IMPLEMENTED)
- [ ] **Admin email template management** — View, edit, preview, and reset email templates from Admin Dashboard (#513)
- [ ] **Broadcast history reuse & resend** — View full broadcast details, reuse as template, resend to all users (#514)
- [x] **Course Materials Storage** — GCS-based persistent file storage for uploaded materials; migrated from PostgreSQL blobs to GCS (`gs://classbridge-files`); backfill complete; `file_data`/`image_data` columns dropped (#572, §6.93, #1643, PRs #1689 #1691 #1704) (IMPLEMENTED — 2026-03-14)
- [x] **Quiz Results History** — Persist quiz attempts with per-question answers; track retries, score trends, child selector for parents. Inline quiz save from Course Material detail page + dedicated Quiz page. View History link on quiz completion. (#574, #621)
- [ ] **User-Provided AI API Key (BYOK)** — Users bring their own OpenAI key; encrypted storage, seamless fallback to platform key (#578)
- [ ] **Premium accounts + admin-configurable limits** — `subscription_tier` column on users; Admin Dashboard toggle; premium users get higher file size (50 MB), session (25 files), and study guide (500) limits; configurable via env vars (#1007)
- [x] **Digital Wallet & Subscription System** — Stripe PaymentIntent flow, dual credit pools (package + purchased), admin-managed PackageTier config, subscription plans, credit purchases (§6.60, #2936) (IMPLEMENTED — core wallet; Interac e-Transfer #1851, invoice module, admin revenue dashboard deferred)
- [ ] **Study Guide Repository & Reuse** — Cross-student dedup via content hashing + fuzzy matching; shared study guide pool saves 67% AI costs (#573)
- [ ] **Student Progress Analysis** — Upload graded tests (photo/PDF), OCR score extraction, manual mark entry, AI recommendations (#575)
- [ ] **Sample Exams/Tests Upload** — Teacher uploads with AI difficulty assessment, topic coverage, curriculum alignment, practice mode (#577)
- [ ] **Parent AI Insights** — Student interest profiling, academic health score, semester reports, engagement analysis (#581)
- [x] **Study Guide Contextual Q&A** — Context-aware chatbot Q&A on study guide pages; save responses as sub-guides or course materials (§6.114, #2937) (IMPLEMENTED)
- [ ] **User Cloud Storage Destination** — Users choose to store uploaded materials in their own Google Drive or OneDrive instead of GCS; auto-created `ClassBridge/{Course}/` folder structure; on-demand download for AI regeneration; fallback to GCS on failure (§6.95, #1865-#1871)
- [ ] **Cloud File Import** — Import files directly from Google Drive or OneDrive into Upload Wizard via tabbed file browser; folder browsing, multi-select, server-side download into existing processing pipeline (§6.96, #1872-#1877)

#### Parent Email Digest Integration (CB-PEDI-001, §6.127) — #2642-#2656

Parents connect personal Gmail via OAuth (`gmail.readonly`). Child's school email (YRDSB) forwarded to parent's Gmail. ClassBridge polls Gmail every 4 hours, Claude AI summarizes into daily digest delivered as a standard ClassBridge notification (email if parent has email enabled). No DTAP/MFIPPA required.

**M0 — Feasibility (March 2026):** COMPLETE — YRDSB forwarding confirmed
**M1 — Foundation (April 2026):** IMPLEMENTED — PR #2780
- [x] ParentGmailIntegration database models — 3 new tables (#2642) (IMPLEMENTED)
- [x] Pydantic schemas (#2643) (IMPLEMENTED)
- [x] Gmail OAuth flow for parent personal accounts (#2644) (IMPLEMENTED — JWT state, redirect_uri validation)
- [x] CRUD API routes — integrations, settings, pause/resume (#2645) (IMPLEMENTED — includes PATCH endpoint)
- [x] PARENT_EMAIL_DIGEST notification type (#2646) (IMPLEMENTED — backend + frontend)
- [x] Email digest setup wizard frontend (#2647) (IMPLEMENTED — 4-step wizard on My Kids page)
- [x] Gmail OAuth callback page — popup redirect handler for setup wizard (#3017) (IMPLEMENTED — PR #3018)

**M2 — Core Engine (May 2026):** IMPLEMENTED — PR #2985, merged 2026-04-10
- [x] Gmail polling service (#2648) (IMPLEMENTED)
- [x] Forwarding verification endpoint (#2649) (IMPLEMENTED)
- [x] Claude AI digest summarization service (#2650) (IMPLEMENTED)
- [x] Scheduled digest job — every 4 hours, timezone-aware, ClassBridge notification delivery (#2651) (IMPLEMENTED)
- [x] Branded email template (#2652) (IMPLEMENTED)
- [x] Email digest page + delivery log frontend (#2653) (IMPLEMENTED)
- [x] Backend test suite — 83 tests (57 route + 26 unit) (#2654) (IMPLEMENTED)
- [x] WhatsApp notification channel — Twilio WhatsApp Business API, phone OTP, delivery fallback (#2967) (IMPLEMENTED)

**M3 — Pilot (June 2026):** 5-10 YRDSB families
**M4 — Phase 2 (July-August 2026):**
- [ ] Digest format selector, email categorization, action items extraction, multi-child UI (#2655)

**M5 — Public Launch (September 2026):**
- [ ] Historical digest archive + weekly roll-up (#2656)

#### CB-UTDF-001 — Unified Template + Detection Framework (Phase 2, §6.131) — DEPLOYED (2026-04-11)

Enhance the existing §3.9 Study Guide Strategy Pattern to auto-detect material type, subject, student, and teacher from uploaded documents, show context-aware suggestion chips, and route generation to the correct named template. Adds worksheet generation as a new first-class output type.

**PRD:** [docs/CB-UTDF-001-PRD-v1.md](../docs/CB-UTDF-001-PRD-v1.md)
**Deployed:** April 11, 2026
**Data model:** Extends `study_guides` table with `guide_type='worksheet'` and `guide_type='weak_area_analysis'` (no new tables)

**Credit costs:** Worksheet = 1 credit, Answer Key = free, High Level Summary = free, Weak Area Analysis = 2 credits

**M1 — Core Infrastructure:**
- [x] [CB-UTDF-S1] Extend document classification: add subject + confidence (#2949)
- [x] [CB-UTDF-S2] DB migration: detected_subject, template_key, worksheet columns (#2950)
- [x] [CB-UTDF-S3] Template key resolver + High Level Summary variant (#2951)

**M2 — UI & Detection:**
- [x] [CB-UTDF-S4] ClassificationBar component + teacher auto-assignment (#2952)
- [x] [CB-UTDF-S5] ChildDisambiguationModal — multi-child selector (#2953)
- [x] [CB-UTDF-S6] MaterialTypeSuggestionChips — type-driven chip sets (#2954)
- [x] [CB-UTDF-S7] ClassificationOverridePanel + PATCH endpoint (#2955)

**M3 — Generation:**
- [x] [CB-UTDF-S8] Worksheet generation: POST endpoint + viewer (#2956)
- [x] [CB-UTDF-S9] Answer key generation endpoint (#2957)
- [x] [CB-UTDF-S10] Weak area analysis: Claude Sonnet endpoint + viewer (#2958)

**M4 — Integration & Polish:**
- [x] [CB-UTDF-S13] CourseDetailPage: add Worksheets tab (#2959)
- [x] [CB-UTDF-S14] Mobile (Expo): ClassificationBar + chips (#2960)
- [x] [CB-UTDF-S15] Tests: classifier unit, integration, E2E (#2961)

**PRs:** #3068 (main), #3085 (post-deploy fixes), #3091 (PR review fixes)

#### CB-PCM-001 — Admin Customer Database: CRM, Branded Email & Messaging (Phase 2, §6.132) — DEPLOYED (2026-04-12)

Standalone Customer Database (CRM) for admin outreach to parents/prospects. 4 new tables, SendGrid email, Twilio WhatsApp/SMS, branded templates, audit logging.

**Deployed:** April 12, 2026
**Data model:** 4 new tables: parent_contacts, parent_contact_notes, outreach_templates, outreach_log

**M1 — Backend Foundation:**
- [x] [CB-PCM-S1] DB models + migrations: 4 tables (#2975)
- [x] [CB-PCM-S2] Pydantic schemas (#2976)

**M2 — Backend APIs:**
- [x] [CB-PCM-S3] Customer contacts CRUD API (#2977)
- [x] [CB-PCM-S4] Outreach templates CRUD API + 5 seed templates (#2978)
- [x] [CB-PCM-S5] Outreach send API — email, WhatsApp, SMS (#2979)

**M3 — Frontend:**
- [x] [CB-PCM-S6] Frontend — Admin Customer Database page (#2980)
- [x] [CB-PCM-S7] Frontend — Unified Outreach Composer (#2981)

**M4 — Quality:**
- [x] [CB-PCM-S9] Tests — backend + frontend (#2983)

---

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

- [x] **Report Card Upload & AI Analysis** — OCR extraction, trend tracking, AI observations per child per term (#663) (IMPLEMENTED — §6.121, commit f7d5efea)
- [x] **Quiz difficulty levels (Easy/Medium/Hard)** — Difficulty selector on QuizTab with AI prompt engineering per level (#664, PR #1064) (IMPLEMENTED — generation side; parent-assigned quizzes with notification + tracking deferred)
- [ ] **Teacher grade & feedback entry** — Spreadsheet-style bulk grading per student per term with feedback (#665)
- [ ] **Unified teacher material upload with type classification** — Notes/Test/Lab/Assignment/Report Card types (#666)
- [ ] **AI Mock Exam Generator** — Teacher generates + bulk-assigns AI-powered exams to students (#667)

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
- [x] **Teacher dashboard enhancement** — SVG icons, dynamic counts, announcement preview (#833) (IMPLEMENTED — via Teacher Dashboard v2 §6.65.3)
- [x] **Student engagement** — Streak celebrations, spaced repetition, continue studying (#834) (IMPLEMENTED)
- [x] **Message search** — Search with pagination, date filtering, and in-thread search (#836) (IMPLEMENTED)
- [x] **Quick action paradigm** — Unified quick actions across Parent, Student, Teacher roles (#837) (IMPLEMENTED)

**Tier 3 — Backlog:**
- [x] **Grade integration** — Display grades from Google Classroom (#838) (IMPLEMENTED)
- [x] **Assignment submission** — Allow students to submit work (#839) (IMPLEMENTED)

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

#### Google OAuth Production Launch (March 2026)
- [x] **Privacy Policy + Terms of Service pages** — `/privacy` and `/terms` live at classbridge.ca (#585, #586) (IMPLEMENTED)
- [x] **Rename OAuth consent screen** — App name updated from EMAI → ClassBridge; logo, homepage, privacy/ToS links updated (#726) (IMPLEMENTED)
- [x] **Remove gmail.readonly from initial OAuth scopes** — Incremental auth implemented; gmail.readonly deferred to post-launch to avoid CASA audit (#727) (IMPLEMENTED)
- [x] **Support email for OAuth consent screen** — classbridge-support Google Group created and set as support email (#757) (IMPLEMENTED)
- [x] **Google OAuth app published to production** — App moved from Testing → In production; branding verified; all Classroom scopes registered; no sensitive scope review required (#589) (IMPLEMENTED — March 1, 2026)

### Phase 2 (Mobile App — March 6 Pilot MVP) - COMPLETE

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

### Phase 2 (WOW Features — Parent Value & Engagement) — #1403-#1420

Features that answer the pilot feedback question: *"Why should I use ClassBridge?"* — transforming ClassBridge from a passive viewer to an active parenting tool.

| Priority | Feature | Epic | AI Cost | WOW Impact |
|----------|---------|------|---------|------------|
| 1 | **Smart Daily Briefing** — proactive "what matters today" | #1403 | $0 | Highest — answers "why open ClassBridge" |
| 2 | **Help My Kid** — one-tap study material generation | #1407 | ~$0.02/use | Highest — instant parent action |
| 3 | **Global Search via Chatbot** — find anything instantly through Help Chatbot | #1630 (supersedes #1410) | $0 | Medium — power users love it |
| 4 | **Weekly Progress Pulse** — email digest every Sunday | #1413 | $0 | High — passive value, no login needed |
| 5 | **Parent-Child Study Link** — feedback loop on sent materials | #1414 | $0 | High — emotional connection |
| 6 | **Dashboard Redesign** — clean, persona-based, 3-section layouts | #1415 | $0 | High — first impression |
| 7 | **Help Page + Chatbot** — document WOW features for discoverability | #1420 | $0 | Medium — user education |
| 8 | **Responsible AI Parent Tools** — readiness checks, parent briefings, practice problems, weak spots, conversation starters | #1421 | ~$0.02/use | Highest — "Parents First" differentiator |
| 9 | **Smart Data Import** — photo capture, email forwarding, ICS calendar sync | #1431 | ~$0.02/photo | High — Layer 1→2 accelerator |

**Phased delivery plan (5 weeks, ship weekly to pilot users):**

| Phase | Name | Ship Date | Issues | Theme |
|-------|------|-----------|--------|-------|
| **2A** | The Hook | March 15 | #1403, #1404, #1405, #1407, #1408, #1409 | Daily Briefing + Help My Kid |
| **2B** | The Dashboard | March 22 | #1415, #1416, #1417, #1425 | Persona-based layouts + Weak Spots |
| **2C** | The Loop | March 29 | #1414, #1422 | Parent-child feedback loop |
| **2D** | The Retention | April 5 | #1413, #1434, #1424 | Email digest + Calendar + Practice |
| **2E** | The Polish | April 14 | #1410, #1411, #1412, #1418, #1419, #1420 | Search + Help + QA |

**Completed (March 8):**
- [x] **Per-Category Notification Preferences** (PR #1464) — fine-grained per-category notification controls
- [x] **Parent Briefing Notes** (#1423, PR #1467) — plain-language topic summaries for parents
- [x] **Learn Your Way** (PR #1469) — interest-based AI personalization with mind maps
- [x] **Premium Storage/Upload Limits** (PR #1470) — tiered limits per subscription level
- [x] **Responsible AI Parent Tools Tests** (PR #1471) — test coverage for parent tools
- [x] **Conversation Starters** (#1426, PR #1485) — moved to My Kids page, on-demand
- [x] **Briefing relocated to My Kids** (PR #1485) — on-demand per-child context
- [x] **Sidebar icons + always-expanded** (PR #1483) — missing icons fixed, collapse removed
- [x] **HelpStudyMenu route fix** (PR #1480) — blank readiness page resolved
- [x] **generation_type VARCHAR widened** (PR #1481) — VARCHAR(20) to VARCHAR(50)

**Deferred (post April 14):** Photo Capture (#1432), Email Forwarding (#1433), Daily Email Digest (#1406), Monetization (#1384-#1392), Learn Your Way Paywall/Monetization (#1441)

### Phase 2 (September 2026 Retention Bundle) — #1997-#2025

Student retention and parent engagement features based on StudyGuide Requirements v3 analysis. Target: September 2026 launch.

| Priority | Feature | Epic/Issue | Build Effort | Audience | Status |
|----------|---------|------------|-------------|----------|--------|
| Critical | **Study Streak & XP Point System** | #1997 | High | Student | **IMPLEMENTED** |
| Critical | **Weekly Parent Digest Enhancements** | #2022 | Low | Parent | **IMPLEMENTED** |
| High | **Sibling Profiles** (mostly LIVE) | — | Low | Parent | **IMPLEMENTED** |
| High | **Assessment Countdown Widget** | #1998 | Low-Medium | Both | **IMPLEMENTED** |
| High | **Multilingual Parent Summaries** | #1999 | Low | Parent | **IMPLEMENTED** |
| High | **Personal Study History Timeline** | #2017 | Medium | Student | **IMPLEMENTED** |
| High | **Sub-Guide v2** | #1817–#1820 | Medium | Student | **IMPLEMENTED** |
| Medium | **End-of-Term Report Card** | #2018 | Medium | Both | **IMPLEMENTED** |
| Medium | **Parent-Initiated Study Request** | #2019 | Medium | Parent | **IMPLEMENTED** |
| Medium | **Is My Child On Track Signal** | #2020 | Low | Parent | **IMPLEMENTED** |
| Medium | **Study With Me (Pomodoro)** | #2021 | Low-Medium | Student | **IMPLEMENTED** |

**Aggressive Batch Delivery Plan — 7 Batches, April–August 2026:**

Each batch is a deployable, testable unit merged to master via PR. Batches include backend + frontend + tests. Parallel Claude sessions use integration branches per CLAUDE.md Rule 6.

---

#### Batch 0 — Tech Debt & Schema Foundation (April 7–11) ✅ COMPLETE
**Theme:** Clean slate — fix debt, add columns needed by everything else.
**Duration:** 1 week | **Risk:** Low | **Deploy:** Yes — invisible to users
**Actual:** Completed March 12, 2026 (PR f359f92d). Deployed ahead of schedule.

| # | Issue | Work | Est |
|---|-------|------|-----|
| 1 | #2025 | **is_master String→Boolean migration** — ALTER TABLE + model update + code cleanup | 0.5d |
| 2 | #2010 | **source_type column** on SourceFile + CourseContent — migration + update upload endpoints to set value | 0.5d |
| 3 | — | **User model columns** — `preferred_language` (VARCHAR DEFAULT 'en'), `timezone` (VARCHAR DEFAULT 'America/Toronto') via ALTER TABLE in main.py | 0.5d |
| 4 | #2024 | **holiday_dates table** — model, admin CRUD endpoints, seed YRDSB 2026-27 dates | 1d |
| 5 | — | **Tests** for all migrations + new endpoints | 0.5d |

**Hook points prepared:** upload routes tag `source_type`, user model ready for XP/streak/language.
**Verification:** `pytest` passes, `npm run build` clean, deploy to staging.

---

#### Batch 1 — XP Core Engine (April 14–25) ✅ COMPLETE
**Theme:** Backend gamification engine — no UI yet, just the data layer and service.
**Duration:** 2 weeks | **Risk:** Medium | **Deploy:** Yes — feature-flagged, invisible
**Actual:** Completed March 14, 2026. XP model, earning service, streak engine, API routes all deployed.

| # | Issue | Work | Est |
|---|-------|------|-----|
| 1 | #2000 | **XP data model** — `xp_ledger`, `xp_summary`, `badges`, `streak_log` tables (models + migrations) | 1d |
| 2 | #2001 | **XP earning service** — `app/services/xp_service.py` with `award_xp()`, daily cap enforcement, multiplier logic | 2d |
| 3 | — | **Hook into 6 endpoints** — study.py (generate, quiz, flashcards, upload), course_contents.py (upload), quiz_results.py (completion) | 2d |
| 4 | #2002 | **Streak engine** — `app/services/streak_service.py`, `app/jobs/streak_check.py` nightly cron, freeze token logic, holiday_dates query | 2d |
| 5 | #2003 | **XP levels & titles** — level calculation in xp_service, level-up notification | 0.5d |
| 6 | — | **XP API endpoints** — `app/api/routes/xp.py`: GET /api/xp/summary, GET /api/xp/history, GET /api/xp/badges | 1d |
| 7 | — | **Tests** — 40+ tests for XP award, caps, streaks, multipliers, levels, edge cases | 1.5d |

**Key decision:** XP awards fire after DB commit in each hook point. Use `await xp_service.award_xp(user_id, action_type, db)` — fail-safe (XP failure doesn't block the primary action).
**Verification:** `pytest` passes, manual test via API calls, streak cron runs correctly.

---

#### Batch 2 — XP Dashboard & Visibility (April 28 – May 9) ✅ COMPLETE
**Theme:** Make gamification visible to students and parents.
**Duration:** 2 weeks | **Risk:** Low | **Deploy:** Yes — users see streaks/XP for first time
**Actual:** Completed March 16, 2026. XP dashboard, history page, parent visibility, digest crons deployed.

**Track A (Student UI)** — can run as parallel session:

| # | Issue | Work | Est |
|---|-------|------|-----|
| 1 | #2006 | **XP dashboard widgets** — StreakCounter, LevelBar, TodayXP, BadgesShelf components on StudentDashboard | 2d |
| 2 | #2007 | **XP history page** — `/xp/history` route, ledger table with filters, PDF export via html2pdf | 1.5d |
| 3 | — | **Streak flame animations** — CSS keyframe animations for 5 streak tiers (grey→orange→red→glow→gold) | 0.5d |

**Track B (Parent UI)** — can run as parallel session:

| # | Issue | Work | Est |
|---|-------|------|-----|
| 4 | #2008 | **Parent XP visibility** — child streak/level/weekly XP on My Kids cards, child detail panel | 1.5d |
| 5 | — | **XP in weekly digest** — extend `weekly_digest_service.py` to include XP summary per child | 0.5d |

**Track C (Digest Cron)** — can run as parallel session:

| # | Issue | Work | Est |
|---|-------|------|-----|
| 6 | #2022 | **Weekly digest cron** — APScheduler job in main.py, Sunday 7pm, timezone-aware, conversation starters | 1d |
| 7 | #2023 | **Daily digest cron** — APScheduler job, morning delivery, opt-in preference | 0.5d |

**Verification:** Full E2E — upload a file → see XP awarded → streak increments → parent sees child's streak. Digest emails fire on schedule.

---

#### Batch 3 — Badges & Brownie Points (May 12–23) ✅ COMPLETE
**Theme:** Depth — make gamification sticky with achievements and social rewards.
**Duration:** 2 weeks | **Risk:** Low | **Deploy:** Yes
**Actual:** Completed March 18, 2026. Badges, brownie points, anti-gaming rules deployed.

**Track A (Badges):**

| # | Issue | Work | Est |
|---|-------|------|-----|
| 1 | #2004 | **Badge trigger service** — evaluate 14 badge conditions after XP award, badge definitions in code | 2d |
| 2 | — | **Badge UI** — badge collection page, badge shelf on dashboard, badge unlock toast notification | 1.5d |
| 3 | — | **Badge tests** — trigger conditions, edge cases, no duplicates | 1d |

**Track B (Brownie Points + Anti-Gaming):**

| # | Issue | Work | Est |
|---|-------|------|-----|
| 4 | #2005 | **Brownie points** — POST /api/xp/award endpoint, weekly caps, audit log, admin view | 1.5d |
| 5 | #2009 | **Anti-gaming rules** — time-on-task checks, 60-second dedup, rapid upload flags, quiz repeat caps | 1.5d |
| 6 | — | **Tests** for brownie points + anti-gaming | 1d |

**Verification:** Earn badge by triggering condition → toast appears → badge on profile. Parent awards brownie points → child sees notification → admin sees audit log.

---

#### Batch 4 — Assessment Countdown & On Track (May 26 – June 6) ✅ COMPLETE
**Theme:** Urgency — give parents and students reasons to open ClassBridge daily.
**Duration:** 2 weeks | **Risk:** Medium (AI date parsing is tricky) | **Deploy:** Yes
**Actual:** Completed March 22, 2026. Assessment countdown, On Track signal, parent study request, multilingual summaries, Pomodoro, timeline, report card all deployed.

| # | Issue | Work | Est |
|---|-------|------|-----|
| 1 | #2011 | **Assessment date detection** — regex + Claude Haiku parsing of uploaded text for dates + exam keywords, hook into upload pipeline | 2d |
| 2 | #2012 | **detected_events table + API** — model, migration, GET /api/events/upcoming, DELETE /api/events/{id} (dismiss false positive) | 1d |
| 3 | #2013 | **Countdown widget UI** — AssessmentCountdown component on student + parent dashboards, "X days until" cards, "last studied Y days ago", tap → opens study guide | 2d |
| 4 | #2020 | **On Track signal** — nightly cron comparing streak_log vs detected_events, green/yellow/red on parent dashboard per child | 1.5d |
| 5 | #2019 | **Parent study request** — extend Help My Kid with urgency selector, student accept/defer/flag flow, response visible to parent | 2d |
| 6 | — | **Tests** — date parsing, events API, countdown display, On Track conditions | 1.5d |

**Verification:** Upload past exam → date detected → countdown appears → On Track signal shows yellow if not studying → parent sends study request → student sees notification.

---

#### Batch 5 — Multilingual & Sub-Guide v2 (June 9–20)
**Theme:** Differentiation — features no competitor has.
**Duration:** 2 weeks | **Risk:** Medium (translation costs) | **Deploy:** Yes

**Track A (Multilingual):**

| # | Issue | Work | Est |
|---|-------|------|-----|
| 1 | #2014 | **Language preference UI** — settings page language selector, saved to user.preferred_language | 0.5d |
| 2 | #2015 | **Translation service** — `app/services/translation_service.py`, Claude API call, `translated_summaries` cache table, on-demand generation | 2d |
| 3 | #2016 | **Multilingual digest** — apply translation to weekly/daily digest emails | 1d |
| 4 | — | **Tests** — translation caching, language preference, digest translation | 0.5d |

**Track B (Sub-Guide v2)** — can run as parallel session:

| # | Issue | Work | Est |
|---|-------|------|-----|
| 5 | #1817 | **Enhanced SelectionTooltip** — "Generate Study Material" button alongside "Add to Notes" | 1d |
| 6 | #1818 | **Sub-Guides collapsible panel** on parent study guide page | 1d |
| 7 | #1819 | **Breadcrumb navigation** for multi-level sub-guide hierarchies | 1d |
| 8 | #1820 | **Tree hierarchy API endpoint** — full parent-child tree | 1d |

**Verification:** Set language to Tamil → view study guide → parent summary in Tamil. Select text → generate sub-guide → see in panel → breadcrumb navigates back.

---

#### Batch 6 — Timeline, Pomodoro & Report Card (June 23 – July 4)
**Theme:** Polish — complete the retention loop.
**Duration:** 2 weeks | **Risk:** Low | **Deploy:** Yes

**Track A:**

| # | Issue | Work | Est |
|---|-------|------|-----|
| 1 | #2017 | **Study history timeline** — backend aggregation API + vertical timeline component with subject/date filters | 3d |
| 2 | #2021 | **Pomodoro sessions** — timer UI, subject selection, min 20-min validation, AI recap via gpt-4o-mini, XP award hook | 2d |

**Track B:**

| # | Issue | Work | Est |
|---|-------|------|-----|
| 3 | #2018 | **End-of-term report card** — semester data aggregation, PDF generation via html2pdf, in-app card, next-term CTA | 2.5d |
| 4 | — | **Tests** for timeline, Pomodoro, report card | 1.5d |

**Verification:** View timeline → see full semester activity. Start Pomodoro → complete 25 min → AI recap → XP awarded. Generate report card PDF.

---

#### Summary Timeline

```
April   ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░
        B0      B1              B2 starts
May     ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░
        B2 ends   B3          B4 starts
June    ░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░
        B4 ends   B5          B6 starts
July    ░░▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░
        B6 ends   Buffer / QA / bug fixes
Aug     ░░░░░░░░░░░░░░░░░░░░░░░░░░
        Integration testing + staging soak
Sept    🚀 September 2026 Launch
```

| Batch | Dates | Issues | Deploy |
|-------|-------|--------|--------|
| **B0** | Apr 7–11 | #2025, #2010, #2024 | Invisible |
| **B1** | Apr 14–25 | #2000, #2001, #2002, #2003 | Feature-flagged |
| **B2** | Apr 28 – May 9 | #2006, #2007, #2008, #2022, #2023 | Users see XP |
| **B3** | May 12–23 | #2004, #2005, #2009 | Badges live |
| **B4** | May 26 – Jun 6 | #2011–#2013, #2019, #2020 | Countdown live |
| **B5** | Jun 9–20 | #2014–#2016, #1817–#1820 | Multilingual + Sub-guide v2 |
| **B6** | Jun 23 – Jul 4 | #2017, #2018, #2021 | Full bundle |
| **Buffer** | Jul 7–31 | Bug fixes, QA, perf testing | Stabilize |
| **Soak** | Aug 1–31 | Staging soak, beta feedback | Validate |

**Parallel session opportunities:** Batches 2, 3, 5, and 6 each have 2 independent tracks (A/B) that can run as parallel Claude sessions using integration branches.

**Safe rollback points:** Each batch is atomic. If a batch has issues, revert its PR. XP system is feature-flagged in Batch 1 — can disable without removing code.

**Total estimated effort:** ~60 working days across 13 weeks (April 7 – July 4) + 2 months buffer.

### Phase 2 (User Journey Guidance & Onboarding) — #2597, #2598

Help users discover and navigate ClassBridge features through an expanded Help page with visual journey guides and smart, non-annoying contextual hints.

**Priority order (12 sub-issues across 2 epics):**

| Step | Issue | Title | Priority | Depends On |
|------|-------|-------|----------|------------|
| 1 | #2599 | Add journey diagram SVG/PNG assets | HIGH | — |
| 2 | #2604 | journey_hints DB table & migration | HIGH | — |
| 3 | #2600 | User Journeys tab in Help Center | HIGH | #2599 |
| 4 | #2602 | Index journey content in Help KB YAML | MEDIUM | — |
| 5 | #2605 | Journey hint detection service | HIGH | #2604 |
| 6 | #2606 | Journey hints API endpoints | HIGH | #2604, #2605 |
| 7 | #2607 | First-login welcome modal | HIGH | #2599, #2606 |
| 8 | #2601 | Ask the Bot on journey cards | MEDIUM | #2600 |
| 9 | #2608 | Contextual nudge banner | MEDIUM | #2606 |
| 10 | #2609 | Behavior signal detection (cooldown, nuclear) | MEDIUM | #2605, #2607, #2608 |
| 11 | #2603 | Tutorial cross-links to journey articles | LOW | #2600 |
| 12 | #2610 | Getting Started progress widget | LOW | #2605, #2606 |

**Parallel opportunities:** Steps 1+2 can run in parallel. Steps 3+4+5 can run in parallel. Steps 7+8 can run in parallel.

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

### Infrastructure: Railway Deployment for clazzbridge.com — #1878

Deploy ClassBridge to Railway as an auto-synced mirror of the production repo, serving **clazzbridge.com**. Production remains on GCP Cloud Run (classbridge.ca) for school board compliance. Railway provides a cost-effective parallel deployment for demo and non-school-board use.

**Architecture:** `emai-dev-03` (master) → GitHub Actions sync → `emai-railway` (main) → Railway auto-deploy → clazzbridge.com

| Phase | Task | Issue | Status |
|-------|------|-------|--------|
| 1 | Create mirror repo `emai-railway` | #1879 | Planned |
| 1 | GitHub Actions auto-sync workflow | #1880 | Planned |
| 2 | Configure Railway project, service, PostgreSQL | #1881 | Planned |
| 2 | Configure environment variables and secrets | #1882 | Planned |
| 2 | Add `railway.toml` deployment config | #1883 | Planned |
| 3 | Configure clazzbridge.com DNS → Railway | #1884 | Planned |
| 3 | Add Railway URLs to Google OAuth console | #1885 | Planned |
| 4 | Configure file storage for Railway | #1886 | Planned |
| 4 | Seed Railway PostgreSQL | #1887 | Planned |
| 5 | Smoke test all core features | #1888 | Planned |
| 5 | Document Railway setup and architecture | #1889 | Planned |

**Cost:** Railway Hobby Plan ~$5/month (includes PostgreSQL + custom domain)

**Compliance note:** Railway has no Canadian data centers — not suitable for FIPPA/MFIPPA school board deployments. Production stays on GCP.

---

### Phase 2F: Phase-2 Port (Milestone: May 1, 2026)

Port 10 unique features from `class-bridge-phase-2` repository that were not independently implemented on `emai-dev-03`.

| # | Feature | Issue | Status |
|---|---------|-------|--------|
| 1 | 2FA/TOTP Authentication | #2130 | Planned |
| 2 | Feature Flags Infrastructure | #2131 | Planned |
| 3 | Learning Journals | #2132 | Planned |
| 4 | Meeting Scheduler | #2133 | Planned |
| 5 | Discussion Forums | #2134 | Planned |
| 6 | Peer Review | #2135 | Planned |
| 7 | AI Writing Assistance | #2136 | Planned |
| 8 | AI Homework Help | #2137 | Planned |
| 9 | Wellness Check-ins | #2138 | Planned |
| 10 | Student Goals | #2139 | Planned |

Additionally, 47 open issues migrated from emai-class-bridge (#2143-#2189) and 9 MCP porting issues (#2191-#2199).

---

#### Accessibility Audit Fixes (P1-Major) — March 31, 2026 — PR #2780

- [x] **Navigation ARIA patterns** — aria-expanded on hamburger, role=menu/menuitem on role switcher with arrow key nav + Escape, aria-current="page" on active nav, aria-hidden on mobile overlay background (#2476) (IMPLEMENTED)
- [x] **Missing labels & heading hierarchy** — aria-hidden on decorative SVG nav icons, aria-label + aria-pressed on RichTextEditor toolbar buttons, aria-current="page" on Breadcrumb (#2478) (IMPLEMENTED)
- [x] **Focus-visible states** — :focus-visible styles on .role-switcher-option, .logout-button, Toast elements (#2479) (IMPLEMENTED)

#### Design System Consistency Fixes (P1-Major) — March 31, 2026 — PR #2780

- [x] **Hardcoded colors → CSS variables** — Replaced hex/rgba in SearchableSelect.css, BugReportModal.css, SpeedDialFAB.css, AuthContext.tsx, DashboardLayout.tsx with var(--color-*) tokens (#2480) (IMPLEMENTED)
- [x] **Spacing tokens + border-radius standardization** — Added --space-xs through --space-2xl tokens; replaced hardcoded border-radius across 10 files with --radius-* tokens (#2481, PR #2778) (IMPLEMENTED)
- [x] **Font type scale (rem)** — Added --text-xs through --text-3xl tokens; converted px font-sizes to rem in Auth.css, Dashboard.css, Toast.css, PageNav.css, NotificationBell.css (#2482) (IMPLEMENTED)

#### Performance Fixes — March 31, 2026 — PR #2780

- [x] **Optimize student enrollment query** — Replaced lazy-load `[c.id for c in student.courses]` with direct join table query on student_courses (#2774, PR #2779) (IMPLEMENTED)
- [x] **Stop polling resource links after timeout** — Added 2-minute max-poll timeout via useRef + refetchInterval callback (#2773, PR #2775) (IMPLEMENTED)

#### Bug Fixes — March 31, 2026 — PR #2780

- [x] **Chip navigation fails** — Moved navigate() before refreshAIUsage(); wrapped refresh in try/catch with console.warn (#2759) (IMPLEMENTED)
- [x] **Empty catch block on refreshAIUsage** — Added console.warn in catch block for chip handler (#2761) (IMPLEMENTED)

#### Gmail OAuth Verification (Planned — July-September 2026)

- [ ] **Privacy policy update** — Update classbridge.ca/privacy to cover Gmail data usage for email digest (#2797)
- [ ] **Terms of Service update** — Update classbridge.ca/terms for Gmail integration (#2798)
- [ ] **OAuth callback page** — Frontend route at /oauth/gmail/callback for popup flow (#2799)
- [ ] **CASA Tier 2 audit + Google verification** — Security assessment for gmail.readonly scope (~$4,500-15,000, 4-8 weeks) (#2800)

See [docs/CB-PEDI-001-setup-guide.md](../docs/CB-PEDI-001-setup-guide.md) for full setup and verification guide.

#### Suggestion Chip Streaming — April 1, 2026 — PR #2812

- [x] **Streaming generation for suggestion chips** — Replaced synchronous `generateChildGuide()` with `stream.startStream()` SSE; content appears word-by-word in Study Guide tab instead of 10-30s blocking wait (#2806, PR #2812) (IMPLEMENTED)
- [x] **Streaming endpoint parent_guide_id support** — Added `parent_guide_id` to streaming endpoint for sub-guide hierarchy (#2810, PR #2879) (IMPLEMENTED)
- [x] **Scroll to tab content on chip click** — Auto-scroll to Study Guide tab when streaming starts (#2811, PR #2879) (IMPLEMENTED)
- [x] **Concise overview prompt + chip reliability** — Rewrote strategy templates for concise overview; max_tokens=1200; Full Study Guide chip uses 4000 tokens (#2837, #2839, #2840, PRs #2852, #2860) (IMPLEMENTED)

#### Progressive Generation Refinements — April 1-5, 2026

- [x] **Ask a Question feature** — Parent open-ended study guide generation with streaming (§6.128, #2861, PR #2866) (IMPLEMENTED)
- [x] **Ask a Question streaming fixes** — Full guide generation, navigate-then-stream pattern, prompt fixes (#2880-#2890, PRs #2881-#2893) (IMPLEMENTED)
- [x] **Suggestion chips on sub-guide pages** — Topic chips, Full Study Guide, Ask Bot on sub-guide detail pages (PR #2871) (IMPLEMENTED)
- [x] **Migrations extracted from main.py** — Dedicated migrations module (#2824, PR #2879) (IMPLEMENTED)
- [x] **DB consistency fixes** — CASCADE on DigestDeliveryLog FK, compound index on link_requests, digest schema validation (#2826, #2829-#2832, PR #2879) (IMPLEMENTED)

#### Study Guide Enhancements — April 6-8, 2026 — PR #2906

- [x] **Study guide section navigation (§6.129)** — TOC auto-generated from markdown headings, collapsible sections, smooth scroll, localStorage persistence (#2894, PR #2906) (IMPLEMENTED)
- [x] **Inline helpful links (§6.130 Phase 1)** — ResourceLinksSection component on study guide pages with YouTube embeds, topic grouping (#2895, PR #2906) (IMPLEMENTED)
- [x] **Continue streaming fix** — Fixed spinner-only bug, actual streaming content now displays (#2896, PR #2906) (IMPLEMENTED)
- [x] **TOC sub-guides only** — TOC and collapsible sections only render on sub-guide pages, not overviews (#2923, PR #2915) (IMPLEMENTED)

#### Activity Feed Fixes — April 8, 2026 — PR #2916

- [x] **Child filter on tasks** — Activity feed showed wrong child's tasks when filtering (#2914) (IMPLEMENTED)
- [x] **Cache invalidation** — Activity cache invalidated after upload/study guide generation (#2919) (IMPLEMENTED)
- [x] **N+1 query fix** — Message sender lookup in activity feed (#2918) (IMPLEMENTED)
- [x] **Regression test** — Added test for activity child filter on tasks (#2917) (IMPLEMENTED)

#### CI/CD Optimization — April 1, 2026 — PR #2847

- [x] **GitHub Actions free tier optimization** — Path filters, concurrency groups, job consolidation, security scan consolidation, daily schedule, rate limit fix, debounce (#2841-#2846, #2813, #2815, PR #2847) (IMPLEMENTED)
- [x] **Security scanning daily schedule** — Moved from PR triggers to daily cron (commit 18e10f3f) (IMPLEMENTED)

#### Batch Bug Fixes — March 29-31, 2026

- [x] **Tab overflow fix** — Study tools grouped into dropdown to prevent tab overflow (#2740, #2747) (IMPLEMENTED)
- [x] **YouTube validation + timestamps + image fallback** — Multiple content rendering fixes (#2742-#2750, PR #2746) (IMPLEMENTED)
- [x] **Accessibility + dark mode fixes** — Quick fixes, accessibility improvements, dark mode (#2741, #2738, #2718, #2474, #2472, #2483, PR #2751) (IMPLEMENTED)
- [x] **Duplicate sub-guides + chip navigation** — Fixed duplicate creation and navigation failure (#2758, #2759, PR #2760) (IMPLEMENTED)
- [x] **Tab sizing + Access Log** — Access Log visible to all users (#2717, PR #2762) (IMPLEMENTED)
- [x] **Student course visibility** — Students only see own/enrolled courses (#2766, PR #2772) (IMPLEMENTED)
- [x] **DB connection pool** — Reduced pool to prevent PostgreSQL slot exhaustion (#2769) (IMPLEMENTED)
- [x] **Child guide dedup** — Proper dedup + student visibility for parent sub-guides (#2758, #2765, PR #2764) (IMPLEMENTED)

#### Auth Hardening & Login Fix — April 13, 2026

- [x] **Login infinite loop fix** — Non-memoized `loginWithToken` in `useEffect` dep array caused OAuth callback re-render loop; all 7 AuthContext functions wrapped with `useCallback`, Provider value with `useMemo`, circuit breaker refs in Login.tsx and Register.tsx (#3233-#3238, PR #3234) (IMPLEMENTED)
- [x] **Multi-sender email monitoring** — Parents can whitelist multiple teacher email addresses for digest polling (#3178, PR #3218) (IMPLEMENTED)
- [x] **Email digest wizard fix** — Detect existing Gmail integration + hardcoded turquoise → CSS theme variables (#3219, #3220, PR #3221) (IMPLEMENTED)

#### Interactive Learning Engine (CB-ILE-001) — April 13-14, 2026 — ALL MILESTONES COMPLETE

- [x] **M0: Foundation** — 5 DB tables, session orchestrator, AI question generation, Flash Tutor UI, XP/badge integration (PR #3224) (IMPLEMENTED Apr 13)
- [x] **M1: Learning Mode + Adaptive** — Component extraction, within-session adaptive difficulty, session persistence + resume (PRs #3243, #3246, #3248) (IMPLEMENTED Apr 14)
- [x] **M2: Topic Mastery + Cost Optimization** — Mastery tracking, Surprise Me, Fill-in-the-Blank, question bank pre-gen, SM-2 Memory Glow, 4 badges + calibration (PRs #3245, #3250, #3252-#3255) (IMPLEMENTED Apr 14)
- [x] **M3: Parent Teaching + Polish** — Parent Teaching Mode, Private Practice, Career Connect, ILE in email digest, Aha Moments + Knowledge Decay (PRs #3273, #3276, #3277, #3279) (IMPLEMENTED Apr 14)
- [x] **M4: Hardening + Analytics** — Cost logging, anti-gaming, admin analytics, response caching, quiz migration, study guide integration, 12 ILE tests (PRs #3274, #3275, #3278) (IMPLEMENTED Apr 14)

#### CB-LAND-001 — Landing Page Redesign (Phase 2, §6.140) — SHIPPED (2026-04-21)

Mindgrasp-inspired landing at `classbridge.ca`: 12-section persuasion architecture (Hero · Pain · Feature rows · How-It-Works accordion · Old-vs-New split · Progress grid · Cross-device bar · Learner-segment tabs · Pricing teaser · Proof Wall · Final CTA · Footer). Coexists with CB-DEMO-001 (§6.135) — reuses `InstantTrialModal` / `TuesdayMirror` / `ProofWall`; replaces landing mount of `RoleSwitcher` with `LearnerSegmentTabs`. Gated by `landing_v2` flag; kill-switch renders legacy `LaunchLandingPage`. Full spec in §6.140.

**Epic:** #3800 · **Integration PR:** #3871 (merged 2026-04-21)
**Reference screenshots:** [docs/design/landing-v2-reference/](../docs/design/landing-v2-reference/) (12 annotated Mindgrasp screenshots)

**Foundations:**
- [x] [CB-LAND-S1] Design spec — typography (Fraunces + Instrument Sans), pastel row palette, motion tokens (#3801, PR #3821)
- [x] [CB-LAND-S2] LandingPageV2 scaffold + section registry + `landing_v2` feature flag (#3802, PR #3849)

**Sections:**
- [x] [CB-LAND-S3] Hero — serif-italic headline, demo CTA, Ontario-board trust bar (#3803, PR #3831)
- [x] [CB-LAND-S4] Pain — 4 role-quote cards + "better way" strip (#3804, PR #3823)
- [x] [CB-LAND-S5] Feature rows — 6 alternating pastel rows with product mockups (#3805, PR #3837)
- [x] [CB-LAND-S6] How It Works — 4-step accordion + synced preview (#3806, PR #3824)
- [x] [CB-LAND-S7] Old vs New comparison split (#3807, PR #3825)
- [x] [CB-LAND-S8] Progress tracking grid — 2×2 (#3808, PR #3826)
- [x] [CB-LAND-S9] Learner-segment tabs — left-stack + right-detail (#3809, PR #3836)
- [x] [CB-LAND-S10] Cross-device + integrations bar (#3810, PR #3835)
- [x] [CB-LAND-S11] Pricing teaser — Free / Family / Board (#3811, PR #3830)
- [x] [CB-LAND-S12] Final CTA band + footer polish (#3812, PR #3827)

**Cross-cutting polish:**
- [x] [CB-LAND-S13] Motion + microinteractions — spring, scanline, reduced-motion (#3813, PR #3866)
- [x] [CB-LAND-S14] Accessibility pass — WCAG 2.1 AA (#3814, PR #3854)
- [x] [CB-LAND-S15] SEO + meta — OG, JSON-LD, lazy-load (#3815, PR #3865)
- [x] [CB-LAND-S16] Analytics — section-view + CTA click events (#3816, PR #3856)
- [x] [CB-LAND-S17] Frontend tests — render / keyboard / reduced-motion / flag on-off (#3817, PR #3860)

**Post-review fixes (filed + merged same-day):**
- [x] [PR-review] #3872 og:image fallback (PR #3876) · #3873 font-load scope (PR #3878) · #3874 default SEO (PR #3877)

**Open fast-follows** (tracked under `CB-LAND-001-fast-follow`): real 1200×630 OG asset (#3875) · real hero screenshot (#3834) · trust-bar data source (#3833) · footer tokens (#3829) · mobile How-It-Works preview (#3832) · S5 FeatureRow polish (#3838) · axe-core automation (#3852) · body-text contrast verification (#3853) · StrictMode-safe hooks (#3858) · headline font decision (#3828) · reduced-motion token docs (#3822) · HomeRedirect auth short-circuit (#3850).


---

