# ClassBridge (EMAI) - Product Requirements

**Product Name:** ClassBridge
**Author:** Theepan Gnanasabapathy
**Version:** 1.0 (Based on PRD v4)
**Last Updated:** 2026-02-15

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
- **Configurable Storage Limits**: Maximum 100 study guides per student, 200 per parent. Limits are configurable via application settings (`STUDY_GUIDE_LIMIT_STUDENT`, `STUDY_GUIDE_LIMIT_PARENT`). When the limit is reached, the oldest active (non-archived) guides are **soft-deleted** (archived) rather than permanently deleted, preserving URLs and enabling restore
- **Version Control**: Regenerating a study guide for the same topic/assignment creates a new version linked to the original via `parent_guide_id`, preserving full history. Users can browse all versions of a guide
- **Duplicate Detection**: Before AI generation, the system checks for existing guides with matching content hash to avoid redundant API calls and save costs. Archived guides are excluded from duplicate checks to prevent redirecting users to deleted content. Endpoint: `POST /api/study/check-duplicate`
- **Role-Based Visibility**:
  - **Students** see their own study guides plus any course-labeled guides shared within their enrolled courses
  - **Parents** see their own study guides plus all study guides belonging to their linked children
- **Deletion**: Users can delete their own study guides. Deleting a parent guide does not cascade to child versions
- **Course Assignment**: Any user can assign/reassign their study guides to a course via `PATCH /api/study/guides/{guide_id}`. A reusable `CourseAssignSelect` dropdown component is available on study guide view pages (StudyGuidePage, QuizPage, FlashcardsPage) and inline in dashboard study material lists
- **Ungrouped Guide Categorization**: Study guides without a `course_content_id` appear under "Ungrouped Study Guides" on the Study Guides page. Each ungrouped guide has a folder icon button ("Move to course") that opens a modal with a searchable course list. Users can type to filter courses or create a new course inline ("+Create" option appears when search text doesn't match any existing course). On move, the backend auto-creates a `CourseContent` entry via `ensure_course_and_content()` and assigns the guide, moving it into the grouped section

#### 6.2.2 Course Materials Restructure (Phase 1) - IMPLEMENTED

Restructure the Study Guides page to centre on **course materials** (course content items) rather than listing study guides directly. Each course material is the source document from which AI study tools (study guide, quiz, flashcards) are generated.

**Terminology**: The UI uses "Course Materials" as the parent concept. A Course Material is composed of:
- **Original Document** — the uploaded source file/text (stored as CourseContent)
- **Study Guide** — AI-generated markdown summary (`guide_type = "study_guide"`)
- **Quiz** — AI-generated practice questions (`guide_type = "quiz"`)
- **Flashcards** — AI-generated flashcard pairs (`guide_type = "flashcards"`)

All UI navigation and buttons use "Course Material(s)" terminology. The specific sub-type labels ("Study Guide", "Quiz", "Flashcards") are used only when referring to the individual generated output types (e.g., filter tabs, detail page tabs, generation buttons).

**GitHub Issues:** #194 (rename to Course Material)

**Navigation Flows:**

1. **Courses → Course → Course Materials** (existing, no change)
   - `/courses` — list all courses
   - `/courses/:id` — show course detail with its content items

2. **Course Materials (nav) → Course Materials List → Tabbed Detail**
   - `/course-materials` — lists all course materials across all courses, with filters (redirects from old `/study-guides` URL)
   - `/course-materials/:contentId` — tabbed detail view for a single course material

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

#### 6.2.3 AI Auto-Task Creation from Critical Dates (Phase 1.5)

When AI generates a study guide, quiz, or flashcards, the system extracts critical dates (exam dates, assignment due dates, review deadlines) from the AI response and automatically creates linked tasks.

**Approach: Prompt Enhancement (Zero Additional AI Cost)**
Instead of a secondary AI call, the existing generation prompts are enhanced to include a structured `CRITICAL_DATES` section in the response. This avoids any additional API costs.

**Flow:**
1. User generates a course material (study guide, quiz, or flashcards)
2. The AI generation prompt includes an instruction: "If any dates, deadlines, exams, or due dates are mentioned, include a `--- CRITICAL_DATES ---` section at the end with JSON array"
3. Backend parses the AI response to extract the `CRITICAL_DATES` section (if present)
4. The dates section is stripped from the stored/displayed content
5. For each extracted date, a task is auto-created:
   - **Title**: contextual (e.g., "Review for Biology Chapter 5 Exam", "Complete Algebra Homework")
   - **Due date**: extracted date
   - **Priority**: `high` for exams/tests, `medium` for homework/assignments
   - **Linked to**: the generated study guide + course
   - **Assigned to**: the student (if parent creates for child) or self
6. **Fallback task**: If no critical dates are found in the document, a "Review: {title}" task is created with today's date to ensure the user engages with the material
7. Created tasks are returned in the generation API response (`auto_created_tasks` array)
8. **Date prompt**: Frontend shows a modal after generation with auto-created tasks and date pickers, allowing the user to adjust action dates. If the user clicks "Skip", today's date is kept as the due date

**Date Extraction Format:**
- AI includes at end of response: `--- CRITICAL_DATES ---\n[{"date": "2026-03-15", "title": "Biology Exam", "priority": "high"}]`
- Backend helper `parse_critical_dates(content)` splits content and parses JSON
- If section is missing or malformed, silently skipped (no error to user)
- Handles relative dates via Python dateutil

**API Changes:**
- Generation endpoints (`/api/study/generate`, `/api/study/quiz/generate`, `/api/study/flashcards/generate`) return optional `auto_created_tasks` array in response
- No new endpoints needed — uses existing task creation logic internally

**GitHub Issues:** #195 (AI auto-task creation)

### 6.3 Parent-Student Registration & Linking (Phase 1)

ClassBridge is designed as a **parent-first platform**. Parents can manage their children's education without requiring school board integration or Google Classroom access. Student email is **optional** — parents can create students with just a name.

> **Note:** Registration no longer requires role selection. Users sign up with name/email/password only and select their role during a post-login onboarding flow. See §6.43 for the simplified registration & onboarding specification (#412, #413, #414).

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
- Supported inputs: PDF, Word, PPTX, text notes - IMPLEMENTED (images/OCR for embedded images in .docx: #523 ✅)
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
- **Course Materials section** — Heading reads "Course Materials". Full CRUD (add, edit, delete) for content items (creator/admin only). Parents and other read-only viewers see materials listed without management buttons
- **Upload Document** — Drag-and-drop or file picker, extracts text via `/api/study/upload/extract-text`, stores as course content with `text_content` field
- **Optional study material generation** — Checkbox + dropdown (study guide, quiz, or flashcards) when uploading a document
- **Generate Study Guide** — Button on each content item to generate study guide from its `text_content` or `description`
- **Navigation** — Course cards expand inline to show a materials preview panel; a "View Details" button navigates to the full detail page
- **Role-aware UI** — All roles can view course materials; management buttons (Add Content, Upload Document, Create Task, Edit Course) only visible to course creator/admin

### 6.5 Performance Analytics (Phase 2) - IMPLEMENTED

Grade tracking and analytics dashboard for parents and students. Provides performance summaries, subject-level insights, grade trends over time, AI-powered recommendations, and weekly progress reports.

**Data Model:**
- `grade_records` — Analytics source of truth: student_id, course_id, assignment_id (nullable for course-level grades), grade, max_grade, percentage (pre-computed), source (google_classroom/manual/seed), recorded_at. Indexed on (student_id, course_id) and (student_id, recorded_at).
- `StudentAssignment` (existing) — Google Classroom sync target with grade, status, submitted_at; feeds into grade_records via sync service
- `progress_reports` — Cached weekly/monthly reports: student_id, report_type, period_start/end, data (JSON Text for SQLite compat), generated_at. 24h TTL before recomputation.

**Grade Data Pipeline:**
- Google Classroom submissions synced → `StudentAssignment` → `GradeRecord` (with pre-computed percentage)
- `GradeRecord.assignment_id` is nullable to support future course-level grades (midterms, finals, manual entry)
- `source` column tracks origin: `google_classroom`, `manual`, `seed`
- Seed service provides 26 demo grade records across 3 courses with 60-day date spread
- `_upsert_grade_record()` in grade_sync_service handles create-or-update logic

**Analytics Service (app/services/analytics_service.py):**
- `get_graded_assignments()` — paginated grades from GradeRecord with pre-computed percentages
- `compute_summary()` — overall average, per-course averages, completion rate, trend detection
- `compute_trend_points()` — chronological trend data points filtered by date range and optional course
- `determine_trend()` — first-third vs last-third average comparison with 3-point threshold
- `get_or_create_weekly_report()` — cached weekly ProgressReport with 24h TTL
- `generate_ai_insight()` — on-demand AI analysis via OpenAI (gpt-4o-mini)

**API Endpoints (all implemented):**
- `GET /api/analytics/grades?student_id=&course_id=&limit=&offset=` — paginated grade records
- `GET /api/analytics/summary?student_id=` — overall + per-course averages, trend, completion rate
- `GET /api/analytics/trends?student_id=&course_id=&days=90` — chronological trend points
- `POST /api/analytics/ai-insights` (body: student_id, focus_area) — AI-generated recommendations
- `GET /api/analytics/reports/weekly?student_id=` — cached weekly progress report
- `POST /api/analytics/sync-grades?student_id=` — trigger Google Classroom grade sync

**RBAC:** Parents see linked children, students see own data, teachers see their course students, admins see all. Enforced via `_get_student_or_403()` helper.

**Frontend (implemented):**
- `/analytics` page with Recharts: grade trend LineChart, course averages BarChart, summary cards (average, completion, graded count, trend badge)
- Child selector dropdown for parents with multiple children
- AI insights panel with on-demand "Generate AI Insights" button (manages API costs)
- Recent grades table with assignment, course, grade, and due date columns
- Time range filter (30d/60d/90d/All) and course filter for trend chart
- 14 backend tests + 6 frontend tests

**GitHub Issues:** #469 (grade data pipeline — closed), #470 (aggregation service + API — closed), #471 (frontend charts — closed), #472 (AI insights — closed), #473 (weekly reports — closed), #474 (test expansion — open)

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
- Dedicated `/tasks` page for full task management (all roles). Clicking a task row navigates to the Task Detail Page (`/tasks/:id`); title highlights on hover to indicate clickability
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

### 6.15 Theme System & UI Appearance (Phase 1) - IMPLEMENTED

The platform supports three visual themes that users can switch between via a toggle button in the header.

#### Themes

| Theme | Description | Primary Accent | Status |
|-------|-------------|----------------|--------|
| Light (default) | Clean, bright UI | Teal (#49b8c0) | IMPLEMENTED |
| Dark (turbo.ai-inspired) | Deep dark with purple glow | Purple (#8b5cf6) / Cyan (#22d3ee) | IMPLEMENTED |
| Focus | Warm muted tones for study sessions | Sage (#5a9e8f) / Amber (#c47f3b) | IMPLEMENTED |

#### Architecture
- CSS custom properties (50+ variables) in `index.css` with per-theme overrides via `[data-theme]` attribute
- `ThemeContext.tsx` provides `useTheme()` hook with `theme`, `setTheme()`, `cycleTheme()`
- `ThemeToggle` component in header cycles through themes
- OS preference auto-detection via `prefers-color-scheme`
- Persisted to `localStorage` under `classbridge-theme`

#### Variable Categories
- Core palette (ink, surface, border)
- Accent colors (primary, warm, dark variants)
- Semantic colors (success, danger, warning, purple)
- Priority badges (high, medium, low)
- Content type badges (syllabus, labs, readings, resources, assignments)
- Role badges (parent, teacher, admin)
- Brand colors (Google)
- Shadows, radii, overlays, gradients

#### 6.15.1 Logo & Branding Assets (Phase 1.5)

The platform uses ClassBridge logo files in multiple locations with theme-aware rendering via transparent backgrounds.

**Logo Types:**

| Logo Type | File | Usage | Dimensions | Theme Support |
|-----------|------|-------|-----------|---------------|
| Auth Logo | `classbridge-logo.png` | Login, Register, ForgotPassword, ResetPassword, AcceptInvite pages | max-width: 280px (220px mobile) | Transparent BG works for all themes |
| Header Icon | `logo-icon.png` | DashboardLayout header (all dashboards) | height: 80px (margin-cropped) | Transparent BG works for all themes |
| Landing Nav Logo | `classbridge-logo.png` | Landing page navigation bar | height: 100px (margin-cropped) | N/A |
| Landing Hero Logo | `classbridge-hero-logo.png` | Landing page hero section | height: 300px (margin-cropped) | N/A |
| Favicon | `favicon.png`, `favicon-192.png`, `favicon.ico`, `favicon.svg` | Browser tab, PWA icon, bookmarks | 16x16, 32x32, 48x48, 192x192 | N/A |

**Theme Handling:**
- CSS uses `content: url()` to swap images based on `[data-theme]` attribute
- Current implementation swaps between `-logo.png` and `-logo-dark.png` variants
- New logo files have transparent backgrounds, so same file works for all themes (light/dark/focus)

**Implementation Details:**
- Auth logo: `Auth.css:21-30` (`.auth-logo` class with dark mode swap)
- Header icon: `Dashboard.css:25-34` (`.header-logo` class with dark mode swap)
- Favicon: `frontend/index.html:5` (`<link rel="icon">`)

**Asset Optimization:**
- Auth logo (v6.1): 196KB - optimized for clarity and detail
- Header icon (v7.1): 150KB - optimized for web performance
- Multiple favicon formats for cross-browser/device support (PNG, ICO, SVG)
- Transparent backgrounds work for both light and dark themes
- All logo images have built-in transparent padding; CSS uses negative margins to visually crop whitespace and render the graphic larger (#427)

**File Locations:**
- Source: `frontend/public/*.{png,ico,svg}`
- Build output: `frontend/dist/*.{png,ico,svg}` (copied during build)

**Status:** Phase 1.5 — IMPLEMENTED (#308, #309, #427) ✅ (Feb 2026, commits 619e42b, d7bb5ce, cdaf63e–000e526)

### 6.15.2 Flat (Non-Gradient) Default Style (Phase 1)

Replace all gradient UI styling with solid accent colors across web and mobile. This is a direct response to user feedback that the gradient style (teal-to-orange diagonal gradients on buttons, tabs, backgrounds) feels too flashy and distracting.

**GitHub Issues:** #486 (parent), #487 (web CSS), #488 (mobile), #489 (gradient toggle)

#### Design Decision
- **Default style: Flat/Solid** — all buttons, tabs, backgrounds, and text accents use solid `var(--color-accent)` instead of `linear-gradient()`
- **Gradient available as opt-in** — users who prefer the old gradient look can re-enable via a style toggle (low priority, #489)
- **Mobile: Flat only** — no gradient style option on mobile

#### Scope (30+ gradient instances across 14 files)

**Web Frontend (13 CSS files):**

| File | Elements Affected |
|------|-------------------|
| `index.css` | Body background (radial wash), dot pattern |
| `Auth.css` | Auth page background, login/register button |
| `Dashboard.css` | Logo text, messages button, active sidebar link, generate/create buttons |
| `MessagesPage.css` | Page title text, new message button, sent message bubble, send button |
| `MyKidsPage.css` | Active child tab, mykids button, study count card, link-child buttons |
| `ParentDashboard.css` | Active child tab, study count card, link-child buttons |
| `CoursesPage.css` | Active child tab |
| `FlashcardsPage.css` | Flashcard front/back faces |
| `Calendar.css` | Primary action button in calendar popover |
| `NotificationBell.css` | Notification action button |
| `AdminDashboard.css` | Admin submit button |
| `TeacherCommsPage.css` | AI summary card |
| `AnalyticsPage.css` | AI insights button |

**Mobile App (1 file):**
- `LoginScreen.tsx` — Replace `expo-linear-gradient` button with solid `colors.primary`

#### Flat Style Design Guidelines
- **Buttons**: `background: var(--color-accent)`, `color: white`. Hover: `var(--color-accent-strong)`
- **Active tabs**: `background: var(--color-accent)`, `color: white`
- **Text accents**: `color: var(--color-accent)` (no `background-clip` gradient text)
- **Flashcards**: Front = `var(--color-accent)`, Back = `var(--color-accent-strong)`
- **Subtle backgrounds** (count cards): `var(--color-accent-light)` (rgba variant)
- **Page background**: Flat `var(--color-surface-bg)` — no radial gradient wash
- **Auth background**: Flat `var(--color-surface-bg)` or subtle single-color tint
- **Skeleton loader**: Keep gradient — it's a loading animation, not decorative

#### Optional Gradient Toggle (#489, low priority)
- `[data-style="gradient"]` CSS attribute restores all gradient declarations
- `ThemeContext.tsx` extended with `style: 'flat' | 'gradient'` (default: `'flat'`)
- Persisted to `localStorage` under `classbridge-style`
- Mobile stays flat-only (no toggle)

#### Status: Phase 1 — Not yet implemented

### 6.16 Layout Redesign (turbo.ai-inspired) — PLANNED

A layout overhaul inspired by modern SaaS dashboards (turbo.ai), addressing prototype user feedback.

GitHub Issues: #198, #199, #200

#### Planned Changes
- Persistent collapsible sidebar navigation (replacing hamburger slide-out)
- Glassmorphism card design with gradient borders
- Improved information density and visual hierarchy
- Simplified header (logo + search + notifications + avatar)
- Generous spacing and modern typography
- Mobile: sidebar converts to bottom nav or full-screen overlay

#### Status: Phase 1.5 — Not yet implemented

### 6.17 Global Search (Phase 1.5)

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

### 6.18 Mobile Support (Phase 1.5 + Phase 2+)

ClassBridge must be accessible and usable on all devices — phones, tablets, and desktops.

#### Phase 1.5: Mobile-Responsive Web (Current)
Make the existing web application fully responsive and touch-friendly.

**Status:** IN PROGRESS — 15 of 20 CSS files already have `@media` breakpoints (primary: `max-width: 600px`). Five files need breakpoints added: Auth.css, QuizPage.css, NotificationBell.css, TeacherDashboard.css, App.css.

**Requirements:**
- [ ] All pages render correctly at 320px–1440px viewport widths
- [ ] Collapsible sidebar navigation on mobile (hamburger menu)
- [ ] Full-screen modals on small screens
- [ ] Minimum 44px touch targets on all interactive elements
- [ ] Horizontal scroll for wide tables (admin user list, etc.)
- [ ] Touch-friendly calendar interactions (tap instead of drag-drop)
- [ ] Swipe gestures for flashcards
- [ ] No horizontal page overflow at any screen size
- [ ] Viewport meta tag configured correctly

**Implementation Notes:**
- Use existing CSS custom properties and `max-width: 600px` breakpoint pattern
- CSS-only solutions preferred over JavaScript for responsiveness
- Test with Chrome DevTools device emulation (iPhone SE, iPad, Galaxy S21)

**GitHub Issues:** #152 (mobile responsive web)

#### Phase 2+: Native Mobile Apps (Future)
Dedicated Android and iOS applications for enhanced mobile experience.

**Recommended Approach:** PWA first (Phase 2), then React Native (Phase 3) if needed.

**Future capabilities:**
- Native push notifications
- Offline access to study guides and flashcards
- Camera integration for scanning assignments/documents
- App store presence for discoverability
- Home screen install via PWA

**GitHub Issues:** #192 (native mobile apps)

### 6.19 AI Email Communication Agent (Phase 5)
- Compose messages inside ClassBridge
- AI formats and sends email to teacher
- AI-powered reply suggestions
- Searchable email archive

### 6.20 UI Polish & Resilience (Phase 1) - IMPLEMENTED

Frontend UX improvements for reliability, feedback, and loading experience.

**GitHub Issues:** #147 (ErrorBoundary), #148 (Toast), #150 (Skeletons)

#### Toast Notification System
- Global `ToastProvider` wraps the app in `App.tsx`
- `useToast()` hook returns `toast(message, type)` for any component
- Three types: `success` (green check), `error` (red x), `info` (blue i)
- Auto-dismiss: 3s for success/info, 5s for errors
- Click to dismiss, max 5 visible, animated entrance
- Mobile responsive (full-width at 480px)

#### React ErrorBoundary
- Class component wraps all routes in `App.tsx`
- Catches unhandled render errors gracefully
- Shows "Something went wrong" card with Try Again / Reload Page buttons
- In dev mode, displays error message for debugging

#### Loading Skeletons
- Reusable `Skeleton`, `PageSkeleton`, `CardSkeleton`, `ListSkeleton`, `DetailSkeleton` components
- Uses CSS shimmer animation (global `.skeleton` class in `index.css`)
- Replaces "Loading..." text across 16 pages: CoursesPage, TeacherDashboard, CourseDetailPage, AdminDashboard, StudyGuidesPage, CourseMaterialDetailPage, TaskDetailPage, ParentDashboard, TeacherCommsPage, AdminAuditLog, TasksPage, StudentDashboard, MessagesPage (conversation selection), QuizPage, FlashcardsPage, MyKidsPage

#### Task Due Date Filters
- Tasks page (`/tasks`) supports `?due=overdue|today|week` URL parameter
- New "Due" filter dropdown: All, Overdue, Due Today, This Week
- Parent Dashboard status cards (Overdue, Due Today) now navigate to `/tasks?due=overdue` and `/tasks?due=today`
- Dashboard overdue/due-today counts computed client-side from task data using local timezone (matches TasksPage filter logic exactly — fixes count mismatch caused by mixing assignment counts and UTC vs local time)
- Dashboard overdue/due-today counts adjust when a specific child is selected
- Filter state syncs with URL for shareable/bookmarkable links

#### Assignee Filter
- Tasks page has an "Assignee" dropdown filter populated from assignable users
- Parents can filter tasks to see only a specific child's tasks
- Filter works client-side alongside existing status, priority, and due filters

### 6.21 Collapsible Calendar (Phase 1) - IMPLEMENTED

Allow parents to collapse/expand the calendar section on the Parent Dashboard for more control over their view.

**GitHub Issue:** #207

**Implementation:**
- Calendar section has a collapse/expand toggle button (chevron icon)
- When collapsed, shows a compact bar with item count and expand button
- When expanded, shows the full calendar (default state)
- Collapse state persists via localStorage across sessions
- Calendar defaults to **expanded** on all screen sizes

### 6.22 Parent UX Simplification (Phase 1.5) — IMPLEMENTED

Simplify the parent experience based on prototype user feedback. The core problem: ClassBridge is organized by feature (Courses, Materials, Tasks) rather than by parent workflow ("What's going on with my kid?").

GitHub Issues: #201, #202, #203, #204, #205, #206

#### 6.22.1 Single Dashboard API Endpoint (#201)
Replace 5+ waterfall API calls with one `GET /api/parent/dashboard` that returns children, overdue counts, due-today items, unread messages, and per-child highlights.

**Status:** IMPLEMENTED ✅

#### 6.22.2 Status-First Dashboard (#202)
Replace calendar-dominated dashboard with status summary cards (overdue count, due today, unread messages) and per-child status cards above the calendar.

**Status:** IMPLEMENTED ✅

#### 6.22.3 One-Click Study Generation (#203)
Smart "Study" button that checks for existing material, generates with defaults if needed, and navigates directly — no modal required for the common case.

**Status:** IMPLEMENTED ✅

#### 6.22.4 Filter Cascade Fix (#204)
Fix course materials page filter behavior: reset course filter when child changes, scope course dropdown to selected child, show result counts.

**Status:** IMPLEMENTED ✅

#### 6.22.5 Modal Nesting Reduction (#205)
Eliminate modal-in-modal patterns. Study generation from day detail should navigate to a page instead of stacking modals.

**Status:** IMPLEMENTED ✅

#### 6.22.6 Simplified Parent Navigation (#206)
Consolidate parent nav from 5 items to 3: Home (status + calendar), My Kids (merged course/task/material view per child), Messages.

**Status:** PLANNED (Phase 2 — deferred)

### 6.23 Security Hardening (Phase 1) - IMPLEMENTED

Critical security vulnerabilities identified in the Feb 2026 risk audit and fixed:

#### 6.23.1 JWT Secret Key (#179)
- Removed hardcoded default `SECRET_KEY`; application crashes on startup in production if not set or uses a known weak value
- Development mode auto-generates a random 64-char key per process
- Production requires explicit `SECRET_KEY` via environment variable (stored in Google Secret Manager)

#### 6.23.2 Admin Self-Registration & Password Validation (#176)
- Blocked admin role from the public registration endpoint (only parent, student, teacher allowed)
- Added password strength validation: minimum 8 characters, must include uppercase, lowercase, digit, and special character
- Validation applied to both registration and invite acceptance flows

#### 6.23.3 CORS Hardening (#177)
- Replaced `allow_origins=["*"]` with explicit origin allowlist
- Development: `localhost:5173`, `localhost:8000`, configured `frontend_url`
- Production: only the configured `frontend_url` (Cloud Run service URL)
- Restricted allowed methods (GET, POST, PUT, PATCH, DELETE, OPTIONS) and headers (Authorization, Content-Type)

#### 6.23.4 Google OAuth Security (#178)
- Added cryptographic state parameter (CSRF protection) using `secrets.token_urlsafe(32)` with 10-minute TTL
- State tokens are consumed on callback (single-use)
- Removed Google access/refresh tokens from redirect URL parameters
- Google tokens stored server-side in temporary store during registration flow, resolved on user creation
- Error messages no longer leak internal exception details to the frontend

#### 6.23.5 RBAC Authorization Gaps (#181, #139)
- **Students route**: `list_students` restricted to ADMIN/TEACHER; teachers see only students in their courses; `get_student` scoped to admin/own/parent-child/teacher-course; `create_student` restricted to admin
- **Users route**: `get_user` restricted to own profile, admin, parent (linked children), teacher (course students)
- **Assignments route**: added `can_access_course()` checks on all CRUD; `create_assignment` restricted to course owner/teacher/admin; `list_assignments` scoped to accessible courses
- **Courses route**: `get_course` checks course access (enrollment/ownership/admin); `list_course_students` allows admin in addition to teacher
- **Course contents route**: `create`, `get`, and `list` (with course_id) verify course enrollment; update/delete allow admin in addition to creator
- **Study routes**: generation endpoints (study guide, quiz, flashcards) verify assignment course access before generating content
- Shared `can_access_course()` helper in `deps.py` checks admin/owner/public/teacher/enrolled/parent-child-enrolled

#### 6.23.6 Logging & Student Password Security (#182)
- Logging endpoint (`/api/logs/`) now requires authentication (Bearer token)
- Added input validation: max message length (2000 chars), max batch size (50 entries), valid level enum
- Frontend logger already sends auth token via Axios interceptor; unauthenticated errors silently skip server logging
- Parent-created student accounts use `UNUSABLE_PASSWORD_HASH` sentinel (`!INVITE_PENDING`) instead of empty string
- `verify_password()` explicitly rejects empty and sentinel hashes — no login possible without setting a real password via invite link

### 6.24 Multi-Role Support (Phase 1) - PARTIAL

Users can hold multiple roles simultaneously (e.g., a parent who is also a teacher, or an admin who is also a parent and student). The system uses an "Active Role" pattern where `role` is the current dashboard context and `roles` stores all held roles as a comma-separated string.

#### Phase A — IMPLEMENTED (#211)
- [x] **Backend: `roles` column** — `String(50)` comma-separated on User model with `has_role()`, `get_roles_list()`, `set_roles()` helpers
- [x] **Backend: Authorization** — `require_role()` and `can_access_course()` check ALL roles, not just active role
- [x] **Backend: Inline auth checks** — Updated 12 permission gates across 6 route files to use `has_role()`
- [x] **Backend: Registration** — New users get `roles` set to their registration role
- [x] **Backend: DB migration** — Auto-adds `roles` column and backfills from existing `role` at startup
- [x] **Backend: Switch-role endpoint** — `POST /api/users/me/switch-role` to change active dashboard
- [x] **Backend: UserResponse** — Includes `roles: list[str]` with field_validator for ORM compatibility
- [x] **Frontend: AuthContext** — `roles: string[]` on User, `switchRole()` function
- [x] **Frontend: ProtectedRoute** — Checks all roles for route access, not just active role
- [x] **Frontend: Role switcher** — Dropdown in DashboardLayout header (visible only with 2+ roles)

#### Phase B — IN PROGRESS
- [ ] **Admin role management UI** (#255) — Admin can add/remove roles for any user from the admin portal, with checkbox modal and auto-creation of profile records
- [x] **Auto-create profile records** (#256) — When adding teacher/student roles, auto-create Teacher/Student records if missing; preserve data on role removal (IMPLEMENTED - Feb 2026, commit 120e065)
- [x] **Multi-role registration** (#257) — Checkbox role selection during signup instead of single dropdown (IMPLEMENTED - Feb 2026, commit 120e065). **Note:** Role selection is being moved from registration to post-login onboarding (§6.43, #412-#414); multi-role selection will be supported in the onboarding flow instead
- [ ] **Admin as multi-role** — Admin users can simultaneously hold parent, teacher, and/or student roles, accessing all corresponding dashboards and features via the role switcher
- [ ] Merged data views (combined parent+teacher data on single dashboard)

### 6.25 Course Materials Lifecycle Management (Phase 1) - IMPLEMENTED

Course materials and study guides use soft-delete (archive) with retention policies, last-viewed tracking, and automatic study guide archival when source content changes.

#### Requirements
1. **Edit/move/archive icons on course materials list** — Each item in the StudyGuidesPage list has pencil (edit ✏️), folder (move to course 📂), and trash (archive 🗑️) action icons. Move opens a course selector modal allowing reassignment to a different course (with search and create-new-course option)
2. **Edit + delete on course materials detail page** — Document tab has "Edit Content" toggle for inline text editing; study guide tabs have "Archive" action
3. **Regeneration prompt after content edit** — When course material `text_content` is modified and linked study guides are archived, a regeneration prompt appears with buttons for Study Guide, Quiz, and Flashcards
4. **Auto-archive linked study guides** — When a course material's `text_content` field changes, all linked non-archived study guides (`StudyGuide.course_content_id == id`) are automatically archived. A toast notification shows: "Content updated. N linked study material(s) archived."
5. **Soft delete (archive)** — DELETE endpoints for both course materials and study guides set `archived_at` timestamp instead of hard-deleting
6. **Archive list with restore and permanent delete** — StudyGuidesPage has "Show Archive" toggle that loads archived course materials and study guides. Each archived item has restore (↺) and permanent delete (🗑) buttons
7. **On-access auto-archive after 1 year** — When a course material is accessed via GET, if `created_at` is more than 1 year ago and not already archived, it is automatically archived
8. **On-access permanent delete after 7 years** — When a course material is accessed via GET, if `last_viewed_at` is more than 7 years ago, the item and linked study guides are permanently deleted
9. **Last-viewed tracking** — `last_viewed_at` is updated on every GET access to a course material
10. **Toast notifications** — Success messages for archive, restore, delete, and content-save operations

#### Technical Implementation
- **Model changes**: `archived_at` column on `course_contents` and `study_guides` tables; `last_viewed_at` column on `course_contents`
- **Schema**: `CourseContentUpdateResponse` extends `CourseContentResponse` with `archived_guides_count: int`
- **Routes**: `PATCH /{id}/restore`, `DELETE /{id}/permanent` for both course contents and study guides; `include_archived` query param on list endpoints
- **Retention checks**: On-access only (no background job) — 1-year auto-archive, 7-year permanent delete
- **Frontend**: Archive toggle section, toast notifications, inline document editing, regeneration prompt on CourseMaterialDetailPage

#### Files Affected
- `app/models/course_content.py`, `app/models/study_guide.py` — new columns
- `app/schemas/course_content.py`, `app/schemas/study.py` — new response fields
- `app/api/routes/course_contents.py` — soft delete, restore, permanent delete, on-access checks
- `app/api/routes/study.py` — soft delete, restore, permanent delete, `include_archived` filter
- `main.py` — DB migration for new columns
- `frontend/src/api/client.ts` — new API methods and types
- `frontend/src/pages/StudyGuidesPage.tsx` — edit/delete icons, archive section
- `frontend/src/pages/CourseMaterialDetailPage.tsx` — document editing, regeneration prompt
- `frontend/src/pages/CourseDetailPage.tsx` — archive wording
- CSS files for archived row styles, toast, and regeneration prompt

---

### 6.26 Password Reset Flow (Phase 1) - IMPLEMENTED

Users can reset forgotten passwords via email-based JWT token flow.

**Endpoints:**
- `POST /api/auth/forgot-password` — accepts email, sends reset link (always returns 200, no user enumeration)
- `POST /api/auth/reset-password` — accepts token + new password, validates strength, updates hash

**Frontend:**
- `/forgot-password` — email form with success confirmation
- `/reset-password?token=...` — new password form with confirmation
- "Forgot password?" link on login page

**Security:**
- JWT reset tokens with 1-hour expiry and `type: "password_reset"`
- Rate limited: 3/min for forgot-password, 5/min for reset-password
- Password strength validation (8+ chars, upper, lower, digit, special)
- Audit logging for reset requests and completions

**Key files:**
- `app/core/security.py` — `create_password_reset_token()`, `decode_password_reset_token()`
- `app/api/routes/auth.py` — forgot-password, reset-password endpoints
- `app/templates/password_reset.html` — email template
- `frontend/src/pages/ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`

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
3. **Parent navigation simplification** (#237) - IMPLEMENTED
   - Remove Courses from parent nav (parents access courses via My Kids → child → Courses section)
   - Parent nav: Home | My Kids | Tasks | Messages

**Sub-tasks:**
- [x] Backend: Add course_count, active_task_count to ChildSummary (#236)
- [x] Frontend: Child card stats display (#236)
- [x] Frontend: Section header icons (#237)
- [x] Frontend: Remove Courses from parent nav (#237)

### 6.31b My Kids Visual Overhaul (Phase 2) - IMPLEMENTED

Visual redesign of the My Kids section on the parent dashboard for improved clarity and usability (#301).

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
4. **Responsive** - Cards single-column on tablet, action buttons horizontal on mobile
5. **Theme compatible** - Works across light, dark, and focus themes

**Sub-tasks:**
- [x] Add CHILD_COLORS palette and getInitials helper
- [x] Add childTaskStats useMemo (completion %, next deadline per child)
- [x] Replace child tabs (color dot, remove edit button)
- [x] Replace child cards with enhanced layout (avatar, progress, deadline, actions)
- [x] CSS: new card styles, responsive breakpoints

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
- [ ] Backend: Add inspiration message injection to email service (#260)
- [ ] Templates: Update all 8+ email templates with inspiration footer (#260)

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

## 7. Role-Based Dashboards - IMPLEMENTED

Each user role has a customized dashboard (dispatcher pattern via `Dashboard.tsx`):

| Dashboard | Key Features | Status |
|-----------|--------------|--------|
| **Parent Dashboard** | Left nav (Courses, Study Guides, Messages), calendar-centric main area (Day/3-Day/Week/Month views), child filter tabs with edit child modal, day detail modal (CRUD tasks/assignments), task management with reminders, course color-coding | Implemented (v2 in progress) |
| **Student Dashboard** | Courses, assignments, study tools, Google Classroom sync, file upload | Implemented |
| **Teacher Dashboard** | Courses teaching, manual course creation, multi-Google account management, messages, teacher communications | Implemented (partial) |
| **Admin Dashboard** | Platform stats, user management table (search, filter, pagination), role management, broadcast messaging, individual user messaging | Implemented (messaging planned) |

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
- **Home** — Dashboard view (calendar)
- **My Kids** — Per-child view with courses, materials, tasks, teachers
- **Tasks** — Dedicated task management view
- **Messages** — Opens messaging view
- **+ Add Child** — Opens Add Child modal
- **+ Add Course** — Opens Create Course modal
- **+ Create Study Guide** — Opens Study Tools modal
- **+ Add Task** — Opens Add Task modal

> **Note:** Courses was removed from parent nav (#237) since parents access courses through My Kids → child → Courses section.

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
- **Click course card** → expands inline to show course materials preview panel (content items with type badges, titles, links)
- **Expanded panel** includes "View Details →" button to navigate to full Course Detail Page (`/courses/:id`)
- **Child selector tabs** — styled pill buttons with active gradient for parents with multiple children
- **Create new course** — name, subject, description (all roles)
- **Assign to children** — parent only, supports assigning one course to multiple children
- **Course Detail Page** — edit course, CRUD content, upload documents, generate study materials (see §6.4.2)
- Course cards show: name, subject, teacher name, Google badge, expand/collapse arrow
- **Hover action icons on all course cards** — Edit (✏️) button appears on hover for all course tiles (parent child courses, student enrolled, and My Created Courses); navigates to Course Detail Page. Parent child courses also show unassign (✕); My Created Courses also show assign (✓) when a child is selected

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
- [ ] Issue #206: Parent UX: Consolidated 3-item navigation (Phase 2 — deferred)
- [ ] Issue #207: Parent Dashboard: Collapsible/expandable calendar section

### Phase 2
- [ ] TeachAssist integration
- [x] **Performance Analytics Dashboard** — Grade tracking, trends, AI insights, weekly reports (#469-#474) — IMPLEMENTED
- [ ] Advanced notifications
- [ ] Notes & project tracking tools
- [ ] Data privacy & user rights (account deletion, data export, consent)
- [ ] **FAQ / Knowledge Base** — Community-driven Q&A with admin approval (#437-#444)
- [ ] **Admin email template management** — View, edit, preview, and reset email templates from Admin Dashboard (#513)
- [ ] **Broadcast history reuse & resend** — View full broadcast details, reuse as template, resend to all users (#514)

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

### Phase 3 (Course Planning & Guidance)
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

## 9. Mobile App Development

> **Status:** Parent-only MVP complete (8 screens). Device testing pending for March 6 pilot.

---

### 9.1 Overview

**Technology Stack:** React Native + TypeScript with Expo (managed workflow)

**Platforms:** iOS 13+ and Android 8.0+

**Approach:** Parent-only "monitor & communicate" mobile app for the March 6, 2026 pilot. All complex workflows (registration, course management, study material generation, teacher linking) remain web-only. Mobile is read-heavy with limited write actions (reply to messages, mark tasks complete, mark notifications read).

**Key Design Decision:** No backend API changes needed for the mobile MVP. The existing `/api/*` endpoints return all data the mobile app needs. The mobile API client calls the same endpoints as the web frontend.

**GitHub Issues:** #364-#380 (pilot MVP + post-pilot enhancements)

### 9.2 Strategic Decision: React Native with Expo

**Selected Approach:** React Native with Expo SDK 54 (managed workflow)

**Rationale:**
1. **Maximum Code Reuse**: Web app already uses React — shared API types, business logic, patterns
2. **Single Team**: Same tooling (npm, TypeScript, VSCode), hot reload like web
3. **Fast Development**: 8 screens built in under a week using web API types as reference
4. **Expo Go Distribution**: No App Store submission needed for pilot — parents install Expo Go and scan QR code
5. **Native Performance**: Sufficient for educational platform (not gaming/AR)

### 9.3 Mobile Stack (Actual)

**Core:**
- React Native 0.81.5
- TypeScript 5.x
- Expo SDK 54

**Navigation:**
- React Navigation 7 (native stack + bottom tabs)

**State & Data Management (shared patterns with web):**
- TanStack React Query 5.x (same query keys and patterns as web)
- Axios (same interceptor pattern as web)
- AsyncStorage (localStorage equivalent for token storage)

**UI:**
- @expo/vector-icons (MaterialIcons)
- react-native-safe-area-context
- Custom theme system matching ClassBridge brand colors

**Deferred (Phase 3+):**
- React Native Firebase (push notifications)
- Expo Image Picker / Document Picker (file uploads)
- React Native MMKV (offline cache persistence)

### 9.4 Backend API Changes

**Key Decision: No backend changes needed for the March 6 pilot.** The existing `/api/*` endpoints return all data the mobile app needs. CORS is not a factor for React Native (native HTTP clients bypass browser CORS restrictions). The mobile API client calls the exact same endpoints as the web frontend.

**Deferred backend API work** (to be implemented post-pilot as needed):
- Issue #311: API Versioning (`/api/v1`) — Not needed when you control both clients
- Issue #312: Pagination on all list endpoints — Not needed for pilot scale
- Issue #313: Structured error responses — Nice-to-have for Phase 3
- Issues #314-#318: Firebase push notifications — Deferred to Phase 3 (late March)
- Issues #319-#320: File upload endpoints — Not needed for read-only parent mobile
- Issue #321: Health endpoint with version info — Deferred
- Issue #322: Integration tests for v1 API — Deferred (no v1 API yet)

### 9.5 Mobile App — What Was Built (Pilot MVP)

**Project:** `ClassBridgeMobile/` — Expo SDK 54 managed workflow

#### 9.5.1 Foundation (Issues #364-#366) ✅ COMPLETE

**API Client (#364)** — Ported from `frontend/src/api/client.ts`
- `src/api/client.ts` — Axios instance with AsyncStorage token management
- Token refresh interceptor (same logic as web, using AsyncStorage instead of localStorage)
- Form-urlencoded login (backend uses `OAuth2PasswordRequestForm`)
- `src/api/parent.ts` — ParentDashboardData, ChildHighlight, ChildOverview types
- `src/api/messages.ts` — ConversationSummary, ConversationDetail, MessageResponse types
- `src/api/notifications.ts` — NotificationResponse type + list/read/count functions
- `src/api/tasks.ts` — TaskItem type + list/toggleComplete functions

**Auth & Login (#365)**
- `src/context/AuthContext.tsx` — Token in AsyncStorage, auto-load user on app start, login/logout
- `src/screens/auth/LoginScreen.tsx` — Email/password form, validation, error display

**Navigation (#366)**
- `src/navigation/AppNavigator.tsx` — Auth-gated navigation:
  - Not authenticated → LoginScreen
  - Authenticated → Bottom tab navigator (Home, Calendar, Messages, Notifications, Profile)
  - HomeStack: Dashboard → ChildOverview (nested stack)
  - MsgStack: ConversationsList → Chat (nested stack)

#### 9.5.2 Core Screens (Issues #367-#373) ✅ COMPLETE

| Screen | Issue | API Endpoint | Key Features |
|--------|-------|-------------|--------------|
| ParentDashboardScreen | #367 | `GET /api/parent/dashboard` | Greeting, 3 status cards (overdue/due today/messages), child cards with avatars and status badges |
| ChildOverviewScreen | #368 | `GET /api/parent/children/{id}/overview` + `GET /api/tasks/` | Courses list, assignments sorted by due date, tasks with complete toggle |
| CalendarScreen | #369 | Dashboard `all_assignments` + tasks API | Custom month grid, color-coded date dots, tap date → day items list |
| MessagesListScreen | #370 | `GET /api/messages/conversations` | Conversation cards, unread badges, time formatting, tap → Chat |
| ChatScreen | #371 | `GET /api/messages/conversations/{id}` + `POST .../messages` | Chat bubbles (sent/received), date separators, send message, auto-mark-read |
| NotificationsScreen | #372 | `GET /api/notifications/` | Type-specific icons, mark as read, mark all read, relative timestamps |
| ProfileScreen | #373 | `GET /api/auth/me` | User info, unread counts, Google status, logout, web app reminder |

#### 9.5.3 UI Polish (#374) ✅ COMPLETE

- SafeArea handling via `useSafeAreaInsets` on headerless screens
- Native headers on Calendar, Notifications, Profile tabs
- Tab bar badges with 30-second polling (Messages: unread count, Notifications: unread count)
- Pull-to-refresh (`RefreshControl`) on all list/scroll screens
- Empty states with icons and messages
- Loading spinners with messages

#### 9.5.4 Remaining Pilot Work

- [x] **Device testing prep (#375):** ESLint 9 flat config migration, unused import cleanup, dependency compatibility fix (`react-native-screens`), `useMemo` dependency fix in ChatScreen — TypeScript and ESLint pass clean, Metro Bundler starts successfully
- [ ] **Device testing (#375):** Test on physical iOS device via Expo Go, test on physical Android device
- [x] **Pilot onboarding docs (#362):** Welcome email template (`docs/pilot/welcome-email.md`), quick-start guide with Expo Go instructions, known limitations, and feedback mechanism (`docs/pilot/quick-start-guide.md`)
- [ ] **Pilot launch checklist (#376):** Verify mobile connects to production API, prepare Expo Go instructions

#### 9.5.5 Mobile Unit & Component Testing (#490-#494)

**Framework:** Jest + React Native Testing Library (same pattern as web frontend's 319 tests)

| Screen | Issue | Tests | Status |
|--------|-------|-------|--------|
| Test framework setup (Jest + RNTL config, mocks) | #490 | — | [ ] |
| LoginScreen | #491 | Logo, inputs, validation, auth flow, error states | [ ] |
| ParentDashboardScreen | #492 | Greeting, status cards, child cards, navigation | [ ] |
| ChildOverviewScreen | #492 | Stats, assignments, tasks, completion toggle | [ ] |
| CalendarScreen | #492 | Grid, date selection, month nav, item dots | [ ] |
| MessagesListScreen | #493 | Conversations, unread styling, time formatting | [ ] |
| ChatScreen | #493 | Message bubbles, send flow, date separators | [ ] |
| NotificationsScreen | #494 | Icons, unread styling, mark read, time formatting | [ ] |
| ProfileScreen | #494 | Avatar, stats, Google status, sign out alert | [ ] |
| PlaceholderScreen | #494 | Smoke test | [ ] |

### 9.6 Mobile Boundary (What's Mobile vs Web-Only)

**MOBILE (parent read/reply only):**
- View dashboard: children status cards (overdue, due today, courses)
- View child detail: courses, assignments, upcoming deadlines
- View calendar: assignments & tasks by date (read-only)
- View/reply messages: parent-teacher conversations
- View notifications: mark as read
- Mark tasks complete: single tap toggle
- View profile & logout

**WEB ONLY (complex workflows):**
- Registration & account setup
- Create/link/edit children (invites, Google discovery)
- Create courses, assign to children, Google sync
- Link teachers (invite flow, email notifications)
- Generate study materials (AI, file upload)
- Create tasks with full detail & resource linking
- Teacher email monitoring (Gmail OAuth)
- All admin functions
- All student & teacher functions

### 9.7 Post-Pilot Phases

#### Phase 3: Post-Pilot Enhancement (Mar 7-31)

| Task | Issue | Est. |
|------|-------|------|
| Firebase Admin SDK setup | #314 | 1 day |
| DeviceToken model + endpoints | #315 | 1 day |
| Push notification service | #316 | 1 day |
| Integrate with key events | #317 | 2 days |
| Firebase in mobile app + deep linking | #334-#335 | 2 days |
| Notification polling (30s foreground) | #377 | 1 day |
| React Query offline caching | #378 | 1 day |
| API versioning (/api/v1) | #311 | 2 days |
| Structured error responses | #313 | 1 day |

#### Phase 4: Full Mobile + Scale (April 2026)

| Task | Issue |
|------|-------|
| Student mobile screens (dashboard, assignments, study viewer) | #379 |
| Teacher mobile screens (messages, notifications, quick grade) | #380 |
| Camera/file upload for course content | #333 |
| Profile picture upload | #319 |
| Offline mode with data sync | #337 |
| App Store + Google Play public launch | #343-#346 |
| Pagination on all endpoints | #312 |
| Mobile CI/CD pipeline | #352 |

### 9.8 Project Structure

```
ClassBridgeMobile/
  src/
    api/
      client.ts          # Axios instance + AsyncStorage token management
      parent.ts          # Parent dashboard/children types + functions
      messages.ts        # Conversations, messages types + functions
      notifications.ts   # Notification types + functions
      tasks.ts           # Task types + functions
    context/
      AuthContext.tsx     # Auth state provider (AsyncStorage)
    navigation/
      AppNavigator.tsx    # Root stack + bottom tabs + nested stacks
    screens/
      auth/
        LoginScreen.tsx
      parent/
        ParentDashboardScreen.tsx
        ChildOverviewScreen.tsx
        CalendarScreen.tsx
      messages/
        MessagesListScreen.tsx
        ChatScreen.tsx
      notifications/
        NotificationsScreen.tsx
      profile/
        ProfileScreen.tsx
    components/
      LoadingSpinner.tsx
      EmptyState.tsx
    theme/
      index.ts           # Colors, spacing, fontSize, borderRadius
  __tests__/             # Jest + React Native Testing Library tests
    setup.ts             # Test setup (mocks for navigation, auth, React Query)
    screens/             # Screen-level component tests
  app.json               # Expo configuration
  jest.config.js         # Jest configuration
  package.json
  tsconfig.json
```

### 9.9 Success Criteria (Pilot)

**Pilot MVP (March 6):**
- [x] All 8 screens built and type-checked
- [ ] App loads on physical iOS device via Expo Go
- [ ] App loads on physical Android device via Expo Go
- [ ] Parent can log in and see dashboard with children
- [ ] Parent can tap child → see courses/assignments
- [ ] Parent can read and reply to messages
- [ ] Parent can view and mark notifications as read
- [ ] No crashes during pilot use

**Post-Pilot Targets:**
- Push notifications working for all event types
- Student + teacher mobile screens
- App Store + Google Play submission
- < 1% crash rate, 4.0+ star rating

---

## 10. Technical Architecture

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
| `/api/admin/broadcast` | POST | Send broadcast message + email to all users | #258 |
| `/api/admin/broadcasts` | GET | List past broadcasts with stats | #258 |
| `/api/admin/users/{user_id}/message` | POST | Send individual message + email to a user | #259 |
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
- ~~Issue #207: Parent Dashboard: Calendar default expanded on all screen sizes~~ ✅
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
- ~~Issue #207: Parent Dashboard: Calendar default expanded on all screen sizes~~ ✅

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
