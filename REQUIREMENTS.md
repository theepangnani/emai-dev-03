# ClassBridge (EMAI) - Product Requirements

**Product Name:** ClassBridge
**Author:** Theepan Gnanasabapathy
**Version:** 1.0 (Based on PRD v4)
**Last Updated:** 2026-02-09

---

## 1. Executive Summary

ClassBridge is a unified, AI-powered education platform that connects parents, students, teachers, administrators, and (in later phases) tutors in one role-based application. It integrates with school systems, provides AI-driven study tools, simplifies communication, and enables parents to actively support their children's education while ensuring access to affordable tutoring and intelligent assistance.

---

## 2. Vision & Mission

### Vision
To become the trusted digital bridge between families and schools, empowering every student to succeed with the right support at the right time.

### Mission
ClassBridge empowers parents to actively participate in their children's education by providing intelligent tools, clear insights, and affordable access to trusted educators - all in one connected platform.

---

## 3. Problem Statement

Education ecosystems are fragmented:
- Parents struggle to track academic progress across multiple systems (Google Classroom, TeachAssist, etc.)
- Students lack structured organization and effective study tools
- Teachers rely on disconnected communication channels
- Affordable tutoring is difficult to discover and manage

---

## 4. Goals & Objectives

### Product Goals
- Provide a single role-based application for parents, students, teachers, and administrators
- Enable parents to support learning at home
- Improve student academic outcomes through AI insights
- Simplify teacher-parent communication

### Business Goals
- Build a scalable SaaS platform
- Partner with school boards
- Establish recurring revenue through subscriptions and future marketplace services

---

## 5. User Roles & Personas

| Role | Description |
|------|-------------|
| **Parent** | Visibility into progress, tools to help children study, access to tutoring (Phase 4) |
| **Student** | Organization, personalized study support, motivation |
| **Teacher (School)** | School teacher — may be on EMAI (platform teacher) or only referenced via Google Classroom sync (shadow record) |
| **Teacher (Private Tutor)** | Independent educator on EMAI — creates own courses, connects own Google Classroom, manages students directly. Phase 4 adds marketplace features (availability, profiles, booking) for teachers with `teacher_type=private_tutor` |
| **Administrator** | User management, analytics, compliance |

---

## 6. Core Features

### 6.1 Integrations
- **Google Classroom** (Phase 1) - IMPLEMENTED
- **TeachAssist** (Phase 2)

### 6.2 AI Study Assistant (Phase 1) - IMPLEMENTED
- Generate study guides from assignment content
- Generate practice quizzes
- Generate flashcards
- Summarize teacher handouts
- Identify strengths and weaknesses
- **Confirmation dialogs**: All AI generation and destructive actions use custom styled confirmation modals (ConfirmModal component with useConfirm hook) instead of native browser dialogs, with danger variant for destructive operations like permanent delete
- **Robust JSON parsing**: AI responses wrapped in markdown code fences (` ```json ... ``` `) are automatically stripped before parsing, preventing "Failed to parse" errors
- **Non-blocking generation**: AI study material generation is fully non-blocking. Modal closes immediately after submission, a pulsing "Generating..." placeholder row appears in the study materials list, and the user can continue working. On success the placeholder is replaced with the real guide; on failure it shows an error with a dismiss button. Works from both Study Guides page and Parent Dashboard (queues generation and navigates to Study Guides page)

#### 6.2.1 Study Guide Storage & Management (Phase 1) - IMPLEMENTED

Persistent storage, organization, and lifecycle management for AI-generated study guides.

- **List & Browse**: Parents and students can view a full list of all their generated study guides, quizzes, and flashcards directly from their dashboards. Clicking any item opens the full study material for review. Students see their materials in the "Your Study Materials" section; parents see both "My Study Materials" and each linked child's study materials
- **Course Categorization**: Study guides are labeled under existing courses for organized browsing; students can filter guides by course using a dropdown filter
- **Configurable Storage Limits**: Maximum 100 study guides per student, 200 per parent. Limits are configurable via application settings (`STUDY_GUIDE_LIMIT_STUDENT`, `STUDY_GUIDE_LIMIT_PARENT`)
- **Version Control**: Regenerating a study guide for the same topic/assignment creates a new version linked to the original via `parent_guide_id`, preserving full history. Users can browse all versions of a guide
- **Duplicate Detection**: Before AI generation, the system checks for existing guides with matching content hash to avoid redundant API calls and save costs. Endpoint: `POST /api/study/check-duplicate`
- **Role-Based Visibility**:
  - **Students** see their own study guides plus any course-labeled guides shared within their enrolled courses
  - **Parents** see their own study guides plus all study guides belonging to their linked children
- **Deletion**: Users can delete their own study guides. Deleting a parent guide does not cascade to child versions
- **Course Assignment**: Any user can assign/reassign their study guides to a course via `PATCH /api/study/guides/{guide_id}`. A reusable `CourseAssignSelect` dropdown component is available on study guide view pages (StudyGuidePage, QuizPage, FlashcardsPage) and inline in dashboard study material lists
- **Ungrouped Guide Categorization**: Study guides without a `course_content_id` appear under "Ungrouped Study Guides" on the Study Guides page. Each ungrouped guide has a folder icon button ("Move to course") that opens a modal with a searchable course list. Users can type to filter courses or create a new course inline ("+Create" option appears when search text doesn't match any existing course). On move, the backend auto-creates a `CourseContent` entry via `ensure_course_and_content()` and assigns the guide, moving it into the grouped section

#### 6.2.2 Course Materials Restructure (Phase 1) - IMPLEMENTED

Restructure the Study Guides page to centre on **course materials** (course content items) rather than listing study guides directly. Each course material is the source document from which AI study tools (study guide, quiz, flashcards) are generated.

**Concept**: Study guides, quizzes, and flashcards are outputs *of* a course material, not standalone entities. The Study Guides page (`/study-guides`) becomes a **course materials listing** where each row represents a course content item, and clicking it opens a tabbed detail view showing the original document and any generated study tools.

**Navigation Flows:**

1. **Courses → Course → Course Materials** (existing, no change)
   - `/courses` — list all courses
   - `/courses/:id` — show course detail with its content items

2. **Study Guides (nav) → Course Materials List → Tabbed Detail**
   - `/study-guides` — lists all course materials across all courses, with filters
   - `/study-guides/:contentId` — tabbed detail view for a single course material

**Tabbed Detail View** (`/study-guides/:contentId`):
- **Tab 1: Original Document** — shows the source text/description of the course content item
- **Tab 2: Study Guide** — shows the generated study guide, or a "Generate Study Guide" button if none exists
- **Tab 3: Quiz** — shows the generated quiz, or a "Generate Quiz" button if none exists
- **Tab 4: Flashcards** — shows the generated flashcards, or a "Generate Flashcards" button if none exists

**Filtering:**
- Parents can filter by **child** (shows materials from that child's courses)
- All roles can filter by **course**

**Default Course ("My Materials"):**
- When a user creates study material (paste text or upload file) without selecting a course, the system auto-creates a personal default course named "My Materials" for that user (if it doesn't already exist)
- The uploaded/pasted content becomes a `CourseContent` item under the default course
- The generated study guide/quiz/flashcards are linked to that `CourseContent` via `course_content_id`
- Default course has `is_default = TRUE` on the Course model; one per user

**Data Model Changes:**
- `study_guides.course_content_id` — new nullable FK to `course_contents.id`, linking each study guide to its source material
- `courses.is_default` — new BOOLEAN column (default FALSE) to identify per-user default courses
- Backend helper: `get_or_create_default_course(user_id, db)` — returns the user's "My Materials" course, creating it if needed

**API Changes:**
- `GET /api/course-contents/` — new list endpoint across all courses (with optional `course_id` and `user_id` filters)
- `GET /api/study/guides?course_content_id=X` — filter study guides by course content
- `POST /api/study/generate` — accepts optional `course_content_id`; when no course selected, auto-creates default course + CourseContent
- `GET /api/courses/default` — get or create the user's default course

### 6.3 Parent-Student Registration & Linking (Phase 1)

ClassBridge is designed as a **parent-first platform**. Parents can manage their children's education without requiring school board integration or Google Classroom access. Student email is **optional** — parents can create students with just a name.

#### Design Principles
- ClassBridge works **independently of school systems** — Google Classroom is an optional import source, not a requirement
- Students don't need to be attached to a teacher — parent-created courses have no teacher
- Student email is optional — students without email are fully managed by their parent
- No data is synced from Google Classroom by default — all syncs are manual and on-demand
- Parent-created courses are **private** to the parent's children only

#### Path 1: Parent-Created Student (Name Only, No Email Required)
- Parent creates a child from the Parent Dashboard with just a **full name**
- Email is optional — if no email, the student cannot log in independently (parent manages their account)
- If email is provided: system auto-creates an invite so the child can set their password and log in later
- Creates User (role=student, email=nullable) + Student record + `parent_students` join entry
- Endpoint: `POST /api/parent/children/create`

#### Path 2: Parent Links Existing Student by Email (with Auto-Create) - IMPLEMENTED
- A parent links to a student by email from the Parent Dashboard via `POST /api/parent/children/link`
- **If the student account exists:** Links immediately — creates entry in `parent_students` join table
- **If no account exists for that email:** System auto-creates a User (role=student) + Student record, generates an invite via the Unified Invite System (30-day expiry), and returns the invite link to the parent
- **If the email belongs to a non-student account:** Returns an error (cannot link to parent/teacher/admin accounts)
- Parent can optionally provide the child's full name; if omitted, the email prefix is used
- Multiple parents can link to the same student (e.g., mother, father, guardian)

#### Path 3: Self-Registered Student
- Student creates their own account at `/auth/register` with role=student
- No parent required — the platform works fully for independent students
- Student can optionally be linked to parent(s) later

#### Path 4: Google Classroom Discovery (On-Demand Import)
- Parent connects Google account and manually triggers "Search Google Classroom"
- System discovers students from the parent's Google Classroom courses
- Students not yet in ClassBridge are auto-created with their Google profile name
- Parent selects which students to link — nothing is automatic
- **Note:** This only works if the parent's Google account has Google Classroom courses (e.g., parent is also a teacher)

#### Student Email Policy
| Scenario | Email Required? | Student Can Log In? | Managed By |
|----------|----------------|---------------------|------------|
| Parent creates child with name only | No | No — parent manages | Parent |
| Parent creates child with email | Yes | Yes — via invite link | Parent + Student |
| Student self-registers | Yes | Yes — has password | Student |
| Google Classroom discovery | Yes (from Google) | Yes — via invite link | Parent + Student |

#### Email Identity Merging (MVP 1.5)
- Students may have both a **personal email** (used in MVP-1) and a **school email** (available when school board approves ClassBridge)
- When school board access becomes available, students can add their school email as a secondary identity
- Both emails resolve to the same student account
- Data model: `student_emails` table (student_id, email, email_type: personal/school, is_primary, verified_at)

#### Data Model
- **Many-to-many**: `parent_students` join table (parent_id, student_id, relationship_type, created_at)
- A student can have zero, one, or many parents
- A parent can have zero, one, or many students
- `relationship_type`: "mother", "father", "guardian", "other"
- `User.email` — **nullable for students only** (other roles still require email for login)

### Unified Invite System
Both student invites (from parent registration) and teacher invites (from shadow discovery) use a single `invites` table and endpoint:
- `invites` table: id, email, invite_type (student, teacher), token, expires_at, invited_by_user_id, metadata (JSON), accepted_at, created_at
- Single endpoint: `POST /api/auth/accept-invite` — resolves invite_type to create the appropriate User + role records
- Invite tokens expire after 7 days (students) or 30 days (teachers)

### 6.3.1 Course Management (Phase 1)

Courses in ClassBridge can be created by **parents, students, or teachers**. Courses do not require a teacher — parent-created courses exist for home learning. Google Classroom courses are imported on-demand only.

#### Who Can Create Courses
| Role | Can Create? | Visibility | teacher_id |
|------|------------|------------|------------|
| **Parent** | Yes | Private to parent's linked children only | NULL |
| **Student** | Yes | Visible to the student only | NULL |
| **Teacher** | Yes | Visible to enrolled students | Set to teacher's ID |

#### Course Assignment
- Parents can **assign courses to their linked children** via `POST /api/parent/children/{student_id}/courses`
- Students can **self-enroll** in courses via `POST /api/courses/{id}/enroll`
- Teachers can add students to their courses

#### Google Classroom Integration (On-Demand Only)
- **No data is synced from Google Classroom by default**
- Users must manually click "Import from Google Classroom" to pull courses
- Users select which courses to import — system does not auto-import all
- Synced courses are tagged with `google_classroom_id` for deduplication
- Background sync jobs are **disabled by default** — sync is portal-only
- Any data synced from Google Classroom or Gmail must be **manually selected and/or requested**

#### Course Data Model Changes
- `Course.teacher_id` — already nullable (no change needed)
- `Course.created_by_user_id` — **new field**: tracks who created the course (parent, student, or teacher)
- `Course.is_private` — **new field**: if true, only visible to creator's linked children (for parent-created courses)

### 6.3.2 Student-Teacher Linking (Phase 1) - IMPLEMENTED

Students link to teachers through **course enrollment**. This creates the relationship needed for parent-teacher messaging. Students don't need to be attached to a teacher — many courses have no teacher.

#### Relationship Model:
```
Parent ←→ Student (via parent_students join table)
Student ←→ Course (via student_courses join table)
Course ←→ Teacher (via course.teacher_id, OPTIONAL)
Parent ←→ Teacher (inferred: parent's child enrolled in teacher's course)
```

#### Manual Flow (No Google OAuth):
1. Parent registers and creates children (by name or email)
2. Parent creates courses and assigns them to children
3. Optionally: Teacher registers, creates course, student enrolls
4. Parent can message the teacher (if child is in a teacher's course)

### 6.4 Manual Course Content Upload (Phase 1) - PARTIALLY IMPLEMENTED
- Upload or enter course content manually - IMPLEMENTED
- Supported inputs: PDF, Word, PPTX, text notes - IMPLEMENTED (images/OCR pending)
- Tag content to specific class or subject - IMPLEMENTED
- AI generates study materials from user-provided content - IMPLEMENTED
- Content privacy controls - pending
- Version history - pending
- GCS file storage - pending (#114)

### 6.4.1 Course Content Types with Reference Links (Phase 1) - IMPLEMENTED
- Structured content items attached to courses (notes, syllabus, labs, assignments, readings, resources, other)
- Each item has title, description, content type, reference URL, and optional Google Classroom URL
- Creator-only edit/delete authorization
- Color-coded content type badges
- Backend: `course_contents` table with `text_content` column for extracted document text, CRUD API at `/api/course-contents/`

### 6.4.2 Course Detail Page (Phase 1) - IMPLEMENTED
Dedicated page for viewing and managing a single course and its content:
- **Route:** `/courses/:id` — accessible to all authenticated roles
- **Course header** — Name, subject, description, privacy badge, Google Classroom badge, created date
- **Edit Course** — Creator/admin can edit name, subject, description via modal (`PATCH /api/courses/{id}`)
- **Course Content list** — Full CRUD (add, edit, delete) for content items
- **Upload Document** — Drag-and-drop or file picker, extracts text via `/api/study/upload/extract-text`, stores as course content with `text_content` field
- **Optional study material generation** — Checkbox + dropdown (study guide, quiz, or flashcards) when uploading a document
- **Generate Study Guide** — Button on each content item to generate study guide from its `text_content` or `description`
- **Navigation** — Courses page cards now navigate to detail page instead of inline expand
- **All roles** — Courses and Study Guides navigation visible to parent, student, teacher, and admin

### 6.5 Performance Analytics (Phase 2)
- Subject-level insights
- Trend analysis
- Weekly progress reports

### 6.6 Communication (Phase 1) - IMPLEMENTED
- Secure Parent <-> Teacher messaging
- Announcements
- Message history
- Notification system with in-app bell, email reminders, and preferences

### 6.7 Notes & Project Tracking (Phase 2)
- Notes management (per-course note-taking, rich text editor)
- Project tracking (group projects, milestones, task breakdown)
- Study planner (weekly study schedules, goal setting)

### 6.8 Central Document Repository (Phase 1)
- Store course materials
- Teacher handouts
- Student notes
- Organized by course/subject

### 6.9 Tutor Marketplace (Phase 4)
Extends the existing `teacher_type=private_tutor` — no new "Tutor" role. Private tutors gain marketplace features:
- Tutor profiles (skills, subjects, availability, hourly rates, ratings)
- Parent/student tutor search and discovery
- AI-powered tutor recommendations based on student needs
- Booking workflow (request, confirm, schedule)
- Payment integration

### 6.10 Teacher Email Monitoring (Phase 1) - IMPLEMENTED
- Monitor teacher emails via Gmail integration
- Monitor Google Classroom announcements
- AI-powered email summarization
- Paginated communication list with type filter and search
- Manual sync trigger and background sync job

### 6.11 Teacher & Private Tutor Platform (Phase 1)

ClassBridge supports two categories of teachers with distinct onboarding paths.

#### Teacher Types
- **School Teacher**: A teacher at a school whose courses appear via Google Classroom sync. May or may not be on EMAI.
- **Private Tutor**: An independent educator who registers on EMAI to teach their own courses, potentially using their own Google Classroom.

#### Platform Teachers (on EMAI)
- Teacher registers on EMAI → `User` (role=teacher) + `Teacher` record created automatically
- `Teacher` record stores: school_name, department, `teacher_type` (school_teacher, private_tutor), `is_platform_user=true`
- Can create and manage courses manually (without Google Classroom)
- Can connect multiple Google accounts (personal + school) to sync courses from different sources
- Full access to Teacher Dashboard: messaging, communications, course management, student rosters

#### Non-EMAI School Teachers (Shadow + Invite)
When a parent/student syncs Google Classroom and the course teacher is not on EMAI:
1. **Shadow record created**: `Teacher` record with `is_platform_user=false`, name/email from Google Classroom
2. **Invite email sent**: Teacher receives an invite to join ClassBridge
3. **If accepted**: Shadow record converts to full platform teacher (`is_platform_user=true`), teacher sets password and can log in
4. **If not accepted**: Teacher remains a read-only reference — name shown on courses, parents can still contact them externally

#### Multi-Google Account Support
- `teacher_google_accounts` table (teacher_id, google_email, google_id, access_token, refresh_token, account_label, is_primary)
- A platform teacher can link multiple Google accounts (e.g., personal Google for private tutoring + school Google for school courses)
- Each account syncs its own courses independently
- Replaces the current single `google_access_token`/`google_refresh_token` on `User` for teachers

#### Manual Course Creation
- Platform teachers can create courses without Google Classroom
- Add students to courses by email
- Create assignments manually
- Supports private tutors who don't use Google at all

#### Data Model
- `Teacher` model: user_id, school_name, department, teacher_type, is_platform_user, invite_token, invite_token_expires
- `teacher_google_accounts` table: teacher_id, google_email, google_id, access_token, refresh_token, account_label, is_primary, created_at

### 6.12 Teacher Course Management & Google Classroom Sync (Phase 1)

Teachers need to see and manage their courses. ClassBridge supports three course sources for teachers, enabling both school teachers and private tutors to manage all their courses in one place.

#### Course Sources

| Source | Description | Who Uses It |
|--------|-------------|-------------|
| **Google Classroom Sync** | Import courses from a connected Google Classroom account | School teachers, private tutors with Google Classroom |
| **Manual Course Creation** | Create courses directly in EMAI without Google | Private tutors, teachers without Google Classroom |
| **Multi-Account Sync** | Sync courses from multiple Google accounts (personal + school) | Private tutors who teach at a school AND independently |

#### Google Classroom Sync for Teachers

When a teacher syncs courses from Google Classroom:
1. System fetches courses where the teacher is the **owner** (not just enrolled)
2. Each synced course is linked to the teacher's `Teacher` record via `teacher_id`
3. Assignments within those courses are also synced
4. Courses already synced (matched by `google_classroom_id`) are updated, not duplicated
5. Teacher can trigger a manual re-sync from their dashboard
6. Background job periodically syncs new courses/assignments (Phase 1.5)

#### Multi-Google Account Support (All Teachers)

Any teacher may need multiple Google accounts:
- **Private tutors**: Personal Google (e.g., `tutor@gmail.com`) for private tutoring courses + school Google (e.g., `tutor@school.edu`) for school courses
- **School teachers**: School Google account + a second school account if they teach at multiple schools, or a personal account for side tutoring

Each Google account may have different courses. ClassBridge supports linking multiple Google accounts:

- `teacher_google_accounts` table stores credentials per Google account
- Each account syncs its own courses independently
- Courses from all accounts appear together on the Teacher Dashboard
- Teacher can label accounts (e.g., "Personal", "Springfield High") for clarity
- Each account has its own OAuth tokens (access + refresh)
- One account is marked as primary (used for default operations)

#### Teacher Dashboard Course View

The Teacher Dashboard should show:
- All courses where `teacher_id` matches the current teacher
- Source badge: "Google Classroom" or "Manual" per course
- "Sync Courses" button (syncs from connected Google account)
- "Create Course" button (manual course creation)
- Student count per course
- Last synced timestamp

#### Data Flow

```
Teacher connects Google → Clicks "Sync Courses"
  → Backend fetches Google Classroom courses (teacherId filter)
  → Creates/updates Course records with teacher_id set
  → Returns synced course list
  → Dashboard refreshes and shows courses
```

#### API Changes Required

| Endpoint | Change |
|----------|--------|
| `POST /api/google/courses/sync` | Set `teacher_id` on synced courses when called by a teacher |
| `POST /api/teacher/courses` | Manual course creation (already planned, sets `teacher_id`) |
| `GET /api/courses/teaching` | Already works — queries by `teacher_id` |
| `GET /api/teacher/google-accounts` | Future: list linked Google accounts |
| `POST /api/teacher/google-accounts` | Future: link additional Google account |

### 6.13 Task Manager & Calendar (Phase 1)

A cross-role task/todo manager integrated into the calendar, available to all EMAI users. Any role can create tasks and assign them to related users. Provides a unified view of what's due, with role-aware data sources.

#### Task/Todo Manager
- Create, edit, complete, and delete tasks (personal or assigned to others)
- Task fields: title, description, due date, reminder date+time (time optional), priority (low, medium, high), category
- Tasks can optionally be assigned to another user (`assigned_to_user_id`) or linked to an assignment
- **Entity linking**: Tasks can be linked to a course (`course_id`), course content item (`course_content_id`), or study guide (`study_guide_id`). Create tasks directly from Study Guides page, Course Detail page, or per-content-item — link is pre-filled automatically. Linked entity name displayed as clickable badge on Tasks page — clicking navigates to the linked study guide, quiz, flashcards, or course detail page
- Quick-add from calendar date click, Day Detail Modal, dedicated Tasks page, Study Guides page (+Task button per guide), or Course Detail page (+Task button per content item)
- Filter by status (pending, completed), priority, date range, assignee, course
- Dedicated `/tasks` page for full task management (all roles)
- **Task Detail Page** (`/tasks/:id`): Dedicated page showing task info card (title, description, due date, priority, status, assignee, creator), toggle complete / delete actions, and linked resources section (study guide, course material, course links) with link/unlink UI — icon buttons to add new links, searchable modal with tabbed resource types, unlink (×) button on each resource card. `GET /api/tasks/{task_id}` endpoint with creator/assignee/parent authorization. `PATCH /api/tasks/{task_id}` supports linking via `course_id`, `course_content_id`, `study_guide_id` (send 0 to unlink) - IMPLEMENTED
- **Calendar task popover**: Clicking a task on the calendar shows a popover with a "See Task Details" button that navigates to the Task Detail Page

#### Cross-Role Task Assignment
Any user can create a task and assign it to a related user. Relationship verification is enforced server-side:

| Creator Role | Can Assign To | Relationship Check |
|-------------|---------------|-------------------|
| **Parent** | Linked children (students) | `parent_students` join table |
| **Teacher** | Students in their courses | `courses` + `student_courses` enrollment |
| **Student** | Linked parents | `parent_students` join table (reverse) |
| **Admin** | Self only (personal tasks) | N/A |

- Assigned tasks appear in both the creator's and assignee's task lists
- The assignee can view and complete assigned tasks but cannot edit or delete them
- The creator can edit, reassign, or delete tasks they created

#### Calendar Integration
- Tasks appear on the calendar alongside assignments, visually distinct (dashed left border, priority-based color vs. solid border with course color for assignments)
- Completed tasks show strikethrough text + muted opacity
- Clicking a calendar date opens a **Day Detail Modal** showing all assignments + tasks for that date
- Day Detail Modal supports: viewing items, adding new tasks, toggling completion, editing/deleting existing items
- Clicking a task on the calendar opens a popover; task title is clickable and navigates to Task Detail Page (`/tasks/:id`). Popover action buttons use icon buttons with title tooltips: clipboard (See Task Details), open book (Create Study Guide), graduation cap (Go to Course), books (View Study Guides)
- **Drag-and-drop rescheduling**: Users can drag task entries (chips in month view, cards in week/3-day view) to a different day to reschedule. Uses native HTML5 DnD with optimistic UI and rollback on failure. Only tasks are draggable — assignments remain fixed. Drop targets highlight with a blue dashed outline during drag.

#### Reminders
- Each task can have an optional reminder with date and time
- Time is optional — if omitted, reminder defaults to start of day (e.g., 8:00 AM)
- Reminders trigger in-app notifications (Phase 1) and optionally email (Phase 2)
- Reminder scheduling uses existing APScheduler infrastructure

#### Role-Aware Calendar Data Sources
| Role | Calendar Shows |
|------|---------------|
| **Student** | Assignment due dates + personal tasks + tasks assigned by parents/teachers |
| **Parent** | Children's assignment due dates + personal tasks + tasks assigned by children |
| **Teacher** | Course assignment deadlines + personal tasks + tasks assigned by students |
| **Admin** | Personal tasks/reminders only |

#### Google Calendar Integration (One-Way Push) — Phase 1.5
- Push EMAI reminders and deadlines to the user's Google Calendar
- Uses existing Google OAuth connection
- User can toggle which items sync to Google Calendar (per-task or global setting)
- `google_calendar_event_id` stored on tasks for update/delete sync

#### Data Model
- `tasks` table: id, created_by_user_id (FK→users.id), assigned_to_user_id (FK→users.id, nullable), title, description, due_date, reminder_at (nullable), is_completed, completed_at (nullable), priority (low/medium/high, default medium), category (nullable), course_id (nullable, FK→courses.id), course_content_id (nullable, FK→course_contents.id), study_guide_id (nullable, FK→study_guides.id), linked_assignment_id (nullable, FK→assignments.id), google_calendar_event_id (nullable), created_at, updated_at
- `created_by_user_id` — the user who created the task (any role)
- `assigned_to_user_id` — the user the task is assigned to (nullable = personal/self task)
- Assignment due dates queried from existing `assignments` table (not duplicated)
- Parent calendar aggregates children's assignments via `parent_students` + `student_courses` + `assignments`
- GET `/api/tasks/` returns tasks where user is creator OR assignee

### 6.14 Audit Logging (Phase 1) - IMPLEMENTED

Persistent audit log tracking sensitive actions for FERPA/PIPEDA compliance and security incident investigation.

#### What's Logged
| Action | Resource | Route |
|--------|----------|-------|
| login / login_failed | user | `auth.py` |
| create (register, accept-invite) | user | `auth.py` |
| create / delete | task | `tasks.py` |
| create / delete | study_guide | `study.py` |
| create / update | course | `courses.py` |
| create | message | `messages.py` |
| read (list children, child overview) | student / children | `parent.py` |
| sync | google_classroom | `google_classroom.py` |

#### Data Model
- `audit_logs` table: id, user_id (FK→users, nullable for failed logins), action (String(20)), resource_type (String(50)), resource_id (nullable), details (JSON text), ip_address (String(45)), user_agent (String(500)), created_at
- Indexes: (user_id, created_at), (resource_type, resource_id), (action, created_at)

#### Admin API
- `GET /api/admin/audit-logs` — paginated, filterable (user_id, action, resource_type, date_from, date_to, search). Admin only. Returns items with resolved user_name

#### Admin UI
- `/admin/audit-log` — table view with filters (action, resource type, search), pagination
- Linked from Admin Dashboard via "View Audit Log" button

#### Configuration
- `AUDIT_LOG_ENABLED` (default: true) — feature toggle
- `AUDIT_LOG_RETENTION_DAYS` (default: 90) — retention period for cleanup

#### Design
- Append-only: no update/delete API for audit entries
- Non-blocking: `log_action()` silently fails on error, never blocks requests
- Uses `String(20)` for action column (not Enum) for SQLite/PostgreSQL compatibility

### 6.15 Color Theme System (Phase 1)

Three site-wide color themes with user preference persistence.

#### Themes

| Theme | Surface | Ink | Accent | Description |
|-------|---------|-----|--------|-------------|
| **Light** (default) | `#ffffff` / `#f5f6f9` | `#1b1e2b` / `#5b6274` | `#49b8c0` / `#f4801f` | Current palette, bright and clean |
| **Dark** | `#1a1d2e` / `#252836` | `#e8eaf0` / `#9ca0b0` | `#5ccfd6` / `#f6923a` | Dark surfaces, lighter text, boosted accents for contrast |
| **Focus** | `#faf8f5` / `#f0ece6` | `#2c2a26` / `#6b6560` | `#5a9e8f` / `#c47f3b` | Muted warm tones, reduced saturation for extended study sessions |

#### Architecture
- **CSS approach**: `data-theme` attribute on `<html>` element; CSS variable overrides per theme
- **ThemeContext**: React context provider (`frontend/src/context/ThemeContext.tsx`) manages active theme, persists to `localStorage` key `classbridge-theme`
- **Auto-detect**: First visit defaults to OS preference via `prefers-color-scheme` media query (light/dark); "Focus" is user-explicit only
- **ThemeToggle component**: 3-way toggle (icon-based: sun / moon / leaf) placed in DashboardLayout header
- **Variable scope**: All color tokens in `:root` / `[data-theme="light"]`, overridden in `[data-theme="dark"]` and `[data-theme="focus"]`

#### Prerequisites
- Convert all hardcoded hex/rgba colors to CSS variables (especially `CourseMaterialDetailPage.css` which has zero variable usage)
- Add missing semantic variables: `--color-success`, `--color-accent-bg`, `--color-surface-raised`
- Add RGB companion variables for `rgba()` patterns: `--color-accent-rgb`, `--color-blue-rgb`

#### Variables Required
Existing 12 variables + new additions:
- `--color-success` — green for positive states
- `--color-accent-bg` — light accent tint for hover/active backgrounds
- `--color-surface-raised` — elevated card/modal backgrounds
- `--color-ink-rgb`, `--color-accent-rgb`, `--color-blue-rgb` — RGB triplets for `rgba()` usage
- `--color-shadow` — shadow base color (opaque in light, transparent in dark)

#### Implementation Steps
1. Hardcoded color cleanup — refactor ~56 hardcoded color values across ~5 CSS files to use variables
2. Add new semantic variables to `:root` in `index.css`
3. Define Dark and Focus theme palettes as `[data-theme="dark"]` and `[data-theme="focus"]` blocks
4. Create `ThemeContext.tsx` with `useTheme()` hook
5. Create `ThemeToggle` component (3-way toggle)
6. Integrate toggle into `DashboardLayout` header
7. Visual QA on all pages for each theme

### 6.16 Global Search (Phase 1.5)

A unified search field in the DashboardLayout header that searches across the entire ClassBridge platform. Available to all roles (parent, student, teacher, admin).

**Searchable Entities:**

| Entity | Searchable Fields | Result Navigation |
|--------|-------------------|-------------------|
| Courses | name, description | `/courses/{id}` |
| Study Guides | title | `/study/guide/{id}`, `/study/quiz/{id}`, `/study/flashcards/{id}` |
| Tasks | title, description | `/tasks/{id}` |
| Course Content | title, description | `/study-guides/{id}` |

**Backend:**
- `GET /api/search?q=<query>&types=<csv>&limit=<n>` — unified search endpoint
- Case-insensitive `ilike()` matching (same pattern as admin user search)
- Results respect role-based access (parents see children's data, students see own, etc.)
- Returns results grouped by entity type with count per type
- Default: 5 results per type, minimum query length: 2 characters

**Data Model:** No new tables — queries existing Course, StudyGuide, Task, CourseContent tables.

**Frontend:**
- `GlobalSearch` component in DashboardLayout header (all roles)
- Debounced input (300ms), dropdown overlay with grouped results
- Type icons per category: courses (🎓), study guides (📖), tasks (📋), content (📄)
- Keyboard: Escape closes, Ctrl+K / Cmd+K to focus search
- Click result → navigate to detail page, click outside → close

**Implementation Steps:**
1. Create `app/schemas/search.py` (SearchResultItem, SearchResponse)
2. Create `app/api/routes/search.py` (GET /api/search)
3. Register router in `main.py`
4. Add `searchApi` to `frontend/src/api/client.ts`
5. Create `frontend/src/components/GlobalSearch.tsx` + `.css`
6. Integrate into `DashboardLayout.tsx` header

### 6.17 AI Email Communication Agent (Phase 5)
- Compose messages inside ClassBridge
- AI formats and sends email to teacher
- AI-powered reply suggestions
- Searchable email archive

---

## 7. Role-Based Dashboards - IMPLEMENTED

Each user role has a customized dashboard (dispatcher pattern via `Dashboard.tsx`):

| Dashboard | Key Features | Status |
|-----------|--------------|--------|
| **Parent Dashboard** | Left nav (Courses, Study Guides, Messages), calendar-centric main area (Day/3-Day/Week/Month views), child filter tabs with edit child modal, day detail modal (CRUD tasks/assignments), task management with reminders, course color-coding | Implemented (v2 in progress) |
| **Student Dashboard** | Courses, assignments, study tools, Google Classroom sync, file upload | Implemented |
| **Teacher Dashboard** | Courses teaching, manual course creation, multi-Google account management, messages, teacher communications | Implemented (partial) |
| **Admin Dashboard** | Platform stats, user management table (search, filter, pagination) | Implemented |

> **Note:** Phase 4 adds marketplace features (bookings, availability, profiles) to the existing Teacher Dashboard for teachers with `teacher_type=private_tutor`. No separate "Tutor Dashboard" is needed.

### Parent Dashboard Layout (v2) - IN PROGRESS

The Parent Dashboard uses a **three-panel layout**: left navigation, calendar-centric main area, and modal-based management views.

#### Layout Structure
```
[Header (compact padding)                                    ]
[Left Nav        | Child Tabs: Child1 | Child2 | ...         ]
[  Dashboard     | Calendar                                  ]
[  Courses       |   Header: < Today > Title                 ]
[  Study Guides  |   View: Day|3-Day|Week|Month              ]
[  Messages      |   Grid with assignments + tasks           ]
[  + Add Child   |                                           ]
[  + Add Course  |                                           ]
[  + Study Guide |   [+ Create Study Guide] [View Guides]    ]
[  + Add Task    |                                           ]
```

#### 1. Header Row
- Compact padding (reduced from default) to maximize content area

#### 2. Left Navigation
The `DashboardLayout` sidebar includes role-specific navigation items for parents:
- **Dashboard** — Home view (calendar)
- **Courses** — Opens dedicated Courses management view
- **Study Guides** — Opens dedicated Study Guides management view
- **Messages** — Opens messaging view
- **+ Add Child** — Opens Add Child modal
- **+ Add Course** — Opens Create Course modal
- **+ Create Study Guide** — Opens Study Tools modal
- **+ Add Task** — Opens Add Task modal

#### 3. Child Filter Tabs (Toggle Behavior)
- Each child appears as a clickable tab button above the calendar
- **Click** a child tab → filters calendar, courses, and study guides to that child only
- **Click again** (unclick) → deselects child, shows **all children's data combined** plus parent's own tasks
- In "All" mode: calendar merges all children's assignments with child-name labels on each entry
- Single-child families: no tabs shown, child is implicitly selected

#### 4. Edit Child Modal
- Child name in the tab shows an **edit link** (replaces the old "parent/guardian" role label)
- Clicking edit opens a modal with tabs:
  - **Details** — Edit child name, email, grade level, school
  - **Courses** — View/manage assigned courses, assign new courses
  - **Reminders** — Configure reminders for the child (after Task system is built)

#### 5. Calendar Views
- **Month View**: 7-column grid with assignment chips + task dots, click day to open Day Detail Modal
- **Week View**: 7-column layout with stacked assignment/task cards
- **3-Day View**: 3-column layout identical to Week but showing only 3 days
- **Day View**: Single-column list of all assignments + tasks for one day

#### 6. Day Detail Modal
Clicking a **date** on the calendar opens a modal showing all items for that day:
- Lists all assignments and tasks for the selected date
- Each item shows: title, type (assignment/task), course (if applicable), time, status
- **Add Task** button to create a new task for that date
- **Edit/Delete** actions on each item (CRUD)
- For assignments: "Create Study Guide" action
- Scoped to selected child or all children based on filter state

#### 7. Tasks with Reminders
- **Add Task** button in left nav and in Day Detail Modal
- Task modal fields: title, description, due date, reminder date+time (time optional), priority, linked child (optional)
- Tasks appear on calendar alongside assignments (visually distinct)
- Clicking a task on the calendar opens it for editing
- Reminders trigger in-app notifications

#### 8. Courses View (Left Nav → `/courses`)
Dedicated page for course management (accessible to all roles):
- **List all courses** — parent-created + child-enrolled courses (parent view); all visible courses (student/teacher view)
- **Click course card** → navigates to Course Detail Page (`/courses/:id`) for full content management
- **Create new course** — name, subject, description (all roles)
- **Assign to children** — parent only, supports assigning one course to multiple children
- **Course Detail Page** — edit course, CRUD content, upload documents, generate study materials (see §6.4.2)
- Course cards show: name, subject, teacher name, Google badge

#### 9. Study Guides View (Left Nav → `/study-guides`)
Dedicated page for study guide management:
- **List all guides** — parent's own + children's guides
- **Create study guide** — opens Study Tools modal (text or file upload)
- **Assign to course** — CourseAssignSelect dropdown on each guide
- **CRUD operations** — view, edit metadata, delete
- Filter by: type (guide/quiz/flashcards), course, child

#### Calendar Components (Reusable)
Located in `frontend/src/components/calendar/`:
- `useCalendarNav` — Hook for date navigation, view mode, range computation
- `CalendarView` — Orchestrator component (header + active grid + popover)
- `CalendarHeader` — Nav buttons, title, view toggle
- `CalendarMonthGrid` / `CalendarDayCell` — Month view grid
- `CalendarWeekGrid` — Week/3-day column layout
- `CalendarDayGrid` — Single-day list view
- `CalendarEntry` — Assignment/task rendered as chip (month) or card (week/day); tasks are draggable for rescheduling
- `CalendarEntryPopover` — Assignment/task detail popover
- `DayDetailModal` — Full CRUD modal for a specific date (new)

#### Drag-and-Drop Task Rescheduling
- Tasks can be dragged to a different day in month view (chips) or week/3-day view (cards)
- Uses native HTML5 Drag and Drop API (no external library)
- Drop targets (day cells, week columns) highlight with blue dashed outline during drag
- Optimistic UI: task moves immediately on drop, reverts if API update fails
- Only tasks are draggable — classroom assignments remain fixed
- Drag data carries task ID and `itemType: 'task'` for validation

#### Key Design Details
- **Course Color-Coding**: 10-color palette assigned by course index, consistent everywhere
- **Task vs Assignment**: Assignments have course color border; tasks have a distinct style (e.g., dashed border or priority-based color)
- **Responsive**: At < 1024px, left nav collapses to icons; calendar takes full width
- **Right sidebar removed**: Courses and Study Guides promoted to dedicated pages via left nav

### Parent-Student Relationship
Parents and students have a **many-to-many** relationship via the `parent_students` join table. A student can have multiple parents (mother, father, guardian), and parent linking is optional.

**Registration & Linking Methods:**
- **Parent Registers Child**: Create a student account from the Parent Dashboard; child receives an invite email to set their password
- **Link by Email**: Enter an existing student's registered email address
- **Via Google Classroom**: Connect Google account, auto-discover children enrolled in Google Classroom courses, select and bulk-link
- **Self-Registered Student**: Students can register independently and use the platform without any parent

### Role-Based Access Control
- Backend: `require_role()` dependency factory for endpoint-level role checking
- Frontend: `ProtectedRoute` component with optional `allowedRoles` prop
- Shared `DashboardLayout` component for common header/nav across all dashboards

---

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
- [ ] **Parent Dashboard v2: Left navigation** — move Add Child, Add Course, Create Study Guide, Add Task to DashboardLayout left nav; compact header padding
- [ ] **Parent Dashboard v2: Child filter toggle** — click/unclick child tabs; "All" mode merges all children's data + parent tasks; child-name labels in All mode
- [ ] **Parent Dashboard v2: Edit Child modal** — edit child details, manage course assignments, setup reminders
- [ ] **Parent Dashboard v2: Day Detail Modal** — click date to open modal with CRUD for all tasks/assignments on that date
- [ ] **Parent Dashboard v2: Dedicated Courses page** — `/courses` route with full CRUD, multi-child assignment, study guide creation from course
- [ ] **Parent Dashboard v2: Dedicated Study Guides page** — `/study-guides` route with full CRUD, course assignment, filtering
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
- [x] **Calendar task popover: See Task Details button** — Icon buttons in popover (clipboard=task details, book=create study guide, graduation cap=go to course, books=view study guides) with title tooltips; fixed task ID offset bug where navigation used calendar-internal offset ID instead of real task ID (IMPLEMENTED)
- [x] **Ungrouped study guide categorization** — Folder icon button on ungrouped guides opens "Move to Course" modal with searchable course list and inline "Create new course" option; backend PATCH auto-creates CourseContent via ensure_course_and_content() (IMPLEMENTED)
- [ ] **Color theme system: Hardcoded color cleanup** — Convert ~56 hardcoded hex/rgba values to CSS variables (priority: CourseMaterialDetailPage.css)
- [ ] **Color theme system: Dark mode** — Define dark palette in `[data-theme="dark"]`, ThemeContext, ThemeToggle in header
- [ ] **Color theme system: Focus mode** — Define focus palette in `[data-theme="focus"]`, muted warm tones for study sessions
- [ ] **Make student email optional** — parent can create child with name only (no email, no login)
- [ ] **Parent creates child** endpoint (`POST /api/parent/children/create`) — name required, email optional
- [ ] **Parent creates courses** — allow PARENT role to create courses (private to their children)
- [ ] **Parent assigns courses to children** — `POST /api/parent/children/{student_id}/courses`
- [ ] **Student creates courses** — allow STUDENT role to create courses (visible to self only)
- [ ] **Add `created_by_user_id` and `is_private` to Course model**
- [ ] **Disable auto-sync jobs by default** — all Google Classroom/Gmail sync is manual, on-demand only
- [ ] Manual course creation for teachers
- [ ] Manual assignment creation for teachers
- [ ] Multi-Google account support for teachers
- [ ] Auto-send invite email to shadow teachers on creation
- [ ] Teacher Dashboard course management view with source badges

#### Architecture Foundation (Tier 0)
- [ ] **Split api/client.ts** — Break 794-LOC monolith into domain-specific API modules (#127)
- [ ] **Extract backend services** — Move business logic from route handlers to domain service layer (#128)
- [ ] **Repository pattern** — Introduce data access layer abstracting SQLAlchemy queries (#129)
- [ ] **Split ParentDashboard** — Break 1222-LOC component into composable sub-components (#130)
- [ ] **Activate TanStack Query** — Replace manual useState/useEffect data fetching with React Query hooks (#131)
- [ ] **Backend DDD modules** — Reorganize into bounded context directories (#132)
- [ ] **Frontend DDD modules** — Reorganize into domain directories (#133)
- [ ] **Domain events** — Add event system for cross-context communication (#134)

#### Security & Hardening (Tier 0)
- [ ] **Authorization gaps** — `list_students()` returns ALL students to any auth user; `get_user()` has no permission check; `list_assignments()` not filtered by course access (#139)
- [ ] **Rate limiting** — No rate limiting on AI generation, auth, or file upload endpoints; risk of brute force and API quota abuse (#140)
- [ ] **CORS hardening** — Currently allows `*` origins; tighten to known frontend domains (#64)
- [ ] **Security headers** — Add X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security, CSP (#141)
- [ ] **Input validation** — Missing field length limits, URL validation, and sanitization on multiple endpoints (#142)
- [ ] **Password reset flow** — No "Forgot Password" link or reset mechanism (#143)

#### Data Integrity & Performance (Tier 0)
- [ ] **Missing database indexes** — Add indexes on StudyGuide(assignment_id), StudyGuide(user_id, created_at), Task(created_by_user_id, created_at), Invite(email, expires_at), Message(conversation_id) (#73)
- [ ] **N+1 query patterns** — `_task_to_response()` does 3-4 extra queries per task; `list_children()` iterates students; assignment reminder job loads all users individually (#144)
- [ ] **CASCADE delete rules** — Task, StudyGuide, Assignment FKs lack ON DELETE CASCADE/SET NULL; orphaned records possible (#145)
- [ ] **Unique constraint on parent_students** — No unique constraint on (parent_id, student_id); duplicate links possible (#146)

#### Frontend UX Gaps (Tier 1)
- [ ] **Global error boundary** — No React ErrorBoundary; unhandled errors crash the entire app (#147)
- [ ] **Toast notification system** — No centralized success/error feedback; 6+ silent catch blocks in TasksPage alone (#148)
- [ ] **Token refresh** — JWT tokens expire without refresh mechanism; users lose work and get silently redirected to login (#149)
- [ ] **Loading skeletons** — Plain "Loading..." text everywhere instead of skeleton screens (#150)
- [ ] **Accessibility (A11Y)** — Missing aria-labels on icon buttons, no keyboard nav for modals/dropdowns, no skip-to-content link, color-only indicators (#151)
- [ ] **Mobile responsiveness** — Calendar not optimized for mobile; tables don't scroll; modals overflow on small screens; no touch drag-drop (#152)
- [ ] **FlashcardsPage stale closure bug** — `handleKeyDown` event listener captures stale state; arrow keys stop working after card flip (#153)

#### Testing Gaps (Tier 1)
- [ ] **Frontend unit tests** — Zero frontend unit tests; no vitest/jest configured (#154)
- [ ] **Missing route tests** — No tests for: google_classroom, study, messages, notifications, teacher_communications, admin, invites, course_contents routes (#155)
- [ ] **PostgreSQL test coverage** — Tests run on SQLite only; misses NOT NULL, Enum, and type divergences (e.g., users.email bug) (#156)

### Phase 1.5 (Calendar Extension, Content & School Integration)
- [ ] Student email identity merging (personal + school email on same account)
- [ ] School board email integration (when DTAP approved)
- [ ] Extend calendar to Student and Teacher dashboards with role-aware data
- [ ] Google Calendar push integration (sync tasks/reminders to Google Calendar)
- [ ] Central document repository
- [ ] Manual content upload with OCR (enhanced)
- [ ] Background periodic Google Classroom course/assignment sync for teachers (opt-in)

### Phase 2
- [ ] TeachAssist integration
- [ ] Performance analytics dashboard
- [ ] Advanced notifications
- [ ] Notes & project tracking tools
- [ ] Data privacy & user rights (account deletion, data export, consent)

### Phase 3
- [ ] Mobile-first optimization
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

## 9. Technical Architecture

### Stack
- **Frontend:** React + TypeScript + Vite
- **Backend:** Python (FastAPI)
- **AI Services:** OpenAI GPT-4o-mini / Vertex AI
- **Database:** PostgreSQL (production), SQLite (development)
- **Object Storage:** Google Cloud Storage
- **Authentication:** OAuth2 + RBAC

### Architecture Direction: Domain-Driven Design (DDD)

ClassBridge is migrating from a transaction-script pattern to a modular Domain-Driven Design (DDD) architecture. Current maturity grade: **C-**. This migration is tracked across issues #127–#134 and will be implemented incrementally alongside feature work.

#### Current Architecture Issues
- **Backend**: Business logic lives in route handlers, no repository layer, cross-domain coupling (tasks imports 3+ domain models), anemic models, no domain events
- **Frontend**: `ParentDashboard.tsx` is 1222 LOC with 33+ useState hooks, `api/client.ts` is 794 LOC monolith, TanStack Query installed but unused, no custom hooks

#### Bounded Contexts

| Context | Backend Domain | Frontend Module | Models |
|---------|---------------|-----------------|--------|
| **Auth & Identity** | `app/domains/auth/` | `src/domains/auth/` | User, Student, Teacher, Invite |
| **Education** | `app/domains/education/` | `src/domains/education/` | Course, Assignment, CourseContent, Enrollment |
| **Study Tools** | `app/domains/study/` | `src/domains/study/` | StudyGuide (guide, quiz, flashcards) |
| **Tasks & Planning** | `app/domains/tasks/` | `src/domains/tasks/` | Task, RecurringTaskTemplate (future) |
| **Communication** | `app/domains/communication/` | `src/domains/communication/` | Conversation, Message, TeacherCommunication |
| **Notifications** | `app/domains/notifications/` | `src/domains/notifications/` | Notification, NotificationPreference |

#### Target Backend Structure (per domain)
```
app/domains/{context}/
  models.py        # SQLAlchemy models (aggregate roots)
  schemas.py       # Pydantic request/response models
  repository.py    # Data access layer (abstracts DB queries)
  service.py       # Business logic (orchestrates repos + rules)
  routes.py        # FastAPI router (thin, delegates to service)
  events.py        # Domain events (future, #134)
```

#### Target Frontend Structure (per domain)
```
src/domains/{context}/
  api.ts           # Axios calls for this domain only
  hooks.ts         # TanStack Query hooks (useQuery, useMutation)
  types.ts         # TypeScript interfaces
  components/      # Domain-specific UI components
  pages/           # Route-level pages
```

#### Migration Phases
1. **Phase A (Foundation)**: Split `api/client.ts` (#127), extract backend services (#128), introduce repository pattern (#129)
2. **Phase B (Frontend)**: Split `ParentDashboard` (#130), activate TanStack Query (#131)
3. **Phase C (Full DDD)**: Reorganize backend into domain modules (#132), reorganize frontend into domain modules (#133)
4. **Phase D (Events)**: Add domain events for cross-context communication (#134)

### Google OAuth Scopes
| Scope | Purpose | Used By |
|-------|---------|---------|
| `classroom.courses.readonly` | Read Google Classroom courses | All roles (sync) |
| `classroom.coursework.students.readonly` | Read assignments | Student, Parent |
| `classroom.rosters.readonly` | Read course rosters (teacher info) | Parent (discover children) |
| `gmail.readonly` | Read teacher emails for monitoring | Teacher |
| `calendar.events` | Push tasks/reminders to Google Calendar | All roles (Phase 1.5) |
| `userinfo.email`, `userinfo.profile` | Basic identity for OAuth | All roles |

**Notes:**
- Scopes are requested incrementally — only `userinfo` + `classroom` scopes at initial connect; `calendar.events` requested when user enables Google Calendar sync
- Teachers with multi-Google accounts: each `teacher_google_accounts` entry stores its own tokens with the scopes relevant to that account
- Scope expansion requires Google OAuth verification (Issue #14)

### API Endpoints

> Full interactive API docs available at `/docs` (Swagger) and `/redoc` when running locally.

#### Implemented Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | User registration (auto-creates Teacher record for role=teacher) |
| `/api/auth/login` | POST | User login (returns JWT) |
| `/api/auth/accept-invite` | POST | Accept invite and set password (unified: student + teacher) |
| `/api/users/me` | GET | Current user info |
| `/api/users/{user_id}` | GET | Get user by ID |
| `/api/google/connect` | GET | Get Google OAuth authorization URL |
| `/api/google/callback` | GET | Handle OAuth callback |
| `/api/google/status` | GET | Google connection status |
| `/api/google/disconnect` | DELETE | Disconnect Google |
| `/api/google/courses` | GET | List Google Classroom courses (remote) |
| `/api/google/courses/sync` | POST | Sync Google Classroom courses to local DB |
| `/api/google/courses/{course_id}/assignments` | GET | Get assignments for a Google Classroom course |
| `/api/google/courses/{course_id}/assignments/sync` | POST | Sync assignments from Google Classroom course |
| `/api/courses/` | GET | List all courses |
| `/api/courses/` | POST | Create course (all roles — auto-assigns teacher for teacher role) |
| `/api/courses/teaching` | GET | List courses teaching (teacher only) |
| `/api/courses/created/me` | GET | List courses created by current user |
| `/api/courses/enrolled/me` | GET | List courses student is enrolled in (student only) |
| `/api/courses/{id}` | GET | Get course details |
| `/api/courses/{id}` | PATCH | Update course (creator or admin only) |
| `/api/courses/{id}/enroll` | POST | Enroll in course (student only) |
| `/api/courses/{id}/enroll` | DELETE | Unenroll from course (student only) |
| `/api/courses/{id}/students` | GET | List enrolled students (teacher only, owns course) |
| `/api/assignments/` | GET | List assignments |
| `/api/study/generate` | POST | Generate study guide |
| `/api/study/quiz/generate` | POST | Generate quiz |
| `/api/study/flashcards/generate` | POST | Generate flashcards |
| `/api/study/guides` | GET | List study materials |
| `/api/study/guides/{guide_id}` | GET | Get a specific study guide |
| `/api/study/guides/{guide_id}` | PATCH | Update a study guide (assign to course) |
| `/api/study/guides/{guide_id}` | DELETE | Delete a study guide |
| `/api/study/check-duplicate` | POST | Check for duplicate study guide before generation |
| `/api/study/guides/{id}/versions` | GET | List all versions of a study guide |
| `/api/study/upload/generate` | POST | Generate from uploaded file |
| `/api/study/upload/extract-text` | POST | Extract text from uploaded file |
| `/api/study/upload/formats` | GET | Supported upload formats |
| `/api/messages/recipients` | GET | List valid message recipients |
| `/api/messages/conversations` | GET | List message conversations |
| `/api/messages/conversations` | POST | Create conversation |
| `/api/messages/conversations/{id}` | GET | Get conversation with messages |
| `/api/messages/conversations/{id}/messages` | POST | Send message |
| `/api/messages/conversations/{id}/read` | PATCH | Mark conversation messages as read |
| `/api/messages/unread-count` | GET | Unread message count |
| `/api/notifications/` | GET | List notifications |
| `/api/notifications/unread-count` | GET | Unread notification count |
| `/api/notifications/{id}/read` | PUT | Mark notification as read |
| `/api/notifications/read-all` | PUT | Mark all notifications as read |
| `/api/notifications/{id}` | DELETE | Delete a notification |
| `/api/notifications/settings` | GET/PUT | Get or update notification preferences |
| `/api/teacher-communications/` | GET | List teacher communications (with search/filter) |
| `/api/teacher-communications/{id}` | GET | Get single communication with details |
| `/api/teacher-communications/{id}/read` | PUT | Mark communication as read |
| `/api/teacher-communications/status` | GET | Email monitoring status and stats |
| `/api/teacher-communications/sync` | POST | Trigger email sync |
| `/api/parent/children` | GET | List linked children |
| `/api/parent/children/link` | POST | Link child by email (uses `student_email` field) |
| `/api/parent/children/discover-google` | POST | Discover children via Google Classroom |
| `/api/parent/children/link-bulk` | POST | Bulk link children |
| `/api/parent/children/{student_id}/overview` | GET | Child overview (courses, assignments, study materials) |
| `/api/parent/children/{student_id}/sync-courses` | POST | Trigger course sync for a child |
| `/api/invites/` | POST | Create an invite (parent→student, teacher/admin→teacher) |
| `/api/invites/sent` | GET | List invites sent by current user |
| `/api/admin/users` | GET | Paginated user list with search/filter (admin only) |
| `/api/admin/stats` | GET | Platform statistics (admin only) |
| `/api/admin/audit-logs` | GET | Paginated audit logs with filters (admin only) |
| `/api/tasks/` | GET | List tasks (creator or assignee, filters: is_completed, priority, include_archived, course_id) |
| `/api/tasks/` | POST | Create task (with optional cross-role assignment and entity linking: course_id, course_content_id, study_guide_id) |
| `/api/tasks/{id}` | PATCH | Update task (creator: all fields; assignee: completion only) |
| `/api/tasks/{id}` | DELETE | Soft-delete (archive) task (creator only) |
| `/api/tasks/{id}/restore` | PATCH | Restore archived task (creator only) |
| `/api/tasks/{id}/permanent` | DELETE | Permanently delete archived task (creator only) |
| `/api/tasks/assignable-users` | GET | List users the current user can assign tasks to |
| `/api/logs/` | POST | Frontend log ingestion |
| `/api/logs/batch` | POST | Frontend batch log ingestion |

#### Planned Endpoints (Not Yet Implemented)

| Endpoint | Method | Description | Issue |
|----------|--------|-------------|-------|
| `/api/parent/children/create` | POST | Create child with name (email optional) | #90 |
| `/api/parent/children/{student_id}/courses` | POST | Assign course to child | #92 |
| `/api/parent/children/{student_id}/courses/{course_id}` | DELETE | Remove course from child | #92 |
| ~~`/api/courses/`~~ | ~~POST~~ | ~~Create course (parent, student, or teacher)~~ | ~~#91~~ (IMPLEMENTED) |
| `/api/teacher/courses/{id}/students` | POST | Add student to course by teacher | #42 |
| `/api/teacher/courses/{id}/assignments` | POST | Create assignment for a course | #49 |
| `/api/teacher/google-accounts` | GET | List linked Google accounts | #41, #62 |
| `/api/teacher/google-accounts` | POST | Link a new Google account | #41, #62 |
| `/api/teacher/google-accounts/{id}` | DELETE | Unlink a Google account | #41, #62 |
| `/api/parent/children/{student_id}` | PATCH | Edit child details (name, email, grade, school) | #99 |
| ~~`/api/tasks/`~~ | ~~GET~~ | ~~List tasks~~ | ~~#100~~ (IMPLEMENTED) |
| ~~`/api/tasks/`~~ | ~~POST~~ | ~~Create task~~ | ~~#100~~ (IMPLEMENTED) |
| ~~`/api/tasks/{id}`~~ | ~~PATCH~~ | ~~Update task~~ | ~~#100~~ (IMPLEMENTED) |
| ~~`/api/tasks/{id}`~~ | ~~DELETE~~ | ~~Soft-delete (archive) task~~ | ~~#100~~ (IMPLEMENTED) |
| ~~`/api/tasks/{id}/restore`~~ | ~~PATCH~~ | ~~Restore archived task~~ | ~~#107~~ (IMPLEMENTED) |
| ~~`/api/tasks/{id}/permanent`~~ | ~~DELETE~~ | ~~Permanently delete archived task~~ | ~~#107~~ (IMPLEMENTED) |
| `/api/calendar/events` | GET | Calendar events (role-aware, assignments + tasks) | #45 |
| `/api/calendar/google-sync` | POST | Push to Google Calendar (Phase 1.5) | #46 |

---

## 10. Non-Functional Requirements

- **Availability:** 99.9% uptime
- **Performance:** <2s response time
- **Scalability:** 100k+ users
- **Security:** Encryption in transit and at rest
- **Compliance:** FERPA, MFIPPA, PIPEDA, GDPR (if applicable)

### 10.1 Data Privacy & User Rights

ClassBridge handles student data subject to FERPA, PIPEDA, and MFIPPA. The following capabilities are required (implementation deferred to Phase 2+):

- **Account Deletion**: Users can request full account deletion. System must cascade-delete or anonymize all related records (tasks, messages, parent-student links, study materials, Google tokens).
- **Data Export**: Users can request a machine-readable export (JSON/CSV) of all personal data (GDPR Article 20, PIPEDA right of access).
- **Consent Management**: Track and store user consent for data collection, Google OAuth scopes, and email communications. Allow users to withdraw consent.
- **Data Retention**: Define retention periods for inactive accounts, expired invites, and completed tasks. Auto-purge after defined periods.
- **Minor Data Protection**: Student accounts (especially those created by parents) require additional protections — no marketing emails, limited data sharing, parental consent for under-13 users.
- **Audit Logging**: Log access to sensitive data (parent viewing child data, admin viewing user list) for compliance auditing. **Phase 1 implementation complete** — see §6.14. Future: log export, alerting, archival to external storage.

---

## 11. Success Metrics (KPIs)

- Parent engagement rate
- Student grade improvement
- Daily active users
- Retention rate
- Teacher adoption rate

---

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

### Phase 1 - Open
- Issue #41: Multi-Google account support for teachers
- Issue #42: Manual course creation for teachers
- Issue #49: Manual assignment creation for teachers
- Issue #57: Auto-send invite email to shadow teachers on creation
- Issue #58: Add is_platform_user flag to Teacher model
- Issue #59: Teacher Dashboard course management view with source badges
- Issue #61: Content privacy controls and version history for uploads
- Issue #62: teacher_google_accounts table for multi-account OAuth
- Issue #89: Auto-create student account when parent links by email
- Issue #109: AI explanation of assignments
- Issue #110: Add assignment/test to task (link tasks to assignments) — courses, content, and study guides now linkable; assignment linking pending
- ~~Issue #111: Student self-learn: create and manage personal courses~~ ✅
- Issue #112: Task reminders: email notifications with opt-out
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
- Issue #169: Color theme: Clean up hardcoded CSS colors (prerequisite for themes)
- Issue #170: Color theme: Dark mode (ThemeContext, ThemeToggle, dark palette)
- Issue #171: Color theme: Focus mode (muted warm tones for study sessions)

### Phase 1.5 - Calendar Extension, Content, Search & School Integration
- Issue #174: Global search: backend unified search endpoint
- Issue #175: Global search: frontend search component in DashboardLayout
- Issue #96: Student email identity merging (personal + school email)
- Issue #45: Extend calendar to other roles (student, teacher) with role-aware data (parent calendar done in #97)
- Issue #46: Google Calendar push integration for tasks
- Issue #25: Manual Content Upload with OCR (enhanced) — document upload + text extraction done; image OCR pending
- Issue #28: Central Document Repository
- Issue #53: Background periodic Google Classroom sync for teachers
- Issue #113: School & School Board model

### Phase 2
- Issue #26: Performance Analytics Dashboard
- Issue #27: Notes & Project Tracking Tools
- Issue #29: TeachAssist Integration
- Issue #50: Data privacy & user rights (FERPA/PIPEDA compliance)

### Phase 3+
- Issue #30: Tutor Marketplace
- Issue #31: AI Email Communication Agent

### Security & Hardening (Codebase Analysis — Feb 2026)
- Issue #139: Security: Fix authorization gaps in list_students, get_user, list_assignments
- Issue #140: Add rate limiting to auth, AI generation, and file upload endpoints
- Issue #141: Add security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)
- Issue #142: Add input validation and field length limits across all endpoints
- Issue #143: Add password reset flow (Forgot Password)
- Issue #144: Fix N+1 query patterns in task list, child list, and reminder job
- Issue #145: Add CASCADE delete rules to FK relationships
- Issue #146: Add unique constraint on parent_students (parent_id, student_id)
- Issue #147: Add React ErrorBoundary for graceful error handling
- Issue #148: Add global toast notification system for user feedback
- Issue #149: Implement JWT token refresh mechanism
- Issue #150: Add loading skeletons to replace text loading states
- Issue #151: Accessibility audit: aria labels, keyboard nav, skip-to-content
- Issue #152: Mobile responsiveness: calendar, tables, modals, touch support
- Issue #153: Fix FlashcardsPage stale closure bug in keyboard handler
- Issue #154: Add frontend unit tests (vitest)
- Issue #155: Add backend route tests for google, study, messages, notifications, admin, invites
- Issue #156: Add PostgreSQL test environment to CI for cross-DB coverage

### Architecture & DDD Migration
- Issue #127: Split api/client.ts into domain-specific API modules
- Issue #128: Extract backend domain services from route handlers
- Issue #129: Introduce repository pattern for data access
- Issue #130: Split ParentDashboard into sub-components
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

### Security & Hardening
- Issue #63: Require SECRET_KEY and fail fast if missing
- Issue #64: Fix CORS configuration for credentials
- Issue #65: Protect frontend log ingestion endpoints
- Issue #66: Introduce Alembic migrations and remove create_all on startup
- Issue #67: Prevent duplicate APScheduler jobs in multi-worker deployments
- Issue #68: Encrypt Google OAuth tokens at rest
- Issue #69: Revisit JWT storage strategy to reduce XSS risk

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
