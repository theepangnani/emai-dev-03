### 6.27 Message Email Notifications (Phase 1) - IMPLEMENTED

When a user receives a new in-app message, the system sends an email notification to the recipient (if they have `email_notifications` enabled). This ensures users don't miss important parent-teacher communications.

**Implementation:**
1. When a new message is sent (via `POST /api/messages/conversations/{id}/messages` or new conversation creation), an email is sent to the recipient
2. Respects the recipient's `email_notifications` preference (opt-out)
3. Creates an in-app notification (type: `MESSAGE`) for the recipient with sender name and message preview
4. Email includes sender name, message preview (truncated to 100 chars), and a link to the messages page
5. Dedup: skips duplicate notifications within a 5-minute window for the same sender (avoids spam on rapid-fire messages)
6. Email template matches ClassBridge branding (consistent with password_reset and task_reminder templates)

**Sub-tasks:**
- [x] Backend: Add email + notification dispatch to message send endpoints
- [x] Backend: Create message notification email template
- [x] Backend: Add dedup/batching logic to avoid email spam
- [x] Testing: Add tests for message email notifications (5 tests)

**Key files:**
- `app/api/routes/messages.py` — `_notify_message_recipient()` helper called from send/create endpoints
- `app/templates/message_notification.html` — branded email template
- `tests/test_messages.py` — `TestMessageNotifications` class with 5 tests

### 6.28 Manual Parent-to-Teacher Linking (Phase 1) - IMPLEMENTED

Parents can manually link their child to a teacher by email for direct messaging, bypassing the course enrollment requirement.

**Implementation:**
- `student_teachers` join table: student_id, teacher_user_id, teacher_name, teacher_email, added_by_user_id, created_at
- `POST /api/parent/children/{student_id}/teachers` — link teacher by email
- `GET /api/parent/children/{student_id}/teachers` — list linked teachers
- `DELETE /api/parent/children/{student_id}/teachers/{link_id}` — unlink teacher
- `GET /api/messages/recipients` updated to include directly-linked teachers (both parent→teacher and teacher→parent directions)
- Frontend: "Teachers" section in My Kids page with "Add Teacher" modal

**Relationship model:**
```
Existing: Parent → Child → Course → Teacher (inferred)
New:      Parent → Child → Teacher (direct via student_teachers)
```

**Key files:**
- `app/models/student.py` — `student_teachers` table
- `app/api/routes/parent.py` — CRUD endpoints
- `app/api/routes/messages.py` — updated `get_valid_recipients()`
- `frontend/src/pages/MyKidsPage.tsx` — Teachers section + Add Teacher modal

### 6.28.1 Teacher Linking Email Notifications (Phase 1) - IMPLEMENTED

Enhance the "Add Teacher" flow to send emails when a parent links a teacher to their child.

**Requirements:**
1. **Invitation email for unregistered teachers** (#234)
   - When teacher email is not in the system → create `Invite` record (type=TEACHER) + send branded invitation email
   - Email template: `app/templates/teacher_invite.html` with parent name, child name, accept link
   - On invite acceptance → backfill `teacher_user_id` on existing `student_teachers` rows
2. **Notification email for registered teachers** (#235)
   - When teacher email is in the system → send notification email + create in-app notification
   - Email template: `app/templates/teacher_linked_notification.html` with parent name, child name
   - In-app notification of type SYSTEM for the teacher

**Sub-tasks:**
- [x] Backend: Invitation email for unregistered teachers (#234)
- [x] Backend: Notification email for registered teachers (#235)
- [x] Email templates: `teacher_invite.html`, `teacher_linked_notification.html`
- [x] Backfill `teacher_user_id` on invite acceptance

### 6.29 Teacher Course Roster Management & Teacher Assignment (Phase 1) - IMPLEMENTED

Teachers can manage their course rosters (add/remove students), and courses allow assigning a teacher during or after creation.

**Requirements:**
1. **Teacher adds/removes students from courses** (#225) - IMPLEMENTED
   - `POST /api/courses/{course_id}/students` — add student by email (existing student → enroll + notification; unknown email → send invite with course context)
   - `DELETE /api/courses/{course_id}/students/{student_id}` — remove student
   - Auth: course teacher, admin, or course creator (`_require_course_manager`)
   - Frontend: Student roster section on CourseDetailPage with Add/Remove buttons
2. **Assign teacher to course during creation/editing** (#226) - IMPLEMENTED
   - `teacher_email` field in CourseCreate and CourseUpdate schemas
   - `_resolve_teacher_by_email()` helper: if teacher exists → assign; if unknown → create invite
   - Frontend: optional "Teacher Email" field in course creation form (non-teacher roles) and edit modal
3. **Teacher invite via course context** (#227) - IMPLEMENTED
   - Unknown teacher/student email → create Invite with `metadata_json = {"course_id": id}`
   - On invite acceptance → auto-assign teacher to course / auto-enroll student
   - Email templates: `teacher_course_invite.html`, `student_course_invite.html`

**Sub-tasks:**
- [x] Backend: Teacher course student management (#225)
- [x] Backend: Teacher assignment to course (#226)
- [x] Backend: Course-aware teacher invites (#227)
- [x] Frontend: Course roster UI for teachers
- [x] Frontend: Teacher field in course creation form
- [x] Tests: 17 new tests (TestTeacherAssignment, TestStudentRoster, TestInviteAcceptWithCourse)

### 6.31 My Kids Page Enhancements (Phase 1) - IMPLEMENTED

Improve the My Kids page visual hierarchy and parent navigation for better discoverability.

**Requirements:**
1. **Quick stats on child overview cards** (#236) - IMPLEMENTED
   - Add `course_count` and `active_task_count` to `ChildSummary` API response
   - Display stats on each child card in the All Children grid view
2. **Section header icons** (#237) - IMPLEMENTED
   - Add inline icons to collapsible section headers in child detail view (Courses, Course Materials, Tasks, Teachers)
3. **Parent navigation update** (#237, #529, #530) - IMPLEMENTED
   - Parent nav: Overview | Child Profiles | Courses | Course Materials | Tasks | Messages | Help
   - Previously Courses/Course Materials were removed from parent nav, but user feedback showed parents need direct sidebar access to these pages (#529, #530)

**Sub-tasks:**
- [x] Backend: Add course_count, active_task_count to ChildSummary (#236)
- [x] Frontend: Child card stats display (#236)
- [x] Frontend: Section header icons (#237)
- [x] Frontend: Restore Courses and Course Materials to parent nav (#529, #530)

### 6.31b My Kids Visual Overhaul (Phase 2) - IMPLEMENTED

Visual redesign of the My Kids section on the parent dashboard for improved clarity and usability (#301). Action buttons replaced with + icon popover (#700).

**Requirements:**
1. **Colored child avatars** - IMPLEMENTED
   - Each child gets a unique colored circle with initials (first+last initial)
   - Color assigned from an 8-color palette, consistent across tabs and cards
2. **Enhanced child cards** - IMPLEMENTED
   - Avatar + Name/Grade + School + Stats row (courses, tasks, overdue)
   - Task completion progress bar (computed from `all_tasks` per child)
   - Next deadline countdown ("due today", "due tomorrow", "due in X days", "overdue by Xd")
   - Quick action buttons: Courses, Tasks, Edit
3. **Simplified tabs** - IMPLEMENTED
   - Colored dot matching avatar color before each child name
   - Edit button moved from tab to card actions
4. **+ Icon Popover for actions** - IMPLEMENTED (#700, PR #701)
   - All four action buttons (Add Child, Add Class, Class Materials, Quiz History) replaced with a single + icon popover at the end of the child selector row
   - Uses shared `AddActionButton` component (same pattern as Dashboard and Tasks pages)
5. **Responsive** - Cards single-column on tablet, action buttons horizontal on mobile
6. **Theme compatible** - Works across light, dark, and focus themes

**Sub-tasks:**
- [x] Add CHILD_COLORS palette and getInitials helper
- [x] Add childTaskStats useMemo (completion %, next deadline per child)
- [x] Replace child tabs (color dot, remove edit button)
- [x] Replace child cards with enhanced layout (avatar, progress, deadline, actions)
- [x] CSS: new card styles, responsive breakpoints
- [x] Replace action button grid with + icon popover (#700, PR #701)

### 6.32 Manual Assignment Creation for Teachers (Phase 1) - IMPLEMENTED

Teachers can create, edit, and delete assignments for their courses without Google Classroom sync (#49).

**Requirements:**
1. **Assignment CRUD** — `POST/PUT/DELETE /api/assignments/`
   - Auth: course teacher, course creator, or admin (`_require_course_write`)
   - Create: validates course access, creates Assignment record
   - Update: partial update via `AssignmentUpdate` schema
   - Delete: hard delete with auth check
2. **Student notifications** — enrolled students receive in-app notification when new assignment posted
3. **Assignment list ordering** — sorted by due date (ascending, nulls last), then created_at descending
4. **Frontend: Assignments section on CourseDetailPage**
   - Displays all assignments with title, description, due date, max points
   - Overdue badge shown when due date has passed
   - Google Classroom badge for synced assignments
   - Create/Edit/Delete UI for teachers (hidden for GC-synced assignments)

**Sub-tasks:**
- [x] Backend: AssignmentUpdate schema, PUT/DELETE endpoints (#49)
- [x] Backend: Student notification on new assignment (#49)
- [x] Frontend: assignmentsApi CRUD methods (#49)
- [x] Frontend: Assignments section with create/edit/delete modals (#49)

### 6.33 Parent-Teacher-Course Visibility Flow (Phase 1) - IMPLEMENTED

Documents the end-to-end flow for parent-teacher-course visibility.

**Flow:**
1. **Parent assigns teacher to course** — Parent creates/edits a course with `teacher_email`
   - Teacher exists → assigned immediately (`teacher_id` set, `is_private = false`)
   - Teacher doesn't exist → invite sent with course context; on accept → auto-assigned
2. **Teacher manages roster** — Teacher adds student to course by email
   - Student exists → enrolled immediately (added to `student_courses`)
   - Student doesn't exist → invite sent with course context; on accept → auto-enrolled
3. **Parent sees course** — Parent's dashboard, CoursesPage, and MyKidsPage query courses via `student_courses` join on their children
   - Any course a child is enrolled in automatically appears to the parent
   - Teacher name/email displayed on course cards

**Visibility access rules (from `can_access_course`):**
- Admin → all courses
- Course creator → their courses
- Public courses → visible to all
- Assigned teacher → their courses
- Enrolled student → their courses
- Parent → courses their children are enrolled in

**Known gaps:**
- No parent notification when a teacher adds their child to a course (#238)
- No real-time dashboard refresh (requires page reload)

### 6.34 Course Enrollment (All Roles) (Phase 1) - PARTIAL

Complete enrollment/unenrollment matrix for all roles.

**Enrollment Matrix:**

| Action | Backend | Frontend | Status |
|--------|---------|----------|--------|
| Teacher enrolls student by email | ✅ `POST /courses/{id}/students` | ✅ CourseDetailPage roster | IMPLEMENTED (#225) |
| Teacher removes student | ✅ `DELETE /courses/{id}/students/{sid}` | ✅ CourseDetailPage roster | IMPLEMENTED (#225) |
| Parent assigns course to child | ✅ `POST /parent/children/{sid}/courses` | ✅ CoursesPage assign modal | IMPLEMENTED |
| Parent unassigns course from child | ✅ `DELETE /parent/children/{sid}/courses/{cid}` | ✅ CoursesPage unassign button | IMPLEMENTED |
| Student self-enrolls | ✅ `POST /courses/{id}/enroll` | ✅ CoursesPage browse/enroll | IMPLEMENTED (#250) |
| Student unenrolls self | ✅ `DELETE /courses/{id}/enroll` | ✅ CoursesPage unenroll | IMPLEMENTED (#250) |

**Known gaps:**
- No parent notification when teacher enrolls their child (#238)

**Sub-tasks:**
- [x] Backend: Teacher add/remove students (#225)
- [x] Frontend: Teacher roster management UI (#225)
- [x] Backend: Parent assign/unassign courses
- [x] Frontend: Parent course assignment UI
- [x] Backend: Student self-enroll/unenroll endpoints
- [x] Frontend: Student browse/enroll/unenroll UI (#250)
- [x] Backend: Add visibility check to self-enroll endpoint (#251) — rejects `is_private` courses
- [ ] Backend: Notify parent when teacher enrolls child (#238)

### 6.35 Teacher Invite & Notification System (Phase 1) - PARTIAL

Teachers should be able to invite parents and students to ClassBridge, resend invites on demand, and trigger proper notifications when enrolling students.

**Current state:**

| Flow | Email | In-App | Status |
|------|-------|--------|--------|
| Teacher adds new student to course | ✅ Invite email | — | IMPLEMENTED |
| Teacher adds existing student to course | ❌ | ✅ Notification | PARTIAL (#254) |
| Teacher invites parent | ✅ Invite email | ✅ TeacherDashboard modal | IMPLEMENTED (#252) |
| Resend any invite on demand | ❌ | ❌ | MISSING (#253) |

**Requirements:**
1. **Teacher invites parent to ClassBridge** (#252) — IMPLEMENTED
   - Added `PARENT` to `InviteType` enum
   - `POST /api/invites/invite-parent` — create invite + send email
   - New email template: `parent_invite.html`
   - On acceptance: creates Parent profile, auto-links to student via `metadata_json.student_id`
   - Frontend: "Invite Parent" card on TeacherDashboard with email + student selector modal
2. **Resend/re-invite on demand** (#253)
   - `POST /api/invites/{id}/resend` — refresh expiry, new token, resend email
   - `GET /api/invites/sent` — list invites sent by current user
   - Rate limit: max 1 resend per hour
   - Frontend: "Sent Invites" section with resend button
3. **Email notification on existing student enrollment** (#254)
   - When teacher enrolls existing student in course, send email (not just in-app notification)
   - New template: `student_enrolled_notification.html`

**Sub-tasks:**
- [x] Backend: Add PARENT invite type and teacher-to-parent endpoint (#252)
- [x] Backend: Parent invite email template (#252)
- [x] Backend: Update accept_invite for PARENT type (#252)
- [x] Frontend: Teacher invite parent UI (#252)
- [ ] Backend: Resend invite endpoint with token refresh (#253)
- [ ] Backend: List sent invites endpoint (#253)
- [ ] Frontend: Sent invites dashboard with resend button (#253)
- [ ] Backend: Email notification on existing student enrollment (#254)

### 6.36 Security Hardening Phase 2 (Phase 1) - IMPLEMENTED

Additional security improvements beyond the initial §6.23 risk audit fixes:

#### 6.36.1 Rate Limiting (#140)
- Added `slowapi` rate limiting to authentication endpoints (5/min login, 3/min register)
- AI generation endpoints rate-limited (10/min per user)
- File upload endpoints rate-limited (20/min per user)
- Rate limit headers returned in responses (X-RateLimit-Limit, X-RateLimit-Remaining)

#### 6.36.2 Security Headers (#141)
- Added security middleware with HSTS (`Strict-Transport-Security`), CSP (`Content-Security-Policy`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, `Referrer-Policy`
- Headers applied globally via FastAPI middleware

#### 6.36.3 LIKE Pattern Injection Fix (#184)
- Escaped `%` and `_` wildcards in user-supplied search terms before passing to SQL LIKE clauses
- Applied to global search, study guide search, and course content search endpoints

### 6.37 Task Reminders (Phase 1) - IMPLEMENTED

Daily background job that sends in-app notifications for upcoming task due dates (#112).

**Implementation:**
- **Background job:** APScheduler job runs daily at 8:00 AM, checks tasks with due dates 1 or 3 days away
- **User preference:** `task_reminder_days` column on User model (default `"1,3"`) — comma-separated days before due date to notify
- **Notification type:** `TASK_DUE` added to `NotificationType` enum
- **Scope:** Sends to task creator and assigned user (deduped if same person)
- **Skips:** Already-completed tasks, tasks with no due date, tasks where reminder already sent (dedup via title+link matching)

**Files:**
- `app/jobs/task_reminders.py` — reminder job logic
- `app/models/user.py` — `task_reminder_days` column
- `app/models/notification.py` — `TASK_DUE` enum value
- `main.py` — APScheduler registration + DB migration for new column

### 6.38 Infrastructure & Reliability (Phase 1) - IMPLEMENTED

Cross-cutting infrastructure improvements for email delivery, auth, UX, testing, and mobile support.

#### 6.38.1 Email Delivery (#213-#217)
- Fixed SendGrid delivery: use synchronous `sg.send()` calls from synchronous FastAPI endpoints (async `SendGridAPIClientAsync` caused silent failures)
- Added Gmail SMTP fallback when SendGrid API key is unavailable or fails
- Parent invite emails now sent automatically when parent creates or links a child
- SMTP environment secrets added to Cloud Run deployment workflow

#### 6.38.2 JWT Token Refresh (#149)
- Added `POST /api/auth/refresh` endpoint that accepts a refresh token and returns new access + refresh tokens
- Refresh tokens have 30-day expiry (vs 24-hour access tokens)
- Frontend Axios interceptor auto-refreshes on 401 responses before retrying the failed request
- Refresh token stored in localStorage alongside access token

#### 6.38.3 Loading Skeletons (#150, #218)
- Replaced text "Loading..." states with animated skeleton screens
- `PageSkeleton` and `ListSkeleton` reusable components in `components/Skeleton.tsx`
- Applied to: StudentDashboard, MessagesPage, QuizPage, FlashcardsPage, CourseDetailPage, MyKidsPage

#### 6.38.4 Mobile Responsive CSS (#152)
- Added CSS breakpoints (`@media (max-width: 768px)` and `(max-width: 480px)`) to 5+ CSS files
- Responsive layout for DashboardLayout, CalendarSection, TasksPage, CoursesPage, MessagesPage
- Touch-friendly tap targets (min 44px), stacked layouts on small screens

#### 6.38.5 Backend Test Expansion (#155)
- Expanded `pytest` route tests from ~220 to ~288+ tests
- Added test coverage for: messages (send, list, conversations), notifications (list, mark read), study guides (generate, list), Google integration endpoints, admin routes, invite acceptance flow

### 6.39 Bug Fixes & Ad-hoc Improvements (Feb 11-12, 2026)

Defect fixes and ad-hoc improvements made during this development sprint:

| Fix | Description | Commit |
|-----|-------------|--------|
| Google OAuth double login | OAuth callback redirect required user to log in again; fixed to auto-set token | `9a317a1` |
| Password reset crash | `audit_logs.action` column was VARCHAR(20), too short for `"password_reset_request"` → widened to VARCHAR(50) | `7433746` |
| Role switcher not appearing | Local SQLite missing `task_reminder_days` column caused `/me` endpoint to crash silently; frontend never received `roles` array | `12b8d31` |
| Admin promotion | One-time migration to set `theepang@gmail.com` as admin+teacher in all environments | `12b8d31` |
| CSS variable mismatches | MyKidsPage.css used undefined CSS variables (`--card-bg`, `--border-color`, etc.) instead of design system vars (`--color-surface`, `--color-border`, etc.) | `29635f9` |
| Dashboard count mismatch (#208) | Overdue/due-today counts on parent dashboard didn't match TasksPage totals; fixed to use same query logic | `078545a` |
| Dashboard count child filter (#208) | Overdue/due-today counts didn't respond to child filter selection | `6376d0e` |
| Assignee filter (#209) | Added assignee dropdown filter to TasksPage for filtering tasks by student | `9677314` |
| Calendar default expanded (#207) | Calendar section defaulted to collapsed on some screen sizes; fixed to always start expanded | `4369eb5` |
| Task inline edit (#210) | Added inline edit mode to Task Detail page — edit button toggles card into form with all fields | `ba3cae8` |
| Inspiration messages Docker | `data/` directory not included in Docker image; added COPY directive and handled admin role in inspiration API | `a5b2f5d` |
| TypeScript build fix | Added `refresh_token` to `acceptInvite` return type and `loginWithToken` signature | `95a9618` |

### 6.40 Admin Messaging: Broadcast & Individual (Phase 1)

Admin users can send messages to all platform users (broadcast) or to individual users. All recipients with a valid email address will also receive the message via email.

**Backend:**
- **Broadcast endpoint:** `POST /api/admin/broadcast` — Admin-only. Accepts `subject` and `body` (HTML-safe). Creates an in-app notification for every active user and sends an email to all users with a non-null email address. Returns count of notifications created and emails sent.
- **Individual message endpoint:** `POST /api/admin/users/{user_id}/message` — Admin-only. Accepts `subject` and `body`. Creates an in-app notification for the target user and sends an email if the user has an email address.
- **Broadcast history:** `GET /api/admin/broadcasts` — List past broadcasts with timestamp, subject, recipient count.
- Email is sent asynchronously (background) to avoid request timeout for large user bases.
- Uses existing `send_email_sync` from `email_service.py` with the configured `FROM_EMAIL` (clazzbridge@gmail.com).
- Audit log entries created for both broadcast and individual messages.

**Frontend (AdminDashboard):**
- **"Send Broadcast" button** on Admin Dashboard — opens a modal with subject + rich-text body fields, preview, and "Send to All Users" confirmation.
- **"Send Message" action** per user row in the user management table — opens a modal to compose a message to that specific user.
- **Broadcast history section** — collapsible section showing past broadcasts with date, subject, and recipient count.
- Success/error toast notifications after send.

**Sub-tasks:**
- [x] Backend: Broadcast endpoint with email delivery (#258)
- [x] Backend: Individual admin-to-user message endpoint (#259)
- [x] Backend: Broadcast history endpoint (#258)
- [x] Frontend: Broadcast modal on Admin Dashboard (#258)
- [x] Frontend: Individual message modal in user table (#259)

### 6.41 Inspirational Messages in Emails (Phase 1)

All outgoing emails from ClassBridge should include a role-based inspirational message (from the existing `InspirationMessage` system) as a footer/tagline. The message is selected based on the **recipient's role** and rotated randomly.

**Backend:**
- Update `send_email_sync()` (or individual callers) to accept an optional `recipient_role` parameter.
- When `recipient_role` is provided, query a random active `InspirationMessage` for that role using the existing `get_random_message(db, role)` service.
- Inject the inspirational quote into the email HTML as a styled footer block (italic quote with optional author attribution).
- Applies to **all** email types: message notifications, broadcast, individual admin messages, password reset, assignment reminders, task reminders, invite emails, teacher linked notifications, and student enrollment notifications.
- If no inspirational message is found for the role, omit the section gracefully.

**Email template update:**
- Add a shared inspirational footer block to all email templates (or inject programmatically before the closing `</body>` tag):
  ```html
  <tr>
    <td style="padding: 16px 32px; text-align: center;">
      <p style="color: #999; font-size: 13px; font-style: italic; margin: 0;">
        "{{inspiration_text}}"
        {{#if inspiration_author}} — {{inspiration_author}}{{/if}}
      </p>
    </td>
  </tr>
  ```

**Sub-tasks:**
- [x] Backend: Add inspiration message injection to email service (#260) (IMPLEMENTED)
- [x] Templates: Update all 8+ email templates with inspiration footer (#260) (IMPLEMENTED)

### 6.42 Admin Messaging Improvements: Notification Modal, User-to-Admin Messaging (Phase 1)

Enhance the admin messaging system so notifications open in a popup modal, all users can see admin messages in the Messages page, and any user can send a message to the admin team with email notification to all admins.

**A. Notification Click → Popup Modal (#261)**

When a user clicks on a notification (in the NotificationBell dropdown), the full message should open in a popup modal overlay instead of expanding inline or navigating away.

- **Frontend (NotificationBell):** Clicking any notification opens a centered modal showing:
  - Notification title (bold header)
  - Full notification content (body text, no truncation)
  - Timestamp
  - "Close" button and click-outside-to-dismiss
  - If notification has a `link`, show a "Go to…" action button in the modal footer
- **Marks as read** on open (existing behavior preserved)
- **CSS:** Uses shared `.modal-overlay` / `.modal` pattern from `Dashboard.css`

**B. Messages Page: Show All Admin Messages (#262)**

When any user opens the Messages page, they must see conversations from all admin users — not just teachers/parents they have explicit relationships with.

- **Backend (`messages.py`):** Update `list_conversations` to include conversations where the other participant is an admin user. Currently conversations are filtered only by participant ID match — this already works since admin messages now create Conversation records. No query change needed if conversations are created correctly.
- **Backend (`messages.py`):** Update `get_valid_recipients` to include admin users in the recipient list for all roles — so users can initiate conversations with admins from the "New Conversation" modal.
- **Frontend (MessagesPage):** No structural changes — admin conversations will appear naturally in the list. Admin users should display with an "Admin" badge or label in the conversation list for clarity.

**C. Any User Can Message Admin (#263)**

Any authenticated user (parent, student, teacher) can send a message to any admin. All admin users receive the message in their Messages page AND receive an email notification.

- **Backend (`messages.py`):**
  - Update `get_valid_recipients` to always include all admin users as valid recipients for every authenticated user (regardless of role or relationships).
  - When a message is sent to an admin, also deliver the message (as a new Conversation or appended message) to **all other admin users** and send them email notifications.
  - New helper: `_notify_all_admins(db, sender, message_content, conversation_id)` — creates notifications and sends emails to all admin users except the sender.
- **Backend (email):** Use existing `send_email_sync` for individual admin emails, or `send_emails_batch` if notifying multiple admins.
- **Frontend (MessagesPage):** Admin users appear in the recipient list with an "Admin" badge. Selecting any admin as recipient sends to all admins.

**Sub-tasks:**
- [ ] Frontend: Notification click opens popup modal (#261)
- [x] Backend + Frontend: Show admin messages in Messages page (#262)
- [x] Backend + Frontend: User-to-admin messaging with email to all admins (#263)

### 6.43 Simplified Registration & Post-Login Onboarding (Phase 1)

Simplify the registration flow to reduce friction and reinforce ClassBridge as a **parent-first platform**. Role selection moves from the registration form to a post-login onboarding screen.

**GitHub Issues:** #412 (simplified registration), #413 (onboarding UI), #414 (backend onboarding endpoint)

#### Current State (Before)
- Registration form collects: name, email, password, role checkboxes (Parent/Student/Teacher), teacher type dropdown
- Roles are required at registration — `ensure_profile_records()` runs immediately
- Users must understand platform roles before signing up

#### New Flow (After)

```
1. REGISTER  →  Name, Email, Password (no role selection)
2. AUTO-LOGIN
3. ONBOARDING SCREEN  →  "How will you use ClassBridge?"
     [🏠 Parent / Guardian]    ← Prominent, recommended (parent-first)
     [📚 Teacher]
     [🎓 Student]
   If Teacher selected  →  "What type of teacher?"
     [School Teacher]  — "I teach at a school"
     [Private Tutor]   — "I teach independently"
4. REDIRECT  →  Role-specific dashboard
```

#### Design Principles
- **Parent-first**: Parent option is visually prominent (first position, highlighted/recommended badge)
- **Low-friction signup**: Only 4 fields at registration (name, email, password, confirm password)
- **Deferred role assignment**: User record created without a role; role set during onboarding
- **Multi-role support**: Onboarding allows selecting multiple roles (e.g., parent + teacher)
- **Teacher types**: School Teacher and Private Tutor — selected only when Teacher role is chosen
- **Not skippable**: Role is required to access any dashboard; users are redirected to onboarding until complete

#### Backend Changes

**Registration (`POST /api/auth/register`):**
- `roles` and `teacher_type` become optional (backward compatible)
- When no roles provided: create User with `role=NULL`, `roles=""`, `needs_onboarding=TRUE`
- Skip `ensure_profile_records()` when no role is set

**New endpoint (`POST /api/auth/onboarding`):**
- Auth: requires valid JWT
- Accepts: `roles: list[str]`, `teacher_type: str | None`
- Validates: at least one role, no admin self-assignment, teacher_type required if teacher
- Actions: set user.role + user.roles, call `ensure_profile_records()`, set teacher_type if applicable, clear `needs_onboarding`
- Audit log: `action="onboarding_complete"`

**User model:**
- New column: `needs_onboarding` (Boolean, default FALSE)
- DB migration in `main.py` startup block
- Included in UserResponse schema and all auth responses (login, register, /me)

**Auth responses:**
- `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me` all include `needs_onboarding` flag

#### Frontend Changes

**Register.tsx:**
- Remove role checkboxes and teacher type dropdown
- Fields: Full Name, Email, Password, Confirm Password only

**New OnboardingPage.tsx (`/onboarding`):**
- Role selection cards with icons (Parent prominent/first)
- Conditional teacher type sub-selection
- Multi-role checkbox support
- Calls `POST /api/auth/onboarding` on completion
- Redirects to role-specific dashboard
- Matches auth page styling (logo, centered card, theme-aware)

**AuthContext / ProtectedRoute:**
- Check `needs_onboarding` flag from auth response
- Redirect users with `needs_onboarding=true` to `/onboarding`
- Existing users with roles skip onboarding entirely

#### Backward Compatibility
- API still accepts roles at registration (for programmatic/test use)
- Existing users with roles already set have `needs_onboarding=false` (backfill migration)
- Mobile app not affected (registration is web-only per §9.6)

**Sub-tasks:**
- [x] Backend: Make roles optional in registration, add `needs_onboarding` column (#412)
- [x] Backend: `POST /api/auth/onboarding` endpoint with validation and profile creation (#414)
- [x] Frontend: Simplify Register.tsx to 4 fields (#412)
- [x] Frontend: OnboardingPage.tsx with role cards and teacher type selection (#413)
- [x] Frontend: AuthContext/ProtectedRoute onboarding redirect (#413)
- [x] Tests: Onboarding endpoint (happy path, validation, backward compat)

### 6.44 Email Verification (Soft Gate) (Phase 1) - IMPLEMENTED

Verify new users' email addresses after registration using a "soft gate" approach — users can log in without verification but see a persistent dashboard banner reminding them to verify.

**GitHub Issue:** #417

**Flow:**
1. User registers → verification email sent with 24-hour JWT link
2. User can log in immediately (no blocking)
3. Dashboard shows yellow banner: "Please verify your email. [Resend email]"
4. Clicking the email link → `/verify-email?token=...` → email verified
5. Banner disappears after verification

**Backend:**
- **Model:** `email_verified` (Boolean, default `false`) and `email_verified_at` (DateTime, nullable) on User
- **Migration:** `ALTER TABLE users ADD COLUMN email_verified/email_verified_at` + grandfather existing users as verified
- **Token:** `create_email_verification_token(email)` / `decode_email_verification_token(token)` in `security.py` (24h expiry JWT)
- **Template:** `app/templates/email_verification.html` (ClassBridge branded, matches password_reset pattern)
- **Endpoints:**
  - `POST /api/auth/verify-email` (public) — accepts `{token}`, verifies user email
  - `POST /api/auth/resend-verification` (authenticated, rate-limited 3/min) — resends verification email
- **Registration:** sends verification email after successful signup (best-effort, non-blocking)
- **Auto-verify:** Google OAuth users and invite-accepted users are auto-verified (email already confirmed)
- **Schema:** `email_verified: bool` added to `UserResponse`

**Frontend:**
- **VerifyEmailPage** (`/verify-email?token=...`) — public page, shows success/error/loading states
- **AuthContext:** `email_verified: boolean` on User interface, `resendVerification()` method
- **DashboardLayout:** yellow verification banner with resend button, dismissable per session
- **Routing:** `/verify-email` added as public route in App.tsx

**Sub-tasks:**
- [x] Backend: Add `email_verified`/`email_verified_at` columns + migration + grandfathering (#417)
- [x] Backend: JWT token functions for email verification (#417)
- [x] Backend: `POST /verify-email` and `POST /resend-verification` endpoints (#417)
- [x] Backend: Send verification email on registration, auto-verify Google/invite users (#417)
- [x] Frontend: VerifyEmailPage, AuthContext, DashboardLayout banner, routing (#417)
- [x] Tests: 11 backend tests covering all verification scenarios (#417)

### 6.45 Show/Hide Password Toggle (Phase 1)

Add a clickable eye icon to all password input fields across authentication pages, allowing users to toggle between masked (`••••••`) and visible (plain text) password display. This improves usability — especially on mobile — by letting users verify what they typed before submitting.

**GitHub Issue:** #420

**Affected Pages (4 pages, 7 password fields):**

| Page | File | Fields |
|------|------|--------|
| Login | `Login.tsx` | Password (1) |
| Register | `Register.tsx` | Password, Confirm Password (2) |
| Reset Password | `ResetPasswordPage.tsx` | New Password, Confirm Password (2) |
| Accept Invite | `AcceptInvite.tsx` | Password, Confirm Password (2) |

**Implementation:**

- **Toggle icon:** An eye icon (open = visible, closed/slash = hidden) positioned inside the input field on the right side
- **Default state:** Password is hidden (`type="password"`)
- **Toggle behavior:** Clicking the icon switches between `type="password"` and `type="text"`
- **Independent toggles:** Each password field has its own independent show/hide state (e.g., toggling Password does not toggle Confirm Password)
- **Accessibility:** Icon button has `aria-label="Show password"` / `aria-label="Hide password"` and is keyboard-focusable
- **Styling:** Icon uses existing CSS variables for theming (works in light, dark, and focus modes). Input field gets `padding-right` to prevent text from overlapping the icon

**Frontend Changes:**

- **Reusable `PasswordInput` component** (or inline per page): wraps a standard `<input>` with a toggle button overlay
- **CSS:** `.password-input-wrapper` with relative positioning; `.password-toggle-btn` absolutely positioned inside the input
- **State:** `useState<boolean>(false)` per password field — `showPassword`, `showConfirmPassword`
- **No backend changes required** — this is a purely frontend UX enhancement

**Sub-tasks:**
- [ ] Frontend: Add show/hide toggle to Login.tsx password field (#420)
- [ ] Frontend: Add show/hide toggle to Register.tsx password + confirm fields (#420)
- [ ] Frontend: Add show/hide toggle to ResetPasswordPage.tsx fields (#420)
- [ ] Frontend: Add show/hide toggle to AcceptInvite.tsx fields (#420)
- [ ] Tests: Update existing tests to verify toggle functionality (#420)

### 6.46 Lottie Animation Loader (Phase 2)

Replace the current ⏳ emoji + CSS pulsing text animation during AI study material generation with a polished Lottie animation. A reusable `LottieLoader` component provides a professional, branded loading experience.

**GitHub Issues:** #424 (web), #425 (mobile, backlogged)

**Lottie Animation Asset:**
- Education/book/loading themed animation matching ClassBridge brand colors (teal `#49b8c0`)
- Stored at `frontend/public/animations/classbridge-loader.json`
- File size target: under 50KB

**Reusable Component (`frontend/src/components/LottieLoader.tsx`):**
- Uses `lottie-react` package
- Props: `size` (default 140px), `loop` (default true), `autoplay` (default true)
- Theme-aware (works in light, dark, focus modes)

**Integration Points:**

| Location | Current | After Lottie | Priority |
|----------|---------|-------------|----------|
| StudyGuidesPage generating row | ⏳ emoji + pulsing text | Lottie animation (~40px) + text | Primary |
| PageLoader (full-page) | Skeleton lines | Centered Lottie (~100px) | Secondary |
| CourseMaterialDetailPage | Skeleton | Lottie animation | Optional |

**Files Affected:**
- `frontend/package.json` — add `lottie-react`
- `frontend/public/animations/classbridge-loader.json` — new animation asset
- `frontend/src/components/LottieLoader.tsx` — new component
- `frontend/src/pages/StudyGuidesPage.tsx` — replace generating row icon
- `frontend/src/pages/StudyGuidesPage.css` — update generating row styles
- `frontend/src/components/PageLoader.tsx` — optional enhancement

**Sub-tasks:**
- [ ] Obtain/create Lottie animation JSON asset for ClassBridge (#424)
- [ ] Install `lottie-react` and create reusable `LottieLoader` component (#424)
- [ ] Replace AI generation placeholder in StudyGuidesPage with Lottie animation (#424)
- [ ] (Optional) Enhance PageLoader with Lottie animation (#424)
- [ ] Test across all 3 themes (light, dark, focus) (#424)
- [ ] Mobile: Add Lottie loader to ClassBridgeMobile (backlogged, #425)

### 6.30 Role-Based Inspirational Messages (Phase 2) - IMPLEMENTED

Replace the static "Welcome back" dashboard greeting with role-specific inspirational messages that rotate on each visit. Messages are maintained in JSON seed files and imported into the database. Admins can manage messages via the admin dashboard.

**Implementation:**
- **Model:** `InspirationMessage` (id, role, text, author, is_active, created_at, updated_at) in `app/models/inspiration_message.py`
- **Seed files:** `data/inspiration/{parent,teacher,student}.json` — 20 messages per role
- **Service:** `app/services/inspiration_service.py` — `seed_messages()` (auto-imports on startup if table empty), `get_random_message(db, role)`
- **API routes:** `app/api/routes/inspiration.py` under `/api/inspiration`
  - `GET /random` — random active message for current user's role (any authenticated user)
  - `GET /messages` — list all messages with role/is_active filters (admin only)
  - `POST /messages` — create new message (admin only)
  - `PATCH /messages/{id}` — update text/author/is_active (admin only)
  - `DELETE /messages/{id}` — delete message (admin only)
  - `POST /seed` — re-import from seed files (admin only, skips if non-empty)
- **Frontend:** `DashboardLayout.tsx` fetches random message on mount, replaces "Welcome back" with italicized quote and author attribution. Falls back to "Welcome back" if no messages.
- **Admin page:** `/admin/inspiration` — full CRUD management with role filter, inline active/inactive toggle, add/edit/delete. Linked from Admin Dashboard.
- **Tests:** 16 tests in `tests/test_inspiration.py` covering random retrieval by role, inactive filtering, admin CRUD, role validation, access control.

**Sub-tasks:**
- [x] Backend: Inspiration model, service, API (#230)
- [x] Data: Seed JSON files per role (#231)
- [x] Frontend: Dashboard greeting integration (#232)
- [x] Backend + Frontend: Admin CRUD + re-import (#233)

### 6.47 Course Planning & Guidance for High School (Phase 3)

Help parents guide their high school children through course selection — from individual semester choices to a complete Grade 9-12 academic plan. All recommendations and course catalogs are scoped to the student's **school board** (e.g., TDSB, PDSB, YRDSB), since each board offers different courses, electives, and specialized programs. AI-powered recommendations ensure students stay on track for graduation and post-secondary goals.

**Design Principles:**
- **Parent-first**: Parents are the primary users; students can also self-plan
- **School board-scoped**: Course catalogs, recommendations, and validation are tied to the student's specific school board — different boards offer different courses and pathways
- **Ontario OSSD focus**: Built around Ontario graduation requirements; extensible to other provinces
- **AI-assisted, not AI-driven**: AI recommends based on board offerings, parents decide
- **Progressive planning**: Start with one semester, build up to a full 4-year plan
- **Integrated**: Connects to existing ClassBridge data (courses, grades, analytics)

#### 6.47.1 School Board Integration (Phase 3) — #511

All course planning is scoped to the student's school board. Depends on Issue #113 (School & School Board model).

**Data Model — `school_boards` table:**
- `id` (PK), `name` (String — e.g., "Toronto District School Board")
- `abbreviation` (String — e.g., "TDSB"), `province` (String — default "Ontario")
- `website_url` (String, nullable), `course_catalog_url` (String, nullable — link to board's official course calendar)
- `graduation_requirements_json` (JSON, nullable — board-specific requirements beyond OSSD)
- `created_at`, `updated_at`

**Student ↔ School Board:**
- `students.school_board_id` (FK → school_boards.id, nullable) — set by parent in Edit Child modal
- `students.school_name` (String, nullable) — specific school within the board
- If no board selected, show all Ontario courses with a prompt to select a board for better recommendations

**Seed Boards:** TDSB, PDSB, YRDSB, HDSB, OCDSB — each with their published course calendar.

**API:**
- `GET /api/school-boards/` — List all boards (for dropdown)
- `GET /api/school-boards/{id}` — Board detail
- `PATCH /api/parent/children/{id}` — Accept `school_board_id` field

#### 6.47.2 Course Catalog (Phase 3) — #500

Board-specific database of available high school courses with prerequisites, credits, and metadata. Each school board has its own catalog — different boards offer different electives, specialized programs, and pathways.

**Data Model — `course_catalog` table:**
- `id` (PK), `course_code` (String — e.g., "SBI3U", "MPM2D")
- `course_name` (String — e.g., "Biology, Grade 11, University Prep")
- `description` (Text), `grade_level` (Integer — 9-12)
- `course_type` (String — mandatory, elective, AP, IB, college_prep, university_prep, open)
- `credits` (Float — typically 1.0), `subject_area` (String — Science, Mathematics, English, Arts, etc.)
- `stream` (String — academic, applied, open, locally_developed)
- `is_mandatory` (Boolean), `prerequisites_json` (JSON — array of course_code strings)
- `corequisites_json` (JSON)
- `school_board_id` (FK → school_boards.id) — **required**; every catalog course belongs to a board
- `availability` (String — all_schools, select_schools, online_only)
- `special_program` (String, nullable — IB, AP, French Immersion, SHSM)
- `province` (String — default "Ontario")
- `created_at`, `updated_at`
- Unique constraint on (`school_board_id`, `course_code`)

**Seed Data:** Ontario OSSD Grade 9-12 courses per board, including board-specific electives and prerequisite chains (e.g., MPM1D → MPM2D → MCR3U → MHF4U/MCV4U).

**API Endpoints:**
- `GET /api/course-catalog/?school_board_id=X` — List filtered by board (+ grade_level, subject_area, course_type, stream)
- `GET /api/course-catalog/{id}` — Detail with prerequisites resolved to full course objects

#### 6.47.3 Academic Plans (Phase 3) — #501

Multi-year course plan per student, created by parents or students.

**Data Model — `academic_plans` table:**
- `id` (PK), `student_id` (FK → students), `created_by_user_id` (FK → users)
- `plan_name` (String), `start_grade` / `end_grade` (Integer), `graduation_target` (String — "OSSD")
- `post_secondary_goal` (String, nullable — e.g., "Engineering at UofT")
- `status` (String — draft, active, completed, archived), `notes` (Text, nullable)
- `created_at`, `updated_at`

**Data Model — `planned_courses` table:**
- `id` (PK), `academic_plan_id` (FK → academic_plans, CASCADE)
- `catalog_course_id` (FK → course_catalog, nullable), `custom_course_name` (String, nullable)
- `grade_level` (Integer — 9-12), `semester` (Integer — 1 or 2)
- `status` (String — planned, in_progress, completed, dropped)
- `actual_grade` (Float, nullable), `notes` (String, nullable)
- `created_at`, `updated_at`

**RBAC:** Parents create/edit plans for linked children. Students create/edit own plans. Teachers view plans of students in their courses (read-only).

**API Endpoints:**
- `POST /api/academic-plans/` — Create plan
- `GET /api/academic-plans/` — List plans (RBAC-filtered)
- `GET /api/academic-plans/{id}` — Detail with all planned courses
- `PATCH /api/academic-plans/{id}` — Update plan metadata
- `DELETE /api/academic-plans/{id}` — Soft delete
- `POST /api/academic-plans/{id}/courses` — Add course to plan
- `PATCH /api/academic-plans/{id}/courses/{course_id}` — Update planned course
- `DELETE /api/academic-plans/{id}/courses/{course_id}` — Remove course from plan

#### 6.47.4 Prerequisite & Graduation Requirements Engine (Phase 3) — #502

Validates academic plans against Ontario OSSD graduation requirements and prerequisite chains.

**Ontario OSSD Requirements:**
- 30 total credits (18 compulsory + 12 elective)
- Compulsory: 4 English, 3 Math, 2 Science, 1 French, 1 Canadian History, 1 Canadian Geography, 1 Arts, 1 HPE, 0.5 Civics, 0.5 Career Studies + 3 from designated groups
- 40 hours community involvement
- OSSLT (literacy test) pass

**Validation Service (`app/services/graduation_service.py`):**
- `validate_plan(plan_id)` → total credits, compulsory checklist, prerequisite violations, schedule conflicts, missing requirements, completion percentage
- `check_prerequisites(catalog_course_id, student_completed_courses)` → eligible boolean + missing prerequisites

**API:**
- `GET /api/academic-plans/{id}/validate` — Full plan validation report
- `GET /api/course-catalog/{id}/check-prerequisites?student_id=X` — Eligibility check

#### 6.47.5 AI Course Recommendations (Phase 3) — #503

Personalized, **board-specific** course guidance using student grades, goals, and ClassBridge analytics data.

**AI Service (`app/services/course_advisor_service.py`):**
- Inputs: student's school board + its course catalog, completed courses + grades, current plan, post-secondary goal, strengths/weaknesses (from analytics), graduation status
- Outputs: Top recommended courses **from the student's board catalog** with reasoning, pathway analysis, risk alerts, alternative paths, workload balance assessment
- AI prompt includes board context: "Based on [Board Name]'s course offerings for Grade [X]..."
- Uses gpt-4o-mini, on-demand generation (same cost-conscious pattern as analytics AI insights)
- Fallback: if no board selected, use generic Ontario OSSD courses with a note to set the board

**API:**
- `POST /api/course-planning/recommend` — `{ student_id, plan_id, target_grade, target_semester }` → recommendations
- `POST /api/course-planning/pathway-analysis` — `{ student_id, plan_id }` → full pathway review

#### 6.47.6 University Pathway Alignment (Phase 3) — #506

Map course plans against post-secondary program admission requirements.

**Data Model — `program_requirements` table:**
- `id`, `institution_name`, `program_name`, `faculty`
- `required_courses_json`, `recommended_courses_json`, `minimum_average`
- `prerequisite_courses_json`, `notes`, `url`, `province`

**Features:**
- Program search by institution, faculty, field of interest
- Alignment check: ✅ planned/completed, ❌ missing, ⚠️ grade below competitive average
- Gap analysis with actionable recommendations
- Multi-program comparison (2-3 programs side-by-side)

**Seed Data:** Top 10-15 Ontario university programs.

**API:**
- `GET /api/program-requirements/` — List/search
- `GET /api/academic-plans/{id}/alignment?program_id=X` — Alignment check
- `GET /api/academic-plans/{id}/alignment/compare?program_ids=X,Y,Z` — Multi-program comparison

#### 6.47.7 Frontend — Semester Planner (Phase 3) — #504

Route: `/course-planning/semester/:planId/:gradeLevel/:semester`

- Course selection panel: browse available courses filtered by grade, search, prerequisite indicators (met ✅ / unmet ❌)
- Semester schedule view: selected courses, total credits, workload balance indicator, remove button
- Validation sidebar: real-time prerequisite check, graduation progress bar, warnings, AI recommendation prompt
- Parent child selector dropdown (same pattern as analytics)

#### 6.47.8 Frontend — Multi-Year Planner (Phase 3) — #505

Route: `/course-planning/:planId`

- 4-column grid (Grade 9-12) with semester rows; course cards showing name, code, credits, status badge
- Prerequisite arrows/connections across grades
- Color-coded by subject area
- Top progress dashboard: credits (X/30), compulsory checklist, graduation readiness %, post-secondary alignment score
- Actions: Add Course, Get AI Recommendations, Validate Plan, Export PDF, Share with Teacher
- Drag-and-drop courses between semesters

#### 6.47.9 Navigation & Dashboard Integration (Phase 3) — #507

- "Course Planning" in DashboardLayout left nav (parent + student)
- `/course-planning` landing page: children's plan list (parent) or own plan (student)
- My Kids page: "Course Plan" button on child cards
- Parent Dashboard: "Plan Courses" quick action

**GitHub Issues:** #500 (catalog model), #501 (academic plan model), #502 (graduation engine), #503 (AI recommendations), #504 (semester planner UI), #505 (multi-year planner UI), #506 (university alignment), #507 (navigation integration), #508 (tests), #511 (school board integration)

### 6.48 Welcome & Verification Acknowledgement Emails (Phase 1)

Send branded lifecycle emails at two key registration milestones to welcome users and drive engagement with ClassBridge features.

**GitHub Issues:** #509 (welcome email on registration), #510 (acknowledgement email after verification)

#### 6.48.1 Welcome Email on Registration — #509

Immediately after a user registers on ClassBridge, send a branded welcome email introducing the platform and encouraging them to get started. This is sent alongside the existing verification email (§6.44) and serves a different purpose — the verification email asks them to confirm their address, while the welcome email introduces ClassBridge features.

**Template:** `app/templates/welcome.html`

**Content:**
- Greeting: "Welcome to ClassBridge, {{user_name}}!"
- Brief intro: "ClassBridge connects parents, students, and teachers in one platform"
- Feature highlights (3-4 bullet points with icons):
  - AI-powered study tools (study guides, quizzes, flashcards)
  - Google Classroom integration
  - Parent-teacher messaging
  - Task management & calendar
- CTA button: "Get Started" → `{{app_url}}/login`
- Footer: inspiration message via `add_inspiration_to_email()`

**Backend:**
- Create `app/templates/welcome.html` matching existing email template style (ClassBridge logo, indigo `#4f46e5` accent bar, white card, responsive table layout)
- In `auth.py` `register()`: call `send_email_sync()` with welcome template after registration (after verification email send, non-blocking best-effort)
- Skip for Google OAuth signups (they already went through the Google consent flow)

**Subject line:** "Welcome to ClassBridge — Let's Get Started!"

#### 6.48.2 Verification Acknowledgement Email — #510

After a user successfully verifies their email via the verification link (§6.44), send a detailed acknowledgement/marketing email confirming verification and showcasing ClassBridge features to drive first-session engagement.

**Template:** `app/templates/email_verified_welcome.html`

**Content:**
- Greeting: "Hi {{user_name}}, your email is verified!"
- Confirmation message: "You're all set — your ClassBridge account is fully activated"
- Detailed feature showcase (with descriptive paragraphs, not just bullets):
  - AI Study Tools — Generate study guides, practice quizzes, and flashcards from any course material
  - Google Classroom — Import courses, assignments, and grades with one click
  - Smart Calendar — Track assignments and tasks across all courses in one view
  - Parent-Teacher Messaging — Communicate directly with teachers in a secure channel
  - Task Management — Create tasks, set reminders, and stay organized
- CTA button: "Explore Your Dashboard" → `{{app_url}}/dashboard`
- Footer: inspiration message via `add_inspiration_to_email()`

**Backend:**
- Create `app/templates/email_verified_welcome.html` matching existing email template style
- In `auth.py` `verify_email()`: send acknowledgement email after successful verification (non-blocking best-effort)
- Do NOT send if verification fails (bad token, expired token, already verified)

**Subject line:** "You're Verified — Explore Everything ClassBridge Has to Offer"

**Sub-tasks:**
- [ ] Backend: Create `welcome.html` email template (#509)
- [ ] Backend: Send welcome email on registration in `auth.py` (#509)
- [ ] Backend: Create `email_verified_welcome.html` email template (#510)
- [ ] Backend: Send acknowledgement email on verification in `auth.py` (#510)
- [ ] Tests: Welcome email on registration (sent, skipped for Google OAuth) (#509)
- [ ] Tests: Acknowledgement email on verification (sent on success, skipped on failure) (#510)

### 6.49 Admin Email Template Management (Phase 2)

Allow admin users to view all email templates and edit their content directly from the Admin Dashboard, without requiring code deployments. Templates are HTML files with `{{placeholder}}` variables.

**GitHub Issue:** #513

**Current State:**
- 14 email templates live as static HTML files in `app/templates/`
- Templates use `{{placeholder}}` variables rendered via simple string replacement (`_render()` in `auth.py`)
- No API exists to list, view, or edit templates — changes require a code push

**Backend:**

**New model — `email_templates` table:**
- `id` (PK), `template_name` (String, unique — matches filename, e.g. `welcome.html`)
- `html_content` (Text — the full HTML)
- `updated_by_user_id` (FK → users.id, nullable)
- `updated_at` (DateTime)
- Only templates that have been admin-edited appear in this table; unedited templates use the filesystem default

**Template registry** (code-defined, not DB):
- Dict mapping template name → `{ display_name, description, variables: ["user_name", "app_url", ...] }`
- e.g. `"welcome.html": { display_name: "Welcome Email", description: "Sent after registration", variables: ["user_name", "app_url"] }`

**Template loading priority:** DB override → filesystem fallback. Modify `_load_template()` to check `email_templates` table first.

**New endpoints (admin-only):**
- `GET /api/admin/email-templates` — List all templates (name, display name, description, last modified, has DB override)
- `GET /api/admin/email-templates/{name}` — Get full HTML content + metadata (available variables, description)
- `PUT /api/admin/email-templates/{name}` — Update template HTML content; validate required `{{variables}}` are present; store in DB
- `POST /api/admin/email-templates/{name}/preview` — Render template with sample data and return HTML preview
- `POST /api/admin/email-templates/{name}/reset` — Delete DB override, revert to filesystem default

**Audit:** Log every template edit with action `email_template_update`.

**Frontend:**

- New "Email Templates" page accessible from Admin Dashboard (link in admin nav or section)
- Template list: cards/rows with name, description, last modified, "Edited" badge if DB override exists
- Template editor view:
  - HTML textarea (syntax-highlighted if possible, or plain textarea)
  - Live preview panel (rendered with sample data via `/preview` endpoint)
  - Available variables reference sidebar
  - Save / Reset to Default buttons with confirmation modals

**Sub-tasks:**
- [ ] Backend: `email_templates` table + model (#513)
- [ ] Backend: Template registry with metadata (#513)
- [ ] Backend: Modify `_load_template()` to check DB first (#513)
- [ ] Backend: CRUD + preview + reset endpoints (#513)
- [ ] Frontend: Email Templates list page (#513)
- [ ] Frontend: Template editor with preview (#513)
- [ ] Tests: Template CRUD, preview, reset, RBAC (#513)

### 6.50 Broadcast History: View Details, Reuse & Resend (Phase 2)

Enhance the existing broadcast history so admins can view full broadcast details, reuse a past broadcast as a template for a new one, and resend a previous broadcast.

**GitHub Issue:** #514

**Current State:**
- Broadcasts persisted in `broadcasts` table (subject, body, recipient_count, email_count, sender_id, created_at)
- `GET /api/admin/broadcasts` lists past broadcasts (subject, date, counts)
- `POST /api/admin/broadcast` sends a new broadcast
- Admin Dashboard shows a collapsible broadcast history table with subject, date, and counts
- **Missing:** No way to view full body, reuse, or resend a past broadcast

**Backend:**

**Model changes to `broadcasts` table:**
- Add `parent_broadcast_id` (FK → broadcasts.id, nullable) — links resent broadcasts to the original

**New/enhanced endpoints (admin-only):**
- `GET /api/admin/broadcasts/{id}` — Full broadcast detail (subject, body, sender name, recipient_count, email_count, created_at, parent_broadcast_id)
- `POST /api/admin/broadcasts/{id}/reuse` — Returns the broadcast's subject + body as JSON for pre-filling the broadcast modal (no side effects)
- `POST /api/admin/broadcasts/{id}/resend` — Resend the exact same broadcast to all active users; creates a new `Broadcast` record with `parent_broadcast_id` set to the original

**Migration:** `ALTER TABLE broadcasts ADD COLUMN parent_broadcast_id INTEGER REFERENCES broadcasts(id)` (top-level, independent, with try/except as per project convention).

**Frontend:**

- Broadcast history table: add "View" and "Reuse" action buttons per row
- **View modal:** Shows full broadcast body (rendered HTML), delivery stats, sender, date
- **Reuse flow:** Click "Reuse" → opens broadcast modal pre-filled with subject + body → admin edits → sends as new broadcast
- **Resend:** Optional "Resend" button in view modal with confirmation dialog

**Sub-tasks:**
- [ ] Backend: Add `parent_broadcast_id` column + migration (#514)
- [ ] Backend: `GET /api/admin/broadcasts/{id}` detail endpoint (#514)
- [ ] Backend: `POST /api/admin/broadcasts/{id}/reuse` endpoint (#514)
- [ ] Backend: `POST /api/admin/broadcasts/{id}/resend` endpoint (#514)
- [ ] Frontend: View broadcast detail modal (#514)
- [ ] Frontend: Reuse pre-fill in broadcast modal (#514)
- [ ] Tests: Detail, reuse, resend endpoints + RBAC (#514)

---

### 6.51 Phase 1 New Workflow — Student-First Registration, Approval Linking & Multi-Channel Notifications

**Added:** 2026-02-18 | **Issues:** #546-#552 | **Branch:** `feature/phase1-foundation` + 3 parallel streams

This section defines the expanded Phase 1 workflow that enables student-initiated registration, bidirectional parent-student approval linking, multi-channel notifications with persistent ACK reminders, Google Classroom type differentiation, and teacher/student invites.

#### 6.51.1 Student Registration (Reqs 1-3) — #546

- Student can register with **either personal email OR username + parent email**
- Username login: alphanumeric + underscores, 3-30 chars
- If parent email specified and parent exists → system creates a **LinkRequest** for parent to approve
- If parent not in ClassBridge → system sends an **Invite email** for parent to register; auto-links on accept
- Parent email stored on `students.parent_email` column

**Models:** `users.username` (new column), `students.parent_email` (new column)

#### 6.51.2 Parent-Student LinkRequest Approval (Reqs 10-14) — #547

- New `link_requests` table: request_type, status (pending/approved/rejected/expired), requester, target, token
- Parent tries to add **existing active student** → LinkRequest created, student must approve
- Parent adds **placeholder student** (UNUSABLE_PASSWORD_HASH) → auto-links immediately (no approval)
- Approval inserts into `parent_students` join table
- Notifications sent via all channels on request + response

**Endpoints:** `GET /api/link-requests`, `GET /api/link-requests/sent`, `POST /api/link-requests/{id}/respond`

#### 6.51.3 Multi-Channel Notifications + ACK System (Reqs 9, 15, 24) — #548

- Centralized `notification_service.py` sends via 3 channels:
  1. **In-app notification bell** (Notification table)
  2. **Email** (SendGrid/SMTP)
  3. **ClassBridge message** (Conversation + Message)
- **ACK system:** Notifications can require acknowledgment (`requires_ack=True`)
  - Persistent reminders re-sent every 24h until ACKed or due date passes
  - Background job runs every 6 hours (`notification_reminders.py`)
- **Suppression:** Parents can permanently silence notifications for a specific source (assignment/task)
  - `notification_suppressions` table tracks per-user suppressed items
- Parent receives notifications for **all student actions**: material upload, task create, study guide generated, upcoming dues (3-day advance)

**Models:** Notification ACK columns (`requires_ack`, `acked_at`, `source_type`, `source_id`, `next_reminder_at`, `reminder_count`), `notification_suppressions` table
**Endpoints:** `PUT /api/notifications/{id}/ack`, `PUT /api/notifications/{id}/suppress`

#### 6.51.4 Parent Request Assignment Completion (Req 16) — #549

- Parent can request a student to complete a specific assignment or task
- Multi-channel notification sent to student
- **Endpoint:** `POST /api/parent/children/{student_id}/request-completion`

#### 6.51.5 Google Classroom School vs Private (Reqs 4-5, 18) — #550

- `courses.classroom_type` column: "school" or "private"
- School classroom: student can see assignments/dues but **cannot download documents** (reference_url stripped)
- Private classroom: full access to all content
- DTAP approval required for school board connections (external process, UI disclaimer only)

#### 6.51.6 Student/Teacher Invites + Course Enrollment (Reqs 6, 22-23) — #551

- Students can invite **private teachers** to join ClassBridge
- Teachers can invite **students to enroll** in a course → `POST /api/courses/{id}/invite-student`
- Teachers can invite **parents to link** to a student (with student_id context)
- All invites trigger multi-channel notifications

#### 6.51.7 Course Material Upload with AI Tool Selection (Reqs 7-8) — #552

- During upload, student selects AI help type: Study Guide, Quiz, Flash Card, Other (custom prompt)
- "Other" sends user's custom text as a prompt to AI
- Manual download from school Google Classroom → upload to ClassBridge (UI guidance, no download API)
- Parent notified when material is uploaded

**Implementation Notes:**
- **Parallel development:** Foundation (Phase 0) creates all models/migrations/services. Then 3 streams run in parallel:
  - Stream A (`feature/registration-linking`): Registration, login, LinkRequest, parent approval
  - Stream B (`feature/notifications-ack`): ACK/suppress, parent notification hooks, reminder job
  - Stream C (`feature/gc-teacher-features`): Google Classroom types, invites, upload UI
- **New notification types:** LINK_REQUEST, MATERIAL_UPLOADED, STUDY_GUIDE_CREATED, PARENT_REQUEST, ASSESSMENT_UPCOMING, PROJECT_DUE

---

### 6.52 Course Material Detail Page -- Refactor and Polish (Phase 1) - IMPLEMENTED

The Course Material Detail page is the most-used page for parents and students studying. This refactor improves code maintainability, fixes bugs, and polishes the UI.

#### Issues Addressed
- #732: Flashcard keyboard navigation not implemented
- #733: Shuffle button resets instead of shuffling
- #734: UI redesign and visual polish
- #735: Extract CourseMaterialDetailPage into sub-components
- #736: Improve focus prompt UX

#### Architecture
- Orchestrator (CourseMaterialDetailPage.tsx, ~330 lines): Data fetching, shared state, tab switching
- Sub-components in frontend/src/pages/course-material/:
  - DocumentTab.tsx: Document viewing, inline editing, formatted JSON detection
  - StudyGuideTab.tsx: Study guide display with print/regenerate/delete
  - QuizTab.tsx: Quiz flow with result saving and parent student banner
  - FlashcardsTab.tsx: Flashcard viewer with shuffle, keyboard nav, a11y
  - ReplaceDocumentModal.tsx: Drag-and-drop file upload with background upload

#### Verification
- TypeScript compiles cleanly, all 333 frontend tests pass, no regressions

---

### 6.53 Waitlist System — Pre-Launch Gated Access (Phase 1) — IMPLEMENTED

**Issues:** #1106-#1115, #1124 (all closed)
**PRs:** #1127 (main implementation), #1128, #1129, #1130 (test fixes)

**Sub-tasks:**
- [x] Data model + migrations (#1107)
- [x] Public API endpoints — join waitlist + token verify (#1108)
- [x] Admin API endpoints — list, approve, decline, remind, notes, delete (#1109)
- [x] Email templates — confirmation, admin notify, approval, decline, reminder (#1110)
- [x] Launch Landing Page — `/` route (#1111)
- [x] Join Waitlist form page — `/waitlist` (#1112)
- [x] Login page — replace "Sign Up" with "Join Waitlist" CTA (#1113)
- [x] Token-gated registration — `/register?token=` (#1114)
- [x] Admin Waitlist Management Panel — `/admin/waitlist` (#1115)
- [x] Feature flag `WAITLIST_ENABLED` + routing changes (#1124)
- [x] Duplicate email check on join (#1129)
- [x] Frontend + backend tests (#1122, #1123, #1130)

ClassBridge launches with a waitlist-gated flow. The current open registration is replaced with a waitlist landing page. Admin manually approves users before they can register. This controls incoming traffic and enables gradual onboarding. Will be reverted to current open-registration flow on Phase 2 launch.

#### Data Model

**`waitlist` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| name | VARCHAR(255) | Required |
| email | VARCHAR(255) | Required, unique, case-insensitive |
| roles | JSON | Array of selected roles (e.g., `["parent", "student"]`) |
| status | VARCHAR(20) | `pending` / `approved` / `declined` / `registered` |
| admin_notes | TEXT | Optional admin notes |
| invite_token | VARCHAR(255) | Unique token for registration link (generated on approval) |
| invite_token_expires_at | DATETIME | Token expiry (14 days from approval) |
| invite_link_clicked | BOOLEAN | Set to TRUE when user clicks invite link |
| approved_by_user_id | INTEGER FK | Admin who approved |
| approved_at | DATETIME | Timestamp of approval |
| registered_user_id | INTEGER FK | Links to `users.id` after registration completes |
| reminder_sent_at | DATETIME | Last reminder email timestamp |
| created_at | DATETIME | Join request timestamp |
| updated_at | DATETIME | Last status change |

#### User-Facing Flow

1. **Landing Page** (`/`) — New launch landing page with two CTAs:
   - "Join the Waitlist" — navigates to `/waitlist`
   - "Login" — navigates to `/login`
   - Hero section with ClassBridge branding, value proposition, feature highlights
   - Clean, modern design matching ClassBridge design system

2. **Waitlist Form** (`/waitlist`) — Simple form:
   - Full Name (required)
   - Email (required, validated format)
   - Role checkboxes: Parent, Student, Teacher (at least one required)
   - Submit button
   - On success: confirmation screen ("Thank you for joining the waitlist!")

3. **Login Page** (`/login`) — Updated login page:
   - Existing email/password login form
   - Replace "Sign Up" / "Create Account" CTA with "Join the Waitlist" link → `/waitlist`
   - Remove any direct link to `/register`

4. **Registration via Invite Link** (`/register?token=<invite_token>`) — When user clicks invite link from approval email:
   - System validates token (exists, not expired, not already used)
   - System marks `invite_link_clicked = TRUE` on the waitlist record
   - Pre-populates name and email from waitlist record (email read-only)
   - User completes the existing progressive registration form (password, role confirmation)
   - On registration complete:
     - Waitlist record status updated to `registered`
     - `registered_user_id` set to new user ID
     - Existing welcome email sent (BAU)

#### Email Templates

1. **Waitlist Confirmation Email** (`waitlist_confirmation.html`)
   - Sent to: User, immediately after joining waitlist
   - Subject: "Welcome to ClassBridge's Waitlist!"
   - Content: Thank you message, what to expect next, ClassBridge branding
   - Includes inspirational message (reuse existing pattern)

2. **Admin Notification Email** (`waitlist_admin_notification.html`)
   - Sent to: All admin users, immediately after new waitlist signup
   - Subject: "New Waitlist Signup: {name}"
   - Content: User name, email, selected roles, link to admin waitlist panel

3. **Approval / Invitation Email** (`waitlist_approved.html`)
   - Sent to: User, when admin approves
   - Subject: "You're Invited to Join ClassBridge!"
   - Content: Welcome message, registration link with invite token (`/register?token=<token>`), token valid for 14 days
   - The link serves dual purpose: validates email + starts registration

4. **Decline Email** (`waitlist_declined.html`)
   - Sent to: User, when admin declines
   - Subject: "ClassBridge Waitlist Update"
   - Content: Polite message that we can't onboard at this time, will keep them informed

5. **Registration Reminder Email** (`waitlist_reminder.html`)
   - Sent to: User (approved but not yet registered), triggered manually by admin
   - Subject: "Reminder: Complete Your ClassBridge Registration"
   - Content: Reminder to register, registration link (refreshed token if expired)

#### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/waitlist` | Public | Join waitlist (name, email, roles) |
| GET | `/api/waitlist/verify/{token}` | Public | Validate invite token, return waitlist record |
| GET | `/api/admin/waitlist` | Admin | List all waitlist entries with filters (status, date range, search) |
| GET | `/api/admin/waitlist/stats` | Admin | Waitlist stats (count by status) |
| PATCH | `/api/admin/waitlist/{id}/approve` | Admin | Approve user, generate invite token, send approval email |
| PATCH | `/api/admin/waitlist/{id}/decline` | Admin | Decline user, send decline email |
| POST | `/api/admin/waitlist/{id}/remind` | Admin | Resend registration reminder to approved user |
| PATCH | `/api/admin/waitlist/{id}/notes` | Admin | Update admin notes |
| DELETE | `/api/admin/waitlist/{id}` | Admin | Delete waitlist entry |

#### Admin Panel

**Waitlist Management Page** (`/admin/waitlist`):
- Summary stats bar: Total | Pending | Approved | Registered | Declined
- Filterable/searchable table with columns: Name, Email, Roles, Status, Date Joined, Date Approved, Actions
- Status badge colors: Pending (yellow), Approved (blue), Registered (green), Declined (red)
- Actions per row:
  - Pending: Approve | Decline buttons
  - Approved: Send Reminder | View buttons
  - Registered: View user profile link
  - Declined: Re-approve button
- Bulk approve (select multiple pending → approve all)
- Admin notes field (inline edit)

#### Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| LaunchLandingPage | `/` | Hero + "Join Waitlist" + "Login" CTAs |
| WaitlistPage | `/waitlist` | Join form + success confirmation |
| LoginPage | `/login` | Updated with "Join Waitlist" CTA |
| RegisterPage | `/register?token=` | Token-gated registration |
| AdminWaitlistPage | `/admin/waitlist` | Waitlist management table |

#### Routing Changes
- `/` → LaunchLandingPage (replaces current redirect-to-login)
- `/register` → requires valid `?token=` param (no direct access without token)
- `/login` → updated CTAs
- Current open `/register` route disabled (returns redirect to `/waitlist`)

#### Revert Plan (Phase 2 Launch)
- Restore `/` → redirect to dashboard or current landing
- Restore `/register` → open registration
- Restore `/login` → "Sign Up" CTA
- Keep waitlist data for historical records
- Feature flag: `WAITLIST_ENABLED` env var (default: `true` for Phase 1 launch, `false` for Phase 2)

---

### 6.54 AI Usage Limits — Configurable Per-User AI Interaction Quota (Phase 1) — IMPLEMENTED

**Issues:** #1116-#1121 (closed), #1125 (audit log — open, future)
**PRs:** #1127 (main implementation), #1130 (test fixes)

**Sub-tasks:**
- [x] Data model + migrations — `ai_usage_count`, `ai_usage_limit` on users, `ai_limit_requests` table (#1117)
- [x] Enforce usage counting in AI generation service (#1118)
- [x] API endpoints — user + admin (#1119)
- [x] Frontend UI — credits display, limit modal, request form (#1120)
- [x] Admin AI Usage Management Panel (#1121)
- [x] Backend + frontend tests (#1122, #1123, #1130)
- [ ] Usage history audit log — `ai_usage_history` table + admin views (#1125)

Control AI API costs by limiting the number of AI interactions per user. Default quota is 10 AI generations. Users can request more; admin approves via admin panel.

#### Data Model

**New columns on `users` table:**
| Column | Type | Default | Notes |
|--------|------|---------|-------|
| ai_usage_limit | INTEGER | 10 | Max AI generations allowed |
| ai_usage_count | INTEGER | 0 | Current count of AI generations used |
| ai_usage_reset_at | DATETIME | NULL | Optional: when to auto-reset count (future use) |

**`ai_limit_requests` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | Requesting user |
| requested_amount | INTEGER | How many additional interactions requested |
| reason | TEXT | User's justification |
| status | VARCHAR(20) | `pending` / `approved` / `declined` |
| approved_amount | INTEGER | Amount actually granted (may differ from requested) |
| admin_user_id | INTEGER FK | Admin who handled request |
| created_at | DATETIME | Request timestamp |
| resolved_at | DATETIME | Approval/decline timestamp |

**`ai_usage_history` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | User who generated |
| generation_type | VARCHAR(20) | `study_guide` / `quiz` / `flashcard` |
| course_material_id | INTEGER FK | Related course material (nullable) |
| credits_used | INTEGER | Always 1 for now (future: variable cost) |
| created_at | DATETIME | Timestamp of generation |

This table provides a complete audit trail of every AI credit consumed, enabling admin to view per-user generation history, filter by type, and see usage patterns over time.

#### Counting Logic

An "AI interaction" counts as one unit for each:
- Study guide generation
- Quiz generation
- Flashcard generation
- Any AI generation triggered via upload with AI tool selection

Counting happens in the AI generation service layer (single point of enforcement). Each successful generation increments `ai_usage_count` by 1.

#### User-Facing Behavior

1. **Usage indicator** — Show remaining AI interactions in the UI:
   - Dashboard: "AI Credits: 7/10 remaining" badge/counter
   - Before any AI generation: show remaining count in confirmation dialog
   - At 80% usage (2 remaining): warning banner "You have 2 AI credits remaining"

2. **Limit reached** — When `ai_usage_count >= ai_usage_limit`:
   - AI generation buttons show "Limit Reached" state (disabled)
   - Modal explaining limit with "Request More" button
   - Request form: desired amount + brief reason

3. **Request more flow:**
   - User fills request form → creates `ai_limit_requests` record (status: pending)
   - Admin gets in-app notification
   - Admin reviews in admin panel → approve (set amount) or decline
   - User gets in-app notification of outcome
   - On approval: `ai_usage_limit` increased by `approved_amount`

#### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/ai-usage` | Authenticated | Get current usage (count, limit, remaining) |
| GET | `/api/ai-usage/history` | Authenticated | Get own AI usage history (paginated) |
| POST | `/api/ai-usage/request` | Authenticated | Request additional AI credits |
| GET | `/api/admin/ai-usage` | Admin | List all users with usage stats |
| GET | `/api/admin/ai-usage/history` | Admin | Full AI usage history across all users (filterable by user, type, date range) |
| GET | `/api/admin/ai-usage/requests` | Admin | List all limit increase requests (filterable by status: pending/approved/declined/all) |
| PATCH | `/api/admin/ai-usage/requests/{id}/approve` | Admin | Approve with amount |
| PATCH | `/api/admin/ai-usage/requests/{id}/decline` | Admin | Decline request |
| PATCH | `/api/admin/ai-usage/users/{id}/limit` | Admin | Manually set user's limit |
| POST | `/api/admin/ai-usage/users/{id}/reset` | Admin | Reset user's usage count to 0 |

#### Admin Panel

**AI Usage Management** (dedicated `/admin/ai-usage` page with tabbed sections):

**Tab 1: Overview**
- Summary cards: Total AI calls today / this week / this month / all time
- Top 10 users by usage (bar chart or ranked list)
- User table: Name, Email, Role, Usage (count/limit as progress bar), Last Used, Actions
- Actions per user: Adjust Limit | Reset Count | View History
- Search/filter by name, email, role

**Tab 2: Usage History**
- Full audit log of every AI credit consumed across all users
- Columns: User, Generation Type (study guide/quiz/flashcard), Course Material, Date/Time
- Filters: User (search), Generation Type (dropdown), Date Range (from/to)
- Export to CSV (future)
- Click user name → filters to that user's history

**Tab 3: Credit Requests**
- All limit increase requests (not just pending — full history)
- Columns: User, Requested Amount, Reason, Status (badge), Approved Amount, Admin, Date Requested, Date Resolved
- Filter by status: All / Pending / Approved / Declined
- Pending requests appear at top with Approve (amount input) / Decline action buttons
- Resolved requests show outcome details (who approved, how much granted)

#### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `AI_DEFAULT_USAGE_LIMIT` | 10 | Default limit for new users |
| `AI_USAGE_WARNING_THRESHOLD` | 0.8 | Show warning at this % of limit |

---

### 6.55 Contextual Notes System `IMPLEMENTED`

**Purpose:** Allow students to take per-material notes directly within the app, with auto-save, task creation, and a floating draggable panel UX.

**GitHub Issues:** #1084-#1090, #1179

#### Data Model

**`notes` table:**
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| user_id | INTEGER FK | Note owner |
| course_content_id | INTEGER FK | Linked material |
| content | TEXT | HTML content |
| plain_text | TEXT | Stripped plain text (for search/preview) |
| has_images | BOOLEAN | Whether content contains images |
| created_at | DATETIME | Auto-set |
| updated_at | DATETIME | Auto-updated on save |

**`tasks` table extension:**
| Column | Type | Notes |
|--------|------|-------|
| note_id | INTEGER FK (nullable) | Links task to originating note |

#### API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/notes/` | Authenticated | List notes (optional `course_content_id` filter) |
| GET | `/api/notes/{id}` | Authenticated | Get single note with full content |
| PUT | `/api/notes/` | Authenticated | Upsert note (create or update by course_content_id) |
| DELETE | `/api/notes/{id}` | Authenticated | Delete note (owner only) |
| GET | `/api/notes/children/{student_id}` | Parent | List child's notes (read-only) |

#### Frontend Components

- **`NotesPanel`** — Floating, draggable, closable panel with:
  - [x] Rich text area with auto-save (1s debounce)
  - [x] Save status indicator (Saving.../Saved)
  - [x] Task creation from notes (quick task or linked task)
  - [x] Floating overlay positioning with drag-to-reposition
  - [x] Close button (X) to dismiss panel
  - [x] `isOpen`/`onClose` props for toggle control

- **`NotesPanelToggle`** — Button that opens/closes the floating NotesPanel:
  - [x] Used on FlashcardsPage, QuizPage, StudyGuidePage
  - [x] Badge indicator when note exists for current material

- **CourseMaterialDetailPage** — Notes toolbar button toggles the floating panel:
  - [x] Notes button in header toolbar
  - [x] URL param `?notes=open` auto-opens panel

#### Behavior

- One note per user per course material (upsert semantics)
- Empty content auto-deletes the note
- Parent can view child's notes (read-only) via `/children/{student_id}` endpoint
- Admin can view any note
- Panel remembers position during session (resets on page navigation)

---
