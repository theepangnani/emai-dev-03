# ClassBridge (EMAI) - Product Requirements

**Product Name:** ClassBridge
**Author:** Theepan Gnanasabapathy
**Version:** 1.0 (Based on PRD v4)
**Last Updated:** 2026-02-02

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

### 6.3 Parent-Student Registration & Linking (Phase 1)

ClassBridge supports three independent paths for student onboarding. Parent linking is entirely optional — students can use the platform independently.

#### Path 1: Parent-Created Student (via Unified Invite)
- Parent creates a student invite from the Parent Dashboard via `POST /api/invites/` with `invite_type=student`
- System creates an invite record with a secure token and sends an invite email
- Student clicks the invite link and sets their own password via `POST /api/auth/accept-invite`
- On acceptance: User (role=student) + Student record + `parent_students` join entry created automatically
- Student can then log in independently

#### Path 2: Self-Registered Student
- Student creates their own account at `/auth/register` with role=student
- Student links to Google Classroom and manages their own courses
- No parent required — the platform works fully for independent students
- Student can optionally be linked to parent(s) later

#### Path 3: Linked After the Fact
- A parent links to an already-existing student account via email or Google Classroom discovery
- Multiple parents can link to the same student (e.g., mother, father, guardian)
- Creates entries in the `parent_students` join table with a `relationship_type`

#### Data Model
- **Many-to-many**: `parent_students` join table (parent_id, student_id, relationship_type, created_at)
- A student can have zero, one, or many parents
- A parent can have zero, one, or many students
- `relationship_type`: "mother", "father", "guardian", "other"

### Unified Invite System
Both student invites (from parent registration) and teacher invites (from shadow discovery) use a single `invites` table and endpoint:
- `invites` table: id, email, invite_type (student, teacher), token, expires_at, invited_by_user_id, metadata (JSON), accepted_at, created_at
- Single endpoint: `POST /api/auth/accept-invite` — resolves invite_type to create the appropriate User + role records
- Invite tokens expire after 7 days (students) or 30 days (teachers)

### 6.3.1 Student-Teacher Linking (Phase 1) - IMPLEMENTED

Students link to teachers through **course enrollment**. This creates the relationship needed for parent-teacher messaging.

#### How Student-Teacher Links Work:
1. **Via Google Classroom** (automatic): Student syncs Google Classroom → courses import with teacher info → student auto-enrolled
2. **Via Manual Enrollment** (without Google): Teacher creates course → student enrolls via `POST /api/courses/{id}/enroll`

#### Relationship Model:
```
Parent ←→ Student (via parent_students join table)
Student ←→ Course (via student_courses join table)
Course ←→ Teacher (via course.teacher_id)
Parent ←→ Teacher (inferred: parent's child enrolled in teacher's course)
```

#### Manual Flow (No Google OAuth):
1. Teacher registers and creates a course
2. Student registers and browses available courses (`GET /api/courses/`)
3. Student enrolls in course (`POST /api/courses/{id}/enroll`)
4. Parent links to student (via email or invite)
5. Parent can now message the teacher (verified through shared course enrollment)

### 6.4 Manual Course Content Upload (Phase 1)
- Upload or enter course content manually
- Supported inputs: PDF, Word, text notes, images (OCR)
- Tag content to specific class or subject
- AI generates study materials from user-provided content
- Content privacy controls
- Version history

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

### 6.13 Task Manager & Calendar (Phase 1.5)

A personal task/todo manager and visual calendar available to all EMAI users. Provides a unified view of what's due, with role-aware data sources and Google Calendar integration.

#### Task/Todo Manager
- Create, edit, complete, and delete personal tasks
- Task fields: title, description, due date, reminder time, priority (low, medium, high), category
- Quick-add from any dashboard
- Filter by status (pending, completed), priority, date range
- Tasks can optionally be linked to an assignment (for students)

#### Visual Calendar (Outlook-style)
- Day, week, and month views
- Color-coded items by type (assignments, tasks, reminders)
- Click to view/edit items
- Drag-and-drop to reschedule tasks

#### Role-Aware Calendar Data Sources
| Role | Calendar Shows |
|------|---------------|
| **Student** | Assignment due dates + personal tasks/reminders |
| **Parent** | Children's assignment due dates + personal tasks/reminders |
| **Teacher** | Course assignment deadlines + personal tasks/reminders |
| **Admin** | Personal tasks/reminders only |

#### Google Calendar Integration (One-Way Push)
- Push EMAI reminders and deadlines to the user's Google Calendar
- Uses existing Google OAuth connection
- User can toggle which items sync to Google Calendar (per-task or global setting)
- `google_calendar_event_id` stored on tasks for update/delete sync

#### Data Model
- `tasks` table: user_id, title, description, due_date, reminder_at, is_completed, priority, category, linked_assignment_id (nullable), google_calendar_event_id (nullable), created_at, updated_at
- Assignment due dates queried from existing `assignments` table (not duplicated)
- Parent calendar aggregates children's assignments via `parent_students` + `student_courses` + `assignments`

### 6.14 AI Email Communication Agent (Phase 5)
- Compose messages inside ClassBridge
- AI formats and sends email to teacher
- AI-powered reply suggestions
- Searchable email archive

---

## 7. Role-Based Dashboards - IMPLEMENTED

Each user role has a customized dashboard (dispatcher pattern via `Dashboard.tsx`):

| Dashboard | Key Features | Status |
|-----------|--------------|--------|
| **Parent Dashboard** | Register child, link children (by email or via Google Classroom), child progress, assignments, study materials, messages | Implemented |
| **Student Dashboard** | Courses, assignments, study tools, Google Classroom sync, file upload | Implemented |
| **Teacher Dashboard** | Courses teaching, manual course creation, multi-Google account management, messages, teacher communications | Implemented (partial) |
| **Admin Dashboard** | Platform stats, user management table (search, filter, pagination) | Implemented |

> **Note:** Phase 4 adds marketplace features (bookings, availability, profiles) to the existing Teacher Dashboard for teachers with `teacher_type=private_tutor`. No separate "Tutor Dashboard" is needed.

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
- [x] Google Classroom integration
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
- [ ] Multi-Google account support for teachers
- [ ] Manual course creation for teachers
- [ ] Manual assignment creation for teachers
- [ ] Deprecate POST /api/courses/ endpoint
- [ ] Auto-send invite email to shadow teachers on creation
- [ ] Teacher Dashboard course management view with source badges

### Phase 1.5 (Task Manager, Calendar & Content)
- [ ] Task/Todo CRUD API and model
- [ ] Visual calendar component (day/week/month views)
- [ ] Google Calendar push integration
- [ ] Frontend Task Manager UI
- [ ] Central document repository
- [ ] Manual content upload with OCR (enhanced)
- [ ] Background periodic Google Classroom course/assignment sync for teachers

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
| `/api/courses/` | POST | Create course (teacher only, auto-assigns teacher) |
| `/api/courses/teaching` | GET | List courses teaching (teacher only) |
| `/api/courses/enrolled/me` | GET | List courses student is enrolled in (student only) |
| `/api/courses/{id}` | GET | Get course details |
| `/api/courses/{id}/enroll` | POST | Enroll in course (student only) |
| `/api/courses/{id}/enroll` | DELETE | Unenroll from course (student only) |
| `/api/courses/{id}/students` | GET | List enrolled students (teacher only, owns course) |
| `/api/assignments/` | GET | List assignments |
| `/api/study/generate` | POST | Generate study guide |
| `/api/study/quiz/generate` | POST | Generate quiz |
| `/api/study/flashcards/generate` | POST | Generate flashcards |
| `/api/study/guides` | GET | List study materials |
| `/api/study/guides/{guide_id}` | GET | Get a specific study guide |
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
| `/api/logs/` | POST | Frontend log ingestion |
| `/api/logs/batch` | POST | Frontend batch log ingestion |

#### Planned Endpoints (Not Yet Implemented)

| Endpoint | Method | Description | Issue |
|----------|--------|-------------|-------|
| `/api/teacher/courses/{id}/students` | POST | Add student to course by teacher | #42 |
| `/api/teacher/courses/{id}/assignments` | POST | Create assignment for a course | #49 |
| `/api/teacher/google-accounts` | GET | List linked Google accounts | #41, #62 |
| `/api/teacher/google-accounts` | POST | Link a new Google account | #41, #62 |
| `/api/teacher/google-accounts/{id}` | DELETE | Unlink a Google account | #41, #62 |
| `/api/tasks/` | GET/POST | Task CRUD (Phase 1.5) | #44 |
| `/api/tasks/{id}` | PUT/DELETE | Update/delete task | #44 |
| `/api/tasks/{id}/complete` | POST | Mark task completed | #44 |
| `/api/calendar/events` | GET | Calendar events (role-aware) | #45 |
| `/api/calendar/google-sync` | POST | Push to Google Calendar | #46 |

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
- **Audit Logging**: Log access to sensitive data (parent viewing child data, admin viewing user list) for compliance auditing.

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
- Issue #52: ~~Teacher Google Classroom course sync (set teacher_id on synced courses)~~ (CLOSED)
- Issue #56: ~~Parent-student-Google sync flow (onboarding, parent sync, teacher info)~~ (CLOSED)

### Phase 1 - Open
- Issue #41: Multi-Google account support for teachers
- Issue #42: Manual course creation for teachers
- Issue #49: Manual assignment creation for teachers
- Issue #51: Deprecate POST /api/courses/ endpoint
- Issue #57: Auto-send invite email to shadow teachers on creation
- Issue #58: Add is_platform_user flag to Teacher model
- Issue #59: Teacher Dashboard course management view with source badges
- Issue #60: Parent registers child directly (name, email, grade, school)
- Issue #61: Content privacy controls and version history for uploads
- Issue #62: teacher_google_accounts table for multi-account OAuth
- Issue #82: Study guide model: add version, parent_guide_id, content_hash
- Issue #83: Role-based study guide limits
- Issue #84: Study guide duplicate detection endpoint
- Issue #85: Study guide versioning
- Issue #86: Role-based study guide visibility
- Issue #87: Frontend study guide management UI
- Issue #88: Update REQUIREMENTS.md with study guide management

### Phase 1.5 - Task Manager, Calendar & Content
- Issue #44: Task/Todo CRUD API and model
- Issue #45: Visual calendar component with role-aware data
- Issue #46: Google Calendar push integration for tasks
- Issue #47: Frontend Task Manager UI
- Issue #25: Manual Content Upload with OCR (enhanced)
- Issue #28: Central Document Repository
- Issue #53: Background periodic Google Classroom sync for teachers

### Phase 2
- Issue #26: Performance Analytics Dashboard
- Issue #27: Notes & Project Tracking Tools
- Issue #29: TeachAssist Integration
- Issue #50: Data privacy & user rights (FERPA/PIPEDA compliance)

### Phase 3+
- Issue #30: Tutor Marketplace
- Issue #31: AI Email Communication Agent

### Infrastructure & DevOps
- Issue #10: Pytest unit tests
- Issue #11: GitHub Actions CI/CD
- Issue #12: PostgreSQL + Alembic migrations
- Issue #13: Deploy to GCP
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
- Issue #71: Add baseline test suite (auth, RBAC, core routes)
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
