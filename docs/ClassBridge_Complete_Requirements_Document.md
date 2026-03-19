# ClassBridge - Complete Product Requirements Document

**Product Name:** ClassBridge (EMAI)
**Author:** Sarah (Product Owner) / Theepan Gnanasabapathy
**Version:** 2.2
**Date:** 2026-03-18
**Quality Score:** 95/100

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Vision & Mission](#2-vision--mission)
3. [Problem Statement](#3-problem-statement)
4. [Goals & Objectives](#4-goals--objectives)
5. [User Roles & Personas](#5-user-roles--personas)
6. [System Architecture](#6-system-architecture)
7. [Core Features](#7-core-features)
8. [Role Workflows](#8-role-workflows)
   - 8.1 [Parent Workflow](#81-parent-workflow)
   - 8.2 [Student Workflow](#82-student-workflow)
   - 8.3 [Teacher Workflow](#83-teacher-workflow)
   - 8.4 [Admin Workflow](#84-admin-workflow)
9. [Role-Based Dashboards](#9-role-based-dashboards)
10. [Non-Functional Requirements](#10-non-functional-requirements)
11. [Phased Roadmap](#11-phased-roadmap)
12. [Success Metrics](#12-success-metrics)
13. [Risk Assessment](#13-risk-assessment)
14. [Appendix](#14-appendix)

---

## 1. Executive Summary

ClassBridge is a unified, AI-powered education management platform that connects parents, students, teachers, and administrators in one role-based application. It integrates with Google Classroom, provides AI-driven study tools (study guides, quizzes, flashcards), simplifies parent-teacher communication, and enables parents to actively support their children's education.

The platform is designed as a **parent-first** system, meaning parents can manage their children's education independently without requiring school board integration or Google Classroom access. Student email is optional, and the platform works fully for independent users.

ClassBridge addresses the fragmentation in education ecosystems where parents struggle to track academic progress, students lack structured study tools, teachers rely on disconnected communication channels, and affordable tutoring is difficult to manage.

**Current Status (Feb 27, 2026):** 725 GitHub issues tracked — 538 closed (74%), 187 open. Phase 1 (MVP) substantially complete with 305+ backend tests and 258+ frontend tests passing. 137 bugs fixed, 183 features built. Mobile MVP (Expo SDK 54) complete with 8 parent screens. Performance analytics, quiz results history, FAQ/Knowledge Base, comprehensive UI/UX audit (HCD Tier 1 complete), WCAG 2.1 AA accessibility, and print/PDF export all deployed. VASP/DTAP compliance planning underway for Ontario school board approval.

---

## 2. Vision & Mission

### Vision
To become the trusted digital bridge between families and schools, empowering every student to succeed with the right support at the right time.

### Mission
ClassBridge empowers parents to actively participate in their children's education by providing intelligent tools, clear insights, and affordable access to trusted educators - all in one connected platform.

---

## 3. Problem Statement

Education ecosystems are fragmented:

| Problem | Impact |
|---------|--------|
| Parents struggle to track academic progress across multiple systems (Google Classroom, TeachAssist, etc.) | Reduced parental involvement in education |
| Students lack structured organization and effective study tools | Poor study habits and academic outcomes |
| Teachers rely on disconnected communication channels | Communication gaps between home and school |
| Affordable tutoring is difficult to discover and manage | Inequitable access to academic support |

**Proposed Solution:** A single, role-based platform that consolidates academic tracking, AI-powered study tools, communication, and (in future phases) tutoring marketplace into one unified experience.

---

## 4. Goals & Objectives

### Product Goals
- Provide a single role-based application for parents, students, teachers, and administrators
- Enable parents to support learning at home with AI-powered tools
- Improve student academic outcomes through AI insights and structured study materials
- Simplify teacher-parent communication with in-app messaging and email notifications

### Business Goals
- Build a scalable SaaS platform on Google Cloud Platform
- Partner with Ontario school boards (starting with TDSB, PDSB, YRDSB, HDSB, OCDSB)
- Establish recurring revenue through subscriptions and future marketplace services
- Achieve 100k+ user capacity with 99.9% uptime

---

## 5. User Roles & Personas

### 5.1 Parent (Primary User)

| Attribute | Details |
|-----------|---------|
| **Role** | Primary platform user; manages children's education |
| **Goals** | Track academic progress, support study at home, communicate with teachers |
| **Pain Points** | Fragmented tools, lack of visibility into schoolwork, no structured study help |
| **Technical Level** | Novice to Intermediate |
| **Key Features** | Dashboard with urgency-first view, AI study tools, messaging, calendar, analytics |

### 5.2 Student

| Attribute | Details |
|-----------|---------|
| **Role** | Learner; uses platform for study tools and organization |
| **Goals** | Stay organized, study effectively, track assignments and grades |
| **Pain Points** | Lack of study tools, poor organization, no centralized assignment tracking |
| **Technical Level** | Intermediate |
| **Key Features** | AI study guides/quizzes/flashcards, task management, calendar, grade analytics |

### 5.3 Teacher (School Teacher / Private Tutor)

| Attribute | Details |
|-----------|---------|
| **Role** | Educator; manages courses and communicates with parents |
| **Goals** | Manage classes, communicate with parents, share materials, monitor student progress |
| **Pain Points** | Disconnected communication, no unified platform for all students |
| **Technical Level** | Intermediate to Advanced |
| **Key Features** | Course management, Google Classroom sync, messaging, email monitoring, announcements |

**Teacher Types:**
- **School Teacher:** Teacher at a school whose courses appear via Google Classroom sync
- **Private Tutor:** Independent educator who creates own courses, manages students directly

### 5.4 Administrator

| Attribute | Details |
|-----------|---------|
| **Role** | Platform manager; oversees users and system health |
| **Goals** | Manage users, monitor platform activity, ensure compliance, curate content |
| **Pain Points** | Lack of visibility into platform usage, manual user management |
| **Technical Level** | Advanced |
| **Key Features** | User management, role management, audit logs, broadcast messaging, FAQ management |

---

## 6. System Architecture

### 6.1 Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend** | FastAPI (Python 3.13+), SQLAlchemy 2.0, Pydantic 2.x |
| **Frontend** | React 19, TypeScript, Vite, React Router 7, TanStack React Query, Axios |
| **Database** | SQLite (development), PostgreSQL (production) |
| **AI** | OpenAI API (gpt-4o-mini) |
| **Authentication** | JWT (python-jose), OAuth2 Bearer, bcrypt |
| **Google APIs** | Classroom API, Gmail API, OAuth2 |
| **Email** | SendGrid |
| **Scheduling** | APScheduler (reminders, sync jobs) |
| **Deployment** | Google Cloud Platform (Cloud Run, Cloud SQL) |
| **Mobile** | Expo SDK 54, React Native 0.81.5 |

### 6.2 Backend Structure

```
app/
  api/
    routes/          # FastAPI routers (all mounted under /api prefix)
    deps.py          # Shared dependencies: get_db(), get_current_user(), require_role()
  models/            # SQLAlchemy ORM models
  schemas/           # Pydantic request/response models
  services/          # Business logic (AI, Google sync, email, file processing)
  jobs/              # APScheduler background jobs
  core/
    config.py        # Pydantic BaseSettings from .env
    security.py      # JWT creation, password hashing
    logging_config.py
  db/database.py     # Engine, session factory, Base
```

### 6.3 Frontend Structure

```
frontend/src/
  pages/             # Route-level page components
  components/        # Reusable UI components
  context/           # Auth state provider (AuthContext.tsx)
  api/client.ts      # Axios instance with Bearer token interceptor
```

### 6.4 Key Architectural Patterns

- **RBAC:** `UserRole` enum (PARENT, STUDENT, TEACHER, ADMIN) with `require_role()` backend dependency and `ProtectedRoute` frontend component
- **Multi-Role Support:** Users can hold multiple roles; `roles` column (comma-separated) with `has_role()` helper
- **Auth Flow:** Register -> JWT token -> localStorage -> Axios interceptor -> Bearer header
- **Google OAuth:** Incremental scope requests with CSRF state parameter protection
- **DB Migrations:** `Base.metadata.create_all()` + startup ALTER TABLE blocks (no Alembic)

---

## 7. Core Features

### 7.1 Google Classroom Integration (Phase 1 - IMPLEMENTED)

- On-demand course sync (no automatic imports)
- Assignment sync with due dates, descriptions, and grades
- Student roster discovery for parent-child linking
- Teacher course ownership recognition
- Multi-Google account support for teachers
- Gmail monitoring for teacher email communications

### 7.2 AI Study Assistant (Phase 1 - IMPLEMENTED)

| Feature | Description |
|---------|-------------|
| **Study Guides** | AI-generated markdown study guides from course content with math-aware formatting |
| **Practice Quizzes** | Multiple-choice questions with auto-grading and result history |
| **Flashcards** | Front/back card pairs with mastery tracking |
| **Content Extraction** | PDF, Word, PPTX, image OCR (Tesseract) support up to 100MB |
| **Non-blocking Generation** | Modal closes immediately, pulsing placeholder appears while generating |
| **Truncation Detection** | Detects token limit cutoffs, stores is_truncated flag; Free users see Upgrade CTA, Plus/Unlimited get Continue generating button at 0 credits (#1645) |
| **Duplicate Detection** | Content hash checking prevents redundant AI API calls |
| **Version Control** | Regeneration creates linked versions preserving history |
| **Storage Limits** | 100 guides/student, 200/parent (configurable) with soft-delete archival |
| **Print & PDF Export** | Print and download PDF on all course material detail tabs |
| **Cloud Storage Destination** | Users choose to store uploads in their own Google Drive or OneDrive instead of GCS; auto-created `ClassBridge/{Course}/` folder structure; on-demand download for AI regeneration; fallback to GCS on failure (§6.95) |
| **Cloud File Import** | Import files directly from Google Drive or OneDrive via tabbed file browser in Upload Wizard; folder browsing, multi-select, server-side download into existing processing pipeline (§6.96) |

### 7.3 Task Manager & Calendar (Phase 1 - IMPLEMENTED)

- Create, edit, complete, archive, and permanently delete tasks
- Cross-role task assignment (parent->child, teacher->student)
- Calendar with Month/Week/3-Day/Day views
- Drag-and-drop task rescheduling
- Entity linking (tasks linked to courses, materials, study guides)
- Task reminders via in-app notifications
- Day Detail Modal for date-specific task management
- Dedicated Task Detail Page with resource linking

### 7.4 Communication System (Phase 1 - IMPLEMENTED)

- Secure parent-teacher messaging with conversation threads
- Email notifications on new messages (with 5-minute dedup)
- Teacher announcements to all course parents
- Teacher email monitoring (Gmail + Google Classroom announcements)
- AI-powered email summarization
- In-app notification bell with unread counts

### 7.5 Performance Analytics (Phase 2 - IMPLEMENTED)

- Grade tracking from Google Classroom and manual entry
- Per-course and overall averages with trend detection
- Recharts line/bar charts with time range filters
- AI-powered insights (OpenAI gpt-4o-mini analysis)
- Weekly cached progress reports
- Quiz results history with score trends

### 7.6 Security & Compliance (Phase 1 - IMPLEMENTED)

- JWT with 30-day refresh tokens
- CORS hardening (explicit origin allowlist)
- Google OAuth CSRF protection (state parameter)
- RBAC authorization on all endpoints
- Password strength validation (8+ chars, upper/lower/digit/special)
- Rate limiting on sensitive endpoints
- Audit logging for FERPA/PIPEDA compliance
- WCAG 2.1 AA accessibility

---

## 8. Role Workflows

---

### 8.1 Parent Workflow

The parent is the **primary user** of ClassBridge. The platform is designed parent-first, meaning all features work without requiring school integration.

#### 8.1.1 Registration & Onboarding

**Registration Path:**
1. Navigate to `/register`
2. Enter full name, email, and password
3. Submit creates User record
4. Redirected to `/onboarding` page
5. Select roles (Parent/Guardian, optionally Teacher or Student)
6. Complete onboarding -> redirected to Parent Dashboard

**Alternative Registration:**
- Google OAuth: Click "Sign in with Google" -> authorize -> pre-filled registration
- Password reset available via email-based JWT token flow

#### 8.1.2 Parent Dashboard (Urgency-First Layout)

The Parent Dashboard uses an **urgency-first, single-hub layout** with:

```
+-----------------------------------------------------------+
| Header: Logo | Search (Ctrl+K) | Bell | User | Sign Out   |
+-----+---------------------------------------------------------+
|ICON | [Child1] [Child2] [+]     <- Child Filter Pills + Add  |
|ONLY |-------------------------------------------------------- |
|SIDE | TODAY'S FOCUS HEADER                                    |
|BAR  | "Good morning, Name!"                                   |
|     | [3 Overdue] [2 Due Today] [5 Upcoming]                  |
|     | "Small steps lead to big achievements" (quote)          |
|     |-------------------------------------------------------- |
|     | ALERT BANNER (overdue + pending invites)                 |
|     |-------------------------------------------------------- |
|     | STUDENT DETAIL PANEL (collapsible)                      |
|     | - Courses (with color dots)                              |
|     | - Course Materials (with type badges)                    |
|     | - Tasks by Urgency (Overdue > Today > Next 3 Days)      |
+-----+---------------------------------------------------------+
```

**Key Components:**
- **Icon-Only Sidebar:** Always visible on desktop (>=768px), hamburger overlay on mobile
- **Child Filter Pills:** Click to filter all data by child; click again to deselect
- **Today's Focus Header:** Greeting + urgency badges + inspirational quote
- **Alert Banner:** Overdue items (red) + pending invites (amber)
- **Student Detail Panel:** Collapsible per-child view with courses, materials, and urgency-grouped tasks
- **+ Icon Popover:** Quick actions (Upload Documents, New Task)

**Navigation Items:**
- Overview (Dashboard)
- Child Profiles (/my-kids)
- Courses (/courses)
- Course Materials (/course-materials)
- Tasks (/tasks)
- Messages (/messages)
- Help (/help)

#### 8.1.3 Student (Child) Management

**Adding Children:**

| Method | Description | Student Login? |
|--------|-------------|----------------|
| **Create with Name Only** | Parent creates child from Dashboard with just a name | No (parent-managed) |
| **Create with Email** | Parent creates child with email; invite sent | Yes (via invite link) |
| **Link by Email** | Link to existing student account | Yes |
| **Google Classroom Discovery** | Discover children from Google Classroom courses | Yes (via invite link) |
| **Bulk Link** | Link multiple students discovered via Google | Yes (via invite link) |

**My Kids Page (/my-kids):**
- Child cards with colored avatars
- Task progress bars per child
- Next-deadline countdowns
- Quick action buttons per child
- Teacher linking section
- Edit child details (name, grade, school, phone, address)
- Reset child password (send email or set directly)

**Key Endpoints:**
- `POST /api/parent/children/create` - Create child (name required, email optional)
- `POST /api/parent/children/link` - Link existing student by email
- `POST /api/parent/children/discover-google` - Discover via Google Classroom
- `POST /api/parent/children/link-bulk` - Bulk link students
- `PATCH /api/parent/children/{id}` - Update child info
- `POST /api/parent/children/{id}/reset-password` - Reset child password
- `GET /api/parent/children/{id}/overview` - Child overview with courses, assignments, tasks

#### 8.1.4 Course Management

- Parents can **create courses** (private to their children)
- Parents can **assign courses** to linked children
- View courses from Google Classroom (after sync)
- Course Detail Page with materials, assignments, and student roster

**Course Creation Flow:**
1. Click "Create Course" from Courses page or + popover
2. Enter course name, subject, and description
3. Course created with `is_private=true`, `created_by_user_id=parent`
4. Assign to children via `/api/parent/children/{student_id}/courses`

#### 8.1.5 AI Study Tools Access

**Study Guide Generation:**
1. From Course Material, Dashboard, or Tasks page
2. Upload document (PDF, Word, PPTX, image) or paste text
3. AI generates structured markdown study guide
4. Critical dates extracted -> auto-creates linked tasks
5. Guide stored with version history and course linkage

**Quiz Generation:**
1. From existing study guide or directly from content
2. AI generates multiple-choice questions
3. Take quiz with auto-grading
4. Results saved with score, per-question answers, and attempt tracking
5. Quiz history available at `/quiz-history`

**Flashcard Generation:**
1. From existing study guide or directly from content
2. AI generates front/back card pairs
3. Study with flip-card interface
4. Mark cards as "Mastered" or "Learning"

**Course Materials Page (/course-materials):**
- Lists all course materials across all courses
- Tabbed detail view per material:
  - Tab 1: Original Document
  - Tab 2: Study Guide (generate if none)
  - Tab 3: Quiz (generate if none)
  - Tab 4: Flashcards (generate if none)
- Print and Download PDF on all tabs
- Filter by child and course

#### 8.1.6 Messaging Teachers

**Starting a Conversation:**
1. Click "+ New Message" on Messages page
2. Select recipient (teachers linked to children's courses)
3. Enter subject and message
4. Conversation created; recipient notified

**Conversation Features:**
- Conversation list with unread badges
- Message thread with auto-scroll
- Read status indicators
- 15-30 second polling for new messages
- Email notification to recipient (with dedup)

#### 8.1.7 Calendar & Tasks

**Calendar (on Tasks Page):**
- Month/Week/3-Day/Day views
- Assignments (color-coded by course) + Tasks (priority-based colors)
- Drag-and-drop task rescheduling
- Click date -> Day Detail Modal
- Collapsible (default collapsed)

**Tasks Page (/tasks):**
- Create/edit/complete/archive/delete tasks
- Filter by: Status, Priority, Due Date, Assignee
- Assign tasks to children
- Link tasks to courses, materials, and study guides
- Task Detail Page with resource linking

#### 8.1.8 Analytics & Grade Tracking

**Analytics Page (/analytics):**
- Child selector dropdown
- Grade summary (overall average, per-course averages)
- Trend chart (30d/60d/90d/All with course filter)
- Recent grades table
- AI-powered insights (on-demand generation)

#### 8.1.9 Notifications

**Types:** Assignment due, grade posted, new message, link request, task due, study guide created, material uploaded, system announcements

**Delivery:** In-app (notification bell with badge) + email (SendGrid)

#### 8.1.10 Google Classroom Integration

**Connection Flow:**
1. Click "Connect Google Classroom" on Dashboard
2. Redirect to Google OAuth consent screen
3. Authorize access to Classroom, Drive, Gmail
4. Tokens stored server-side
5. Manual course sync available

**What Syncs:**
- Courses (name, description, subject, teacher info)
- Assignments (titles, descriptions, due dates, grades)
- Student roster (for child discovery)

---

### 8.2 Student Workflow

Students can register independently or be created by a parent. The platform provides AI study tools, task management, and communication features.

#### 8.2.1 Registration & Onboarding

**Path 1: Self-Registration**
1. Navigate to `/register`
2. Select "I'm a student" checkbox
3. Enter name, email/username, and password
4. Optionally enter parent email (triggers link request)
5. Auto-logged in -> `/dashboard`

**Path 2: Invite-Based (from Parent/Admin)**
1. Receive invite email with token link
2. Navigate to `/accept-invite?token=<TOKEN>`
3. Set full name and password
4. Student account activated and linked to parent

**Path 3: Google OAuth**
1. Click "Sign in with Google"
2. Authorize ClassBridge
3. Pre-filled registration with Google email
4. Complete signup with password

#### 8.2.2 Student Dashboard (Focused Command Center)

```
+-----------------------------------------------------------+
| Header: Logo | Search (Ctrl+K) | Bell | User | Sign Out   |
+-----+---------------------------------------------------------+
|ICON | HERO SECTION                                            |
|ONLY | "Good morning, Name!"                                   |
|SIDE | [3 Overdue] [2 Due Today]  <- urgency pills             |
|BAR  | 5 Courses - 12 Materials - 8 Tasks  <- stat chips       |
|     |-------------------------------------------------------- |
|     | NOTIFICATION ALERTS (if any)                             |
|     | [Parent assigned: Math HW] [Teacher request: Quiz]       |
|     |-------------------------------------------------------- |
|     | QUICK ACTIONS (2x2 grid)                                 |
|     | [Upload Materials] [Create Course]                       |
|     | [Generate Study Guide] [Sync Classroom]                  |
|     |-------------------------------------------------------- |
|     | COMING UP (timeline - next 7 days)                       |
|     | * Tomorrow - Math HW (Math 101)                          |
|     | * Wed - Science Lab Report                               |
|     |-------------------------------------------------------- |
|     | RECENT MATERIALS + COURSE CHIPS                          |
+-----+---------------------------------------------------------+
```

**Key Features:**
- Hero greeting with urgency pills and stat chips
- Notification alerts for parent/teacher requests
- Quick action cards (Upload, Create Course, Generate Guide, Sync)
- Unified "Coming Up" timeline (assignments + tasks)
- Recent materials with type icons and course badges
- Course chips (horizontal row of enrolled courses)
- Onboarding card for new students

#### 8.2.3 Courses & Assignments

**Viewing Courses (/courses):**
- List enrolled courses (from Google Classroom or manual creation)
- Course cards with teacher info and student count
- Click to view Course Detail Page

**Course Detail Page (/courses/:id):**
- Course metadata (name, subject, description)
- Course Materials section (documents, links)
- Assignments section (with due dates and grades)
- Study Tools linked to course

**Creating Courses:**
- Students can create their own courses (visible to self only)
- Useful for self-directed study or organizing materials

#### 8.2.4 AI Study Tools

**Study Guide Creation:**
1. Click "Create Study Guide" from Dashboard, Course, or Course Materials
2. Upload document or type/paste content
3. AI generates structured study guide with key concepts
4. Math-aware: provides step-by-step worked solutions when math detected
5. Version history preserved for regeneration

**Taking Quizzes:**
1. Generate quiz from study guide or content
2. Multiple-choice questions displayed one at a time
3. Submit answers -> immediate feedback (Correct/Incorrect)
4. Final score calculated at completion
5. Results saved to quiz history
6. Retry available with new attempt tracking

**Studying Flashcards:**
1. Generate flashcards from study guide or content
2. Flip-card interface (front=question, back=answer)
3. Mark cards as "Mastered" or "Learning"
4. Shuffle and review modes available

**Quiz History (/quiz-history):**
- Stats cards: Total Attempts, Unique Quizzes, Average Score, Best Score
- Score trend chart (Recharts line chart)
- Scrollable attempts list with retry and delete

#### 8.2.5 Task Management

- Create personal tasks with title, description, due date, and priority
- View tasks on dedicated Tasks page with filters
- Tasks appear on calendar alongside assignments
- Link tasks to courses, materials, and study guides
- Task Detail Page with full info card and resource linking

#### 8.2.6 Messaging

- Message teachers, parents, peers, and admins
- Conversation list with unread badges
- Real-time polling (15-30 seconds)
- Email notifications for new messages

#### 8.2.7 Analytics & Grades

- View grade summary and trends
- Filter by time range and course
- See AI-generated performance insights
- Track quiz results and score progression

#### 8.2.8 Google Classroom Integration

- Connect Google account -> sync courses and assignments
- One-way sync (Google -> ClassBridge, read-only)
- Background sync every 15 minutes
- Manual refresh available

#### 8.2.9 Settings & Profile

- Edit: full name, email, username, phone, grade, school, DOB, address
- Change password
- Link/unlink Google account
- Notification preferences
- Theme toggle (Light/Dark/Focus)

---

### 8.3 Teacher Workflow

Teachers manage courses, communicate with parents, monitor email, and support students. Two teacher types exist: School Teacher and Private Tutor.

#### 8.3.1 Registration & Onboarding

**Primary Path: Invite-Based**
1. Receive invite email from parent, admin, or another teacher
2. Click invite link (`/accept-invite?token=<TOKEN>`)
3. Set full name and password
4. Invite token expires after 30 days

**Onboarding:**
1. Select roles (can be teacher + parent + student)
2. Choose teacher type: School Teacher or Private Tutor
3. Creates Teacher profile record with selected type
4. Redirected to Teacher Dashboard

**Shadow Teachers:**
- When Google Classroom syncs and teacher is not on ClassBridge:
  - Shadow Teacher record created (`is_platform_user=false`)
  - Invite email sent to join ClassBridge
  - If accepted: converts to full platform teacher
  - If not accepted: remains read-only reference

#### 8.3.2 Teacher Dashboard

```
+-----------------------------------------------------------+
| Header: Logo | Search | Bell | User | Sign Out             |
+-----+---------------------------------------------------------+
|ICON | GREETING + MESSAGE COUNT                               |
|ONLY | "Good morning, Name!"  [3 unread messages]             |
|SIDE |-------------------------------------------------------- |
|BAR  | QUICK ACTION CARDS (grid)                               |
|     | [Classes] [Messages] [Communications]                    |
|     | [Announcement] [Invite Parent] [Upload Material]         |
|     | [Google Classroom: Connected/Connect]                    |
|     |-------------------------------------------------------- |
|     | RECENT MESSAGES (last 3 conversations)                   |
|     |-------------------------------------------------------- |
|     | UPCOMING DEADLINES (next 7 days, max 5)                  |
|     |-------------------------------------------------------- |
|     | YOUR CLASSES (searchable, with Create/Sync buttons)      |
|     | [Course Card] [Course Card] [Course Card]                |
|     |-------------------------------------------------------- |
|     | SENT INVITES (if any pending)                            |
|     |-------------------------------------------------------- |
|     | GOOGLE ACCOUNTS (if connected)                           |
+-----+---------------------------------------------------------+
```

#### 8.3.3 Course Management

**Creating Courses:**
- Manual creation: name, subject, description
- Google Classroom sync: import courses where teacher is owner
- Source badge: "Google Classroom" or "Manual" per course

**Course Detail Page:**
- Course metadata with edit capability
- Materials section: upload files, create text content, link external resources
- Assignments section: create/edit/delete assignments
- Roster section: list enrolled students, add by email

**Google Classroom Sync:**
1. Connect Google account (OAuth)
2. Click "Sync Classes" -> fetch courses owned by teacher
3. Courses created/updated with `google_classroom_id`
4. Student roster synced automatically
5. Assignment data pulled with due dates and point values

**Multi-Google Account Support:**
- Link multiple Google accounts (personal + school)
- Each account syncs its own courses
- Label accounts (e.g., "Personal", "Springfield High")
- One marked as primary for default operations

#### 8.3.4 Assignment Management

- Create assignments: title, description, course, due date, max points
- Edit and delete assignments
- View upcoming deadlines on dashboard
- Students notified of new assignments

#### 8.3.5 Parent Communication

**Direct Messaging:**
- View conversations with parents
- Send/receive messages
- Email notifications to parents
- Message dedup (5-minute window)

**Announcements:**
- Select course -> compose subject + body
- Sends email to ALL parents of students in that course
- Returns recipient count and email count

**Inviting Parents:**
- Enter parent email from dashboard
- If registered: sends direct message
- If not registered: creates invite with email

#### 8.3.6 Email/Announcement Monitoring

**Teacher Communications Page (/teacher-communications):**
- Sync emails from Gmail and Google Classroom announcements
- AI-powered email summarization
- Paginated list with type filter and search
- Communication detail view with full content
- Reply to emails via SendGrid
- Manual sync trigger + automatic 15-minute background sync

**Email Monitoring Status:**
- Gmail enabled/disabled
- Classroom enabled/disabled
- Last sync timestamps
- Total and unread counts

#### 8.3.7 Student Management

- View roster per course
- Add students by email
- View student details (enrolled in teacher's courses)
- Link students via invites

#### 8.3.8 Notification System

- New messages from parents
- Assignment submissions
- Link requests from parents
- Teacher invitations
- In-app bell + email delivery

---

### 8.4 Admin Workflow

Administrators manage the platform, users, content, and system health. Admin access is not available via self-registration.

#### 8.4.1 Login & Access

- Login via standard `/login` page
- Admin role assigned by existing admin (not self-registration)
- `require_role(UserRole.ADMIN)` on all admin endpoints
- `ProtectedRoute` with `allowedRoles={['admin']}` on frontend
- Multi-role support: admin can also be teacher/parent

#### 8.4.2 Admin Dashboard

```
+-----------------------------------------------------------+
| Header: Logo | Search | Bell | User | Sign Out             |
+-----+---------------------------------------------------------+
|ICON | PLATFORM STATISTICS                                    |
|ONLY | [Total Users: 150 (+12 this week)]                     |
|SIDE | [Students: 80 (+5)] [Teachers: 30 (+3)] [Classes: 45]  |
|BAR  |-------------------------------------------------------- |
|     | USER MANAGEMENT TABLE                                    |
|     | Search: [_____________] Role: [All Roles v]              |
|     | +------+-------+-------+--------+---------+----------+  |
|     | | Name | Email | Roles | Status | Created | Actions  |  |
|     | +------+-------+-------+--------+---------+----------+  |
|     | | ...  | ...   | ...   | Active | Feb 26  | Roles|Msg|  |
|     | +------+-------+-------+--------+---------+----------+  |
|     | [< Prev]  Page 1 of 15  [Next >]                        |
|     |-------------------------------------------------------- |
|     | RECENT ACTIVITY (last 5 audit log entries)               |
|     |-------------------------------------------------------- |
|     | BROADCAST HISTORY (collapsible)                          |
|     |-------------------------------------------------------- |
|     | QUICK LINKS: Audit Log | Inspirational Messages | FAQ   |
+-----+---------------------------------------------------------+
```

#### 8.4.3 User Management

**User Table:**
- Paginated (10/page) with search and role filter
- Columns: Name, Email, Roles, Status, Created, Actions

**Role Management:**
- Click "Roles" on any user -> modal with checkboxes
- Add/remove roles (parent, student, teacher, admin)
- Cannot remove last role
- Auto-creates profile records when adding roles (e.g., Student/Teacher)

**User Email Update:**
- `PATCH /api/admin/users/{user_id}/email`
- Cascades to pending invites

**Individual Messaging:**
- Click "Message" on any user
- Sends: in-app notification + conversation message + email

#### 8.4.4 Broadcast Messaging

- "Send Broadcast" button -> modal with subject + body
- Delivers to ALL active users:
  - In-app notification
  - Conversation message
  - Email (via SendGrid)
- Broadcast history shows dates, subjects, delivery metrics

#### 8.4.5 Audit Log (/admin/audit-log)

**What's Logged:**
- Login/login failure
- User creation (register, accept-invite)
- Task CRUD
- Study guide CRUD
- Course CRUD
- Message send
- Parent child access
- Google Classroom sync

**Features:**
- Filter by action type and resource type
- Full-text search on details
- 25 entries per page with pagination
- Columns: Time, User, Action, Resource, Details, IP Address

#### 8.4.6 Inspirational Messages (/admin/inspiration)

- CRUD for motivational messages shown on dashboards
- Filter by role (Parent, Teacher, Student)
- Toggle active/inactive per message
- Author attribution
- Messages randomly displayed in dashboard welcome sections

#### 8.4.7 FAQ Management (/admin/faq)

**Three Tabs:**
1. **Pending Answers:** Review and approve/reject user-submitted answers
2. **All Questions:** Pin/unpin questions, manage categories, soft-delete
3. **Create Official FAQ:** Admin creates pre-approved Q&A entries

**Categories:** getting-started, google-classroom, study-tools, account, courses, messaging, tasks, other

#### 8.4.8 Platform Statistics

- Total users with weekly trend
- Users by role (parent, student, teacher, admin)
- Total courses and assignments
- Trend badges (+N this week)

---

## 9. Role-Based Dashboards

### Summary Comparison

| Feature | Parent | Student | Teacher | Admin |
|---------|--------|---------|---------|-------|
| **Layout Style** | Urgency-first hub | Focused command center | Activity summary | Management console |
| **Sidebar** | Icon-only, 7 nav items | Icon-only, 5+ nav items | Icon-only, 5+ nav items | Icon-only, 5+ nav items |
| **Hero/Header** | Today's Focus with urgency badges | Greeting with urgency pills + stats | Greeting with message count | Platform statistics |
| **Primary Action** | Monitor children's progress | Upload & study materials | Manage courses & communicate | Manage users & content |
| **Calendar** | On Tasks page (collapsed default) | Available on tasks page | Available on tasks page | Personal tasks only |
| **Messaging** | Teachers, admins, other parents | Teachers, parents, peers | Parents of students | All users + broadcast |
| **Google Classroom** | Child discovery + course sync | Course + assignment sync | Course ownership sync | N/A |
| **Analytics** | Per-child grade tracking | Own grade tracking | Course student analytics | Platform-wide statistics |
| **AI Tools** | Generate for children | Generate for self | N/A | N/A |

---

## 10. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Availability** | 99.9% uptime |
| **Performance** | < 2s response time for all API calls |
| **Scalability** | 100k+ users |
| **Security** | Encryption in transit (HTTPS) and at rest |
| **Compliance** | FERPA, MFIPPA, PIPEDA, GDPR (if applicable) |
| **Accessibility** | WCAG 2.1 AA (focus traps, ARIA labels, 44px touch targets, 4.5:1 contrast) |
| **Browser Support** | Chrome, Firefox, Safari, Edge (latest 2 versions) |
| **Mobile** | Responsive web (320px-1440px) + React Native app (Expo) |

### Data Privacy & User Rights

- Account deletion with cascade delete/anonymize
- Data export (JSON/CSV) per GDPR Article 20 / PIPEDA
- Consent management for data collection and Google OAuth
- Data retention policies for inactive accounts
- Minor data protection (no marketing to students)
- Audit logging for compliance (Phase 1 complete)

---

## 11. Phased Roadmap

### Phase 1 (MVP) - SUBSTANTIALLY COMPLETE

**Core Features (All Implemented):**
- Google Classroom integration (on-demand sync for parents, students, teachers)
- Parent, Student, Teacher, Admin dashboards (all redesigned with urgency-first layout)
- AI study tools (guides, quizzes, flashcards) with math-aware prompts and DOCX OCR
- Secure parent-teacher messaging with email notifications and dedup
- Task manager with calendar integration, drag-and-drop, entity linking
- Audit logging with admin API and UI
- Multi-role support (Phase A: role switcher, multi-role registration)
- Security hardening (JWT refresh, CORS, RBAC, rate limiting, security headers, password reset)
- Course materials lifecycle (soft delete, archive, retention, replace document)
- Print & PDF export for course materials
- Theme system (Light/Dark/Focus modes) with flat non-gradient default
- Parent-to-teacher manual linking with email notifications
- Teacher course roster management (add/remove students, assign teacher)
- Manual assignment CRUD for teachers
- Welcome email on registration and email verification
- Inspirational messages (role-based, admin-managed, included in emails)
- My Kids page with child cards, teacher linking, quick stats
- Global search (Ctrl+K) across courses, tasks, materials
- Loading skeletons, toast notifications, error boundaries
- WCAG 2.1 AA accessibility (focus traps, ARIA, 4.5:1 contrast, 44px touch targets)
- Breadcrumb navigation, micro-interactions, mobile touch support
- Student Dashboard "Focused Command Center" redesign
- Parent Dashboard visual redesign (Epic #710 complete)
- Admin broadcast + individual messaging with email
- FAQ / Knowledge Base with admin approval workflow (8 issues, all complete)
- HCD Assessment Tier 1 complete (design tokens, responsive breakpoints, progressive disclosure)

**Remaining Phase 1 Items:**
- [ ] Simplified registration (remove role from signup, #412)
- [ ] Post-login onboarding flow (#413, #414)
- [ ] Student registration with username + parent email (#546)
- [ ] Parent-Student LinkRequest approval workflow (#547)
- [ ] Multi-channel notifications with ACK (#548)
- [ ] Upload with AI tool selection (#552)

### Phase 1.5 (Calendar Extension, Mobile & School Integration)
- [x] Mobile-responsive web (CSS breakpoints, touch support) - IN PROGRESS — 75 CSS files have breakpoints; ~55+ files still need 768px/480px breakpoints (#1641)
- [x] Extend calendar to Student and Teacher dashboards - IMPLEMENTED
- [x] Background periodic Google Classroom sync for teachers - IMPLEMENTED
- [ ] Student email identity merging (personal + school email)
- [ ] Google Calendar push integration
- [ ] Central document repository

### Phase 2 (WOW Features — Parent Value & Engagement) — NEW (March 2026)

Features that answer pilot feedback: *"Why should I use ClassBridge?"* — transforming ClassBridge from a passive viewer to an active parenting tool.

**Core Principle: Parents First, Responsible AI** — AI helps parents understand and engage; AI challenges students, never shortcuts their learning.

| Priority | Feature | Epic | AI Cost | WOW Impact |
|----------|---------|------|---------|------------|
| 1 | **Smart Daily Briefing** — proactive "what matters today" | #1403 | $0 | Highest |
| 2 | **Help My Kid** — one-tap study material generation | #1407 | ~$0.02/use | Highest |
| 3 | **Global Search + Smart Shortcuts** | #1410 | $0 | Medium |
| 4 | **Weekly Progress Pulse** — email digest every Sunday | #1413 | $0 | High |
| 5 | **Parent-Child Study Link** — feedback loop | #1414 | $0 | High |
| 6 | **Dashboard Redesign** — clean, persona-based layouts | #1415 | $0 | High |
| 7 | **Responsible AI Parent Tools** — readiness checks, parent briefings, practice problems, weak spots, conversation starters | #1421 | ~$0.02/use | Highest |

**Responsible AI Parent Tools (§6.66):**
- **"Is My Kid Ready?" Assessment** — 5-question diagnostic, parent sees gap report, student must answer
- **Parent Briefing Notes** — plain-language topic summary for parents only, student never sees
- **Practice Problem Sets** — open-ended problems student must solve (not multiple choice)
- **Weak Spot Report** — SQL aggregation of quiz results, zero AI cost
- **Conversation Starters** — dinner table prompts based on what child is studying

**Dashboard Redesign (§6.65) — 3-section max per role:**
- Parent v5: Daily Briefing + Child Snapshot + Quick Actions
- Student v4: Coming Up + Recent Study + Quick Actions
- Teacher v2: Student Alerts + My Classes + Quick Actions
- Admin v2: Platform Health + Recent Activity + Quick Actions

**Hybrid Search Strategy:** All search is SQL ILIKE ($0). AI only invoked on explicit generation actions.

### Phase 2 (Intelligence & Data)
- [x] Performance Analytics Dashboard - IMPLEMENTED (#469-#474)
- [x] Quiz Results History - IMPLEMENTED (#574, #621)
- [x] FAQ / Knowledge Base - IMPLEMENTED (#437-#444)
- [x] AI Usage Limits and Quota Management - IMPLEMENTED (#1121-#1130)
- [ ] AI Token/Cost Tracking — prompt_tokens, completion_tokens, estimated_cost_usd per generation (#1650)
- [ ] AI Regeneration/Continuation Tracking — is_regeneration, is_continuation flags; admin filter by type (#1651)
- [ ] Continuation as Premium Perk — Free tier sees Upgrade CTA on truncated guides; Plus/Unlimited get free continuation (#1645)
- [ ] Admin cost-summary endpoint — total cost by user/type/date range (#1650)
- [ ] Mind Map desktop layout — horizontal, center node with left/right branches, no overlap (#1653)
- [ ] Course Materials Storage (GCS) (#572)
- [ ] User-Provided AI API Key (BYOK) (#578)
- [ ] Study Guide Repository & Reuse (#573)
- [ ] Student Progress Analysis (#575)
- [ ] Sample Exams/Tests Upload (#577)
- [ ] Parent AI Insights (#581)
- [ ] **User Cloud Storage Destination** — Users choose to store uploaded materials in their own Google Drive or OneDrive instead of GCS; auto-created `ClassBridge/{Course}/` folder structure; on-demand download for AI regeneration; fallback to GCS on failure (§6.95, #1865-#1871)
- [ ] **Cloud File Import** — Import files directly from Google Drive or OneDrive into Upload Wizard via tabbed file browser; folder browsing, multi-select, server-side download into existing processing pipeline (§6.96, #1872-#1877)
- [x] Mobile App March 2026 Pilot (8 screens COMPLETE)

### VASP/DTAP Compliance - Ontario School Board Approval (29 issues open)
- Data residency (GCP Canada region, OpenAI data transfer)
- Privacy (PIA, MFIPPA consent, PIPEDA compliance, cookie disclosure)
- Security (MFA/2FA, SSO/SAML, httpOnly cookies, WAF/DDoS, SAST/DAST)
- Governance (SOC 2, penetration testing, breach notification, DPA templates)
- Accessibility (WCAG 2.1 AA remediation)
- School board engagement (K-12CVAT questionnaire, pilot partner)

### LMS Abstraction & D2L Brightspace Integration (5 issues open)
- LMS adapter pattern with OneRoster canonical models
- Google Classroom refactored into LMSProvider adapter
- D2L Brightspace MVP (courses, assignments, grades sync)

### Phase 3 (Course Planning & Guidance)
- Ontario Curriculum Management
- School Board Integration
- Academic Plan Model (Grade 9-12)
- AI Course Recommendations
- University Pathway Alignment
- Multi-language support

### Phase 4 (Tutor Marketplace)
- Private tutor profiles
- Search & discovery
- AI tutor matching
- Booking workflow
- Ratings & reviews
- Payment integration

### Phase 5 (AI Email Agent)
- AI email sending
- Reply ingestion
- AI summaries
- Searchable archive

---

## 12. Success Metrics (KPIs)

| KPI | Measurement |
|-----|-------------|
| **Parent Engagement Rate** | % of parents logging in weekly |
| **Student Grade Improvement** | Average grade change after 1 semester |
| **Daily Active Users** | DAU across all roles |
| **Retention Rate** | 30-day and 90-day retention |
| **Teacher Adoption Rate** | % of invited teachers who accept |
| **AI Tool Usage** | Study guides/quizzes/flashcards generated per user per week |
| **Message Response Time** | Average time for parent-teacher message replies |

---

## 13. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Google API rate limits | Medium | High | Implement caching, batch requests, exponential backoff |
| User adoption challenges | Medium | High | Focus on UX, onboarding experience, pilot with target families |
| OpenAI API costs at scale | High | Medium | BYOK feature (Phase 2), study guide repository/reuse, caching |
| VASP/DTAP compliance for school boards | High | High | 29 compliance issues planned; PIA, MFA, SSO, data residency, SOC 2 readiness |
| Data privacy compliance (MFIPPA/PIPEDA) | Medium | High | Age-based consent, data export/erasure, privacy officer, breach procedures |
| SQLite to PostgreSQL migration issues | Medium | Medium | Cross-DB testing, migration scripts, type compatibility checks |
| Stale browser cache after deploy | Low | Low | Lazy chunk retry wrapper, cache-busting, Ctrl+Shift+R guidance |
| Railway migration risk | Low | Medium | Staged cutover plan (6 issues), domain verification, rollback path |

---

## 14. Appendix

### 14.1 Data Model Summary

```
User
  |- id, email (nullable for students), hashed_password, full_name
  |- role (active), roles (comma-separated all roles)
  |- google_access_token, google_refresh_token
  |- email_notifications, needs_onboarding

Student (1:1 with User)
  |- grade_level, school_name, DOB, phone, address
  |- parents (via parent_students) -> User[]
  |- courses (via student_courses) -> Course[]

Teacher (1:1 with User)
  |- school_name, department, teacher_type, is_platform_user
  |- google_accounts -> TeacherGoogleAccount[]

Course
  |- name, subject, description
  |- teacher_id (nullable), created_by_user_id
  |- is_private, is_default, google_classroom_id
  |- students (via student_courses)

Assignment
  |- course_id, title, description, due_date, max_points
  |- google_id

CourseContent
  |- course_id, title, description, text_content, content_type
  |- reference_url, archived_at, last_viewed_at

StudyGuide
  |- title, content, guide_type (study_guide/quiz/flashcards)
  |- created_by_user_id, created_for_user_id
  |- course_id, course_content_id, parent_guide_id
  |- archived_at

Task
  |- title, description, due_date, priority, is_completed
  |- created_by_user_id, assigned_to_user_id
  |- course_id, course_content_id, study_guide_id

Conversation & Message
  |- participant_1_id, participant_2_id, subject, student_id
  |- Messages: sender_id, content, is_read

Notification
  |- user_id, type, title, description, read, action_url

parent_students (join table)
  |- parent_id, student_id, relationship_type

Invite
  |- email, invite_type, token, expires_at, invited_by_user_id

AuditLog
  |- user_id, action, resource_type, resource_id, details, ip_address

GradeRecord
  |- student_id, course_id, assignment_id, grade, max_grade, percentage, source

QuizResult
  |- user_id, study_guide_id, score, total_questions, percentage, answers_json

FAQQuestion
  |- title, body, category, status (open/answered/closed)
  |- asked_by_user_id, is_pinned, view_count, error_code

FAQAnswer
  |- question_id, body, author_id, is_official
  |- status (pending/approved/rejected), reviewed_by_user_id

InspirationMessage
  |- message, author, target_role, is_active, display_order

CloudStorageConnection (§6.95, §6.96)
  |- user_id, provider (google_drive/onedrive/dropbox)
  |- encrypted_refresh_token, account_email
  |- connected_at, last_used_at, is_active
  |- UNIQUE(user_id, provider)

CloudStorageFolder (§6.95 — folder cache)
  |- user_id, provider, course_id
  |- folder_name, cloud_folder_id, parent_folder_id
  |- UNIQUE(user_id, provider, course_id)

SourceFile (new columns for §6.95/§6.96)
  |- storage_destination (gcs/google_drive/onedrive)
  |- cloud_file_id, cloud_provider, cloud_folder_id
  |- source_type (local_upload/google_drive/onedrive)

User (new column for §6.95)
  |- file_storage_preference (gcs/google_drive/onedrive)
```

### 14.2 API Endpoint Summary

**Authentication:**
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - Login (returns JWT)
- `POST /api/auth/accept-invite` - Accept invite
- `POST /api/auth/complete-onboarding` - Complete onboarding
- `POST /api/auth/forgot-password` - Request password reset
- `POST /api/auth/reset-password` - Reset password

**Parent:**
- `GET /api/parent/dashboard` - Aggregated dashboard data
- `GET /api/parent/children` - List linked children
- `POST /api/parent/children/create` - Create child
- `POST /api/parent/children/link` - Link child by email
- `POST /api/parent/children/discover-google` - Discover via Google
- `GET /api/parent/children/{id}/overview` - Child overview

**Courses:**
- `GET /api/courses/` - List courses
- `POST /api/courses/` - Create course
- `GET /api/courses/{id}` - Course details
- `PATCH /api/courses/{id}` - Update course
- `POST /api/courses/{id}/enroll` - Enroll student

**Study Tools:**
- `POST /api/study/generate` - Generate study guide
- `POST /api/study/quiz/generate` - Generate quiz
- `POST /api/study/flashcards/generate` - Generate flashcards
- `GET /api/study/guides` - List study materials
- `POST /api/quiz-results/` - Save quiz result
- `GET /api/quiz-results/stats` - Quiz statistics

**Messaging:**
- `GET /api/messages/conversations` - List conversations
- `POST /api/messages/conversations` - Create conversation
- `POST /api/messages/conversations/{id}/messages` - Send message
- `GET /api/messages/unread-count` - Unread count

**Tasks:**
- `GET /api/tasks/` - List tasks
- `POST /api/tasks/` - Create task
- `PATCH /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Archive task

**Admin:**
- `GET /api/admin/users` - List users
- `GET /api/admin/stats` - Platform stats
- `GET /api/admin/audit-logs` - Audit logs
- `POST /api/admin/broadcast` - Broadcast message
- `POST /api/admin/users/{id}/message` - Individual message

**Google:**
- `GET /api/google/connect` - OAuth URL
- `GET /api/google/callback` - OAuth callback
- `POST /api/google/courses/sync` - Sync courses

**Analytics:**
- `GET /api/analytics/summary` - Grade summary
- `GET /api/analytics/trends` - Grade trends
- `POST /api/analytics/ai-insights` - AI analysis

**FAQ / Knowledge Base:**
- `GET /api/faq/questions` - List FAQ questions
- `POST /api/faq/questions` - Ask a question
- `POST /api/faq/questions/{id}/answers` - Submit answer
- `GET /api/faq/admin/pending` - Admin pending queue
- `PATCH /api/faq/admin/answers/{id}/approve` - Approve answer

**Invites:**
- `POST /api/invites/student` - Invite student
- `POST /api/invites/teacher` - Invite teacher
- `POST /api/invites/resend/{id}` - Resend invite

**Cloud Storage (§6.95, §6.96):**
- `POST /api/cloud-storage/connect/{provider}` - Initiate OAuth, store tokens
- `DELETE /api/cloud-storage/disconnect/{provider}` - Revoke and delete connection
- `GET /api/cloud-storage/connections` - List user's cloud connections
- `PATCH /api/users/me/storage-preference` - Update file storage destination preference
- `GET /api/cloud-storage/{provider}/files` - List files/folders in user's cloud drive (§6.96)
- `POST /api/cloud-storage/{provider}/import` - Download and process cloud files (§6.96)

### 14.3 Glossary

| Term | Definition |
|------|-----------|
| **ClassBridge** | The product name for the EMAI education platform |
| **EMAI** | Original project codename (Education Management AI) |
| **RBAC** | Role-Based Access Control |
| **JWT** | JSON Web Token (authentication mechanism) |
| **Shadow Teacher** | Auto-created teacher record from Google Classroom (not on platform) |
| **Course Material** | Umbrella term for uploaded content + generated study tools |
| **Study Guide** | AI-generated study summary from course content |
| **BYOK** | Bring Your Own Key (user provides their OpenAI API key) |
| **DDD** | Domain-Driven Design (target architecture) |
| **OSSD** | Ontario Secondary School Diploma |
| **Storage Destination** | Where uploaded files are persisted — GCS (ClassBridge-managed) or user's personal cloud drive (§6.95) |
| **Cloud File Import** | Browsing and selecting files from a user's cloud drive for import into ClassBridge (§6.96) |
| **Incremental Auth** | Adding new OAuth scopes to an existing authentication without full re-consent |

### 14.4 References

- [REQUIREMENTS.md](../REQUIREMENTS.md) - Original requirements
- [requirements/](../requirements/) - Detailed feature specifications
- [design/UI_AUDIT_REPORT.md](../design/UI_AUDIT_REPORT.md) - UI/UX Audit Report
- [docs/ClassBridge_UI_UX_Assessment_Report.docx](ClassBridge_UI_UX_Assessment_Report.docx) - HCD Assessment
- [docs/cloud-storage-integration-prd.md](cloud-storage-integration-prd.md) - Cloud Storage PRD (§6.95, §6.96)
- Swagger API Docs: `http://localhost:8000/docs`
- Production URL: `https://www.classbridge.ca`

---

*This document was compiled from the ClassBridge codebase analysis, REQUIREMENTS.md, and role-specific workflow exploration. It covers all implemented features as of February 27, 2026. Updated with comprehensive GitHub issue audit (725 issues, 538 closed).*

*Quality Score: 95/100*
- Business Value & Goals: 28/30
- Functional Requirements: 24/25
- User Experience: 19/20
- Technical Constraints: 14/15
- Scope & Priorities: 10/10
