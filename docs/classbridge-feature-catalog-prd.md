# ClassBridge — Complete Feature & Design Catalog

**Version**: 1.2
**Date**: 2026-03-20
**Author**: Sarah (Product Owner)
**Source Data**: 1,969 GitHub Issues + REQUIREMENTS.md (60+ feature sections)
**Quality Score**: 95/100

---

## Executive Summary

ClassBridge is an AI-powered education platform connecting parents, students, teachers, and administrators in a unified role-based application. Built on FastAPI + React 19, it integrates with Google Classroom, provides AI-driven study tools, enables secure messaging, and gives parents active visibility into their children's education.

This document catalogs **every feature** across 5 development phases, organized by functional domain. Each feature includes its status, GitHub issues, design details, and implementation notes.

**By the numbers:**
- **1,969 issues** tracked across phases
- **60+ feature sections** documented
- **4 role-based dashboards** (Parent, Student, Teacher, Admin)
- **8 mobile screens** (Parent MVP)
- **14 email templates**
- **1,004 backend tests**
- **Production**: classbridge.ca (live since March 6, 2026)

---

## Table of Contents

1. [Authentication & Identity](#1-authentication--identity)
2. [Google Classroom Integration](#2-google-classroom-integration)
3. [AI Study Tools](#3-ai-study-tools)
4. [Course & Content Management](#4-course--content-management)
5. [Task Manager & Calendar](#5-task-manager--calendar)
6. [Messaging & Communication](#6-messaging--communication)
7. [Notifications System](#7-notifications-system)
8. [Parent Features](#8-parent-features)
9. [Student Features](#9-student-features)
10. [Teacher Features](#10-teacher-features)
11. [Admin Features](#11-admin-features)
12. [Performance Analytics](#12-performance-analytics)
13. [Contextual Notes System](#13-contextual-notes-system)
14. [Teacher Resource Links](#14-teacher-resource-links)
15. [Image Retention in Study Guides](#15-image-retention-in-study-guides)
16. [AI Help Chatbot](#16-ai-help-chatbot)
17. [Waitlist System](#17-waitlist-system)
18. [AI Usage Limits](#18-ai-usage-limits)
19. [Security & Compliance](#19-security--compliance)
20. [UI/UX Design System](#20-uiux-design-system)
21. [Mobile App](#21-mobile-app)
22. [Monetization & Payments](#22-monetization--payments)
23. [Pre-Launch Survey System](#23-pre-launch-survey-system)
24. [Bot Protection](#24-bot-protection)
25. [Performance Optimization](#25-performance-optimization)
26. [Course Planning (Phase 3)](#26-course-planning-phase-3)
27. [WOW Features — Parent Value & Engagement](#27-wow-features--parent-value--engagement-phase-2-march-2026)
28. [Future Phases](#28-future-phases)

---

## 1. Authentication & Identity

### 1.1 Registration & Login
**Status**: IMPLEMENTED | **Issues**: #2, #412-#414

| Feature | Description | Status |
|---------|-------------|--------|
| Email/password registration | Name, email, password, confirm password (4 fields only) | Implemented |
| JWT authentication | Access tokens (24h) + refresh tokens (30d) | Implemented |
| Google OAuth login | OAuth2 flow with CSRF state parameter | Implemented |
| Token refresh | Axios interceptor auto-refreshes on 401 | Implemented (#149) |
| Password strength validation | 8+ chars, upper, lower, digit, special char | Implemented |
| Multi-role registration | Checkbox role selection (moved to onboarding) | Implemented (#257) |

### 1.2 Post-Login Onboarding
**Status**: IMPLEMENTED | **Issues**: #412, #413, #414

Simplified registration removes role selection from signup. After first login, users see an onboarding screen:
- Role selection cards: Parent (prominent), Teacher, Student
- Teacher type sub-selection: School Teacher / Private Tutor
- Multi-role support (e.g., parent + teacher)
- `needs_onboarding` flag on User model
- `POST /api/auth/onboarding` endpoint

### 1.3 Email Verification (Soft Gate)
**Status**: IMPLEMENTED | **Issues**: #417

- Verification email with 24h JWT link sent on registration
- Users can log in without verification (no blocking)
- Dashboard yellow banner: "Please verify your email. [Resend email]"
- Google OAuth and invite-accepted users auto-verified
- `email_verified` / `email_verified_at` columns on User

### 1.4 Password Reset
**Status**: IMPLEMENTED | **Issues**: #176

- `POST /api/auth/forgot-password` — sends reset link (no user enumeration)
- `POST /api/auth/reset-password` — validates token + new password
- 1-hour JWT reset tokens, rate limited (3/min, 5/min)
- Works for all user types including OAuth/invite-only users
- Parent-managed child password reset from My Kids page

### 1.5 Multi-Role Support
**Status**: PARTIAL | **Issues**: #211, #255-#257

- `roles` column (comma-separated) + `role` (active dashboard context)
- `has_role()`, `get_roles_list()`, `set_roles()` helpers
- Role switcher dropdown in header (visible with 2+ roles)
- `POST /api/users/me/switch-role` endpoint
- Authorization checks use ALL roles, not just active role

### 1.6 Invite System
**Status**: IMPLEMENTED

Unified `invites` table for student, teacher, and parent invites:
- Token-based with configurable expiry (7d students, 30d teachers)
- `POST /api/auth/accept-invite` resolves type and creates appropriate records
- Course-aware invites auto-enroll/assign on acceptance
- Backfill `teacher_user_id` on teacher invite acceptance

---

## 2. Google Classroom Integration

**Status**: IMPLEMENTED | **Issues**: #2, #34

### 2.1 OAuth & Connection
- Google OAuth with incremental scope requests
- Scopes: classroom.courses.readonly, coursework.students.readonly, rosters.readonly, gmail.readonly, calendar.events
- Connect/disconnect from dashboard
- Multi-Google account support for teachers (`teacher_google_accounts` table)

### 2.2 Course Sync
- On-demand only (no automatic sync)
- `POST /api/google/courses/sync` — imports selected courses
- Deduplication via `google_classroom_id`
- Teacher courses synced with `teacher_id` set
- Assignment sync per course

### 2.3 Child Discovery
- Parent connects Google → "Search Google Classroom"
- Discovers students from parent's Google Classroom courses
- Parent selects which students to link (nothing automatic)
- Auto-creates student accounts with Google profile names

### 2.4 Google Classroom Types (Phase 1.5)
**Issues**: #550
- `courses.classroom_type`: "school" or "private"
- School classroom: reference-only (no document download)
- Private classroom: full access

---

## 3. AI Study Tools

### 3.1 Study Guide Generation
**Status**: IMPLEMENTED | **Issues**: #4, #16

- Generate study guides from any course material content
- Math-aware prompts with step-by-step worked solutions
- Non-blocking generation with pulsing placeholder
- Focus prompt with history persistence and K-12 content moderation (Claude Haiku)
- Image-aware: includes extracted document images in AI prompts

### 3.2 Practice Quiz Generation
**Status**: IMPLEMENTED | **Issues**: #17

- Multiple-choice quizzes from course material
- Interactive stepper UI with immediate feedback
- Quiz results saved and tracked over time
- Math-aware: numerical answer choices for math content

### 3.3 Flashcard Generation
**Status**: IMPLEMENTED | **Issues**: #18

- Flashcard pairs with flip animation
- Keyboard navigation (left/right arrows, space to flip)
- Shuffle with Fisher-Yates algorithm
- Math-aware: problems on front, worked solutions on back

### 3.4 AI Auto-Task Creation
**Status**: IMPLEMENTED | **Issues**: #195, #902, #920

- AI extracts critical dates from generated content
- Auto-creates linked tasks with appropriate priority
- `CRITICAL_DATES` section parsed from AI response
- Fallback "Review" task created when no dates found
- Today's date context included in all AI prompts

### 3.5 Quiz Results History
**Status**: IMPLEMENTED | **Issues**: #574, #621

- `POST /api/quiz-results/` — saves attempts with per-question answers
- Stats cards: Total Attempts, Unique Quizzes, Average Score, Best Score
- Score trend chart (Recharts line chart)
- Parent-to-child access with child selector

### 3.6 Print & PDF Export
**Status**: IMPLEMENTED | **Issues**: #764

- Print button opens clean print dialog (no UI chrome)
- Download PDF via `html2pdf.js` (dynamically imported)
- Works for study guides, quizzes, flashcards, documents
- Shared `exportUtils.ts` utility

### 3.7 Content Moderation
**Status**: IMPLEMENTED | **Issues**: #1001

- Focus prompt moderated via Claude Haiku safety check
- K-12 policy: blocks sexual content, violence, hate speech, self-harm, drug use, prompt injection
- Fails-open on API error, returns HTTP 400 on violation

### 3.8 Sub-Guide Generation from Text Selection (§6.100, #1594)
**Status**: IMPLEMENTED (v1) | PLANNED (v2) | **Issues**: #1594, #1817-#1820

Generate **child study guides** (study guides, quizzes, flashcards) from selected text within an existing study guide. Enables deeper topic exploration on demand.

| Feature | Status |
|---------|--------|
| Right-click context menu on selected study guide text | Implemented |
| Generate Sub-Guide Modal (Study Guide / Quiz / Flashcards type cards) | Implemented |
| Selected text as context preview in modal | Implemented |
| `POST /api/study/guides/{id}/generate-child` endpoint | Implemented |
| `GET /api/study/guides/{id}/children` endpoint | Implemented |
| Child guide shows "Generated from: [Parent Title]" link | Implemented |
| Background generation with inline status | Implemented (#1838) |
| Enhanced SelectionTooltip with "Generate Study Material" button | Planned (v2, #1817) |
| Sub-Guides collapsible section on parent guide page | Planned (v2, #1818) |
| Breadcrumb navigation for multi-level hierarchies | Planned (v2, #1819) |
| Full tree hierarchy endpoint | Planned (v2, #1820) |

**Data Model:**
- `relationship_type` column on `study_guides`: `version` (existing) vs `sub_guide` (new)
- `generation_context` column: stores the selected text used for generation

**Components:** `TextSelectionContextMenu`, `GenerateSubGuideModal`, `SelectionTooltip`

### 3.9 Study Guide Strategy Pattern (§6.106, #1972)
**Status**: IMPLEMENTED | **Issues**: #1972, #1985, #1987, #1989

Document type classification and study goal selection to produce persona-based, contextually-aware AI study output.

| Feature | Description | Status |
|---------|-------------|--------|
| Document type classification | Claude Haiku classifies uploaded documents into 8 types | Implemented |
| Study goal selection | 7 study goal options in upload wizard Step 2 | Implemented |
| AI output structured by type | Prompts vary based on document type + study goal | Implemented |
| Strategy context in sub-guides | Sub-guide generation inherits parent strategy context | Implemented (#1989) |

**Document Types:** teacher_notes, course_syllabus, past_exam, mock_exam, project_brief, lab_experiment, textbook_excerpt, custom

**Study Goals:** upcoming_test, final_exam, assignment, lab_prep, general_review, discussion, parent_review

**Components:** `DocumentTypeSelector`, `StudyGoalSelector` (wired into `UploadWizardStep2`)

---

## 4. Course & Content Management

### 4.1 Course CRUD
**Status**: IMPLEMENTED | **Issues**: #91

| Creator Role | Visibility | Teacher ID |
|-------------|------------|------------|
| Parent | Private to linked children | NULL |
| Student | Visible to student only | NULL |
| Teacher | Visible to enrolled students | Set to teacher ID |

- `POST /api/courses/` — all roles can create
- `PATCH /api/courses/{id}` — creator/admin edit
- `is_private`, `is_default`, `created_by_user_id` fields
- Default "My Materials" course auto-created per user

### 4.2 Course Content / Materials
**Status**: IMPLEMENTED | **Issues**: #194

- Structured content items with 7 types: notes, syllabus, labs, assignments, readings, resources, other
- Upload: PDF, Word, PPTX, text notes, images, ZIP
- Multi-file upload: up to 10 files, 20 MB each, combined into one material
- Google Cloud Storage integration for production with SourceFile tracking (#1841)
- Backfill migration for existing materials; original filenames as material titles
- Magic bytes validation prevents extension spoofing
- OCR for embedded images in .docx files (Tesseract)
- Tabbed detail view: Document | Study Guide | Quiz | Flashcards | Videos & Links

### 4.3 Course Materials Lifecycle
**Status**: IMPLEMENTED | **Issues**: §6.25

- Soft delete (archive) with `archived_at` timestamp
- Bulk archive button on class materials and CourseDetailPage (#1846, #1849, #1856)
- Cascade archive/restore/delete to sub-materials
- Archive list with restore and permanent delete
- On-access auto-archive after 1 year
- On-access permanent delete after 7 years
- `last_viewed_at` tracking
- Auto-archive linked study guides when source content changes
- Regeneration prompt after content edit

### 4.4 Course Enrollment
**Status**: IMPLEMENTED | **Issues**: #225, #250, #251

| Action | Status |
|--------|--------|
| Teacher enrolls student by email | Implemented |
| Teacher removes student | Implemented |
| Parent assigns course to child | Implemented |
| Parent unassigns course from child | Implemented |
| Student self-enrolls | Implemented |
| Student unenrolls self | Implemented |

### 4.5 Course Detail Page
**Status**: IMPLEMENTED

- Course header with badges (privacy, Google Classroom)
- Course materials CRUD (creator/admin)
- Upload document with drag-and-drop
- Optional study material generation on upload
- Student roster management (teacher view)
- Assignment section with create/edit/delete

### 4.6 Material Hierarchy — Master/Sub Architecture (§6.98, #1740)
**Status**: IMPLEMENTED | **Issues**: #1740, #1804, #1809, #1815, #1822, #1841, #1849

When uploading multiple documents, the system creates a **master Class Material** and one **sub Class Material per attachment**, forming a parent-child hierarchy. This enables per-section study tool generation when combined content exceeds AI context limits.

**Hierarchy Rules:**

| Scenario | Result |
|----------|--------|
| 1 file uploaded | Standalone material (no hierarchy) |
| N files, no pasted text | First file = master, remaining = sub-materials |
| N files + pasted text | Master holds pasted text, all N files = sub-materials |
| More than 10 files | Validation error — upload rejected |

**Data Model:**
- `parent_content_id` — Self-referencing FK; subs point to master, master is NULL
- `is_master` — `"true"/"false"` (string for SQLite/PostgreSQL cross-DB compatibility)
- `material_group_id` — Timestamp-based group ID linking master + all subs
- `display_order` — Order of sub-materials within hierarchy

**Sub-Material Naming:** Auto-named as "Master Title — Part 1", "Part 2", etc. (user-editable)

**AI Generation:** At upload time, generation triggered **only for master**. Sub-materials generate on demand post-upload.

**UI — Linked Materials Panel:**
- Collapsible panel at top of all tabs (Document, Study Guide, Quiz, Flashcards)
- Master view: lists all sub-materials as clickable links
- Sub view: lists master + all sibling subs
- Seamless back-and-forth navigation

**Key Endpoints:**
- `POST /api/course-contents/upload-multi` — Multi-file upload (max 10 files, 100 MB total)
- `GET /api/course-contents/{id}/linked-materials` — Get all materials in group

### 4.7 Post-Creation Material Management (§6.99, #993)
**Status**: IMPLEMENTED | **Issues**: #993

Extends the material hierarchy (§6.98) for post-upload file management.

| Feature | Endpoint | Description |
|---------|----------|-------------|
| Add files | `POST /{id}/add-files` | Max 10 files; promotes standalone → master if needed |
| Reorder subs | `PUT /{id}/reorder-subs` | Updates `display_order` on sub-materials |
| Delete sub | `DELETE /{id}/sub-materials/{sub_id}` | Cascades to SourceFiles, images, study guides; demotes master if last sub |
| Replace file | `PUT /{id}/replace-file` | Deletes old file, re-extracts text/images, archives linked study guides |

---

## 5. Task Manager & Calendar

### 5.1 Task CRUD
**Status**: IMPLEMENTED | **Issues**: #100, #107, #210

- Fields: title, description, due date, reminder, priority (low/medium/high), category
- Cross-role assignment with relationship verification
- Entity linking: course, course content, study guide, assignment
- Soft delete with archive/restore/permanent delete
- Task Detail Page with linked resources section
- Inline edit mode on Task Detail Page

### 5.2 Calendar
**Status**: IMPLEMENTED | **Issues**: #45, #207, #691

- Month / Week / 3-Day / Day views (Recharts)
- Tasks and assignments with color-coded entries
- Drag-and-drop task rescheduling (HTML5 DnD)
- Day Detail Modal with full CRUD
- Calendar popover for quick task details
- Moved from Dashboard to Tasks page (#691)
- Default collapsed with item count badge

### 5.3 Task Reminders
**Status**: IMPLEMENTED | **Issues**: #112

- APScheduler daily job at 8:00 AM
- Configurable `task_reminder_days` per user (default "1,3")
- `TASK_DUE` notification type
- Dedup via title+link matching

### 5.4 Due Date Filters
**Status**: IMPLEMENTED | **Issues**: #208, #209

- URL parameter: `?due=overdue|today|week`
- Assignee dropdown filter
- Dashboard status cards link to filtered task views

---

## 6. Messaging & Communication

### 6.1 Parent-Teacher Messaging
**Status**: IMPLEMENTED | **Issues**: #8

- Conversation-based threading
- Valid recipients based on relationships (parent ↔ teacher via enrolled courses)
- Direct teacher linking (bypasses course enrollment requirement)
- Admin users always included as valid recipients

### 6.2 Message Email Notifications
**Status**: IMPLEMENTED | **Issues**: §6.27

- Email sent to recipient on new message (if `email_notifications` enabled)
- In-app notification with sender name and message preview
- 5-minute dedup window to prevent spam
- ClassBridge branded email template

### 6.3 Admin Messaging
**Status**: IMPLEMENTED | **Issues**: #258, #259, #261-#263

- **Broadcast**: `POST /api/admin/broadcast` — all users + email
- **Individual**: `POST /api/admin/users/{user_id}/message`
- **User-to-admin**: Any user can message any admin
- All admins receive cross-notifications on user messages
- Broadcast history with view/reuse/resend

### 6.4 Teacher Email Monitoring
**Status**: IMPLEMENTED | **Issues**: #33

- Gmail integration for teacher email monitoring
- Google Classroom announcement monitoring
- AI-powered email summarization
- Paginated list with type filter and search
- Manual sync trigger + background sync job

---

## 7. Notifications System

### 7.1 In-App Notifications
**Status**: IMPLEMENTED | **Issues**: #20, #23

- NotificationBell dropdown in header
- Types: MESSAGE, TASK_DUE, SYSTEM, LINK_REQUEST, MATERIAL_UPLOADED, STUDY_GUIDE_CREATED, etc.
- Mark as read / Mark all as read / Delete
- Click notification → popup modal (#261, partial)

### 7.2 Email Notifications
**Status**: IMPLEMENTED | **Issues**: #21

- 14 email templates in `app/templates/`
- SendGrid primary + Gmail SMTP fallback
- Role-based inspirational message footer on all emails
- Templates: password_reset, message_notification, task_reminder, welcome, email_verification, teacher_invite, teacher_linked_notification, student_course_invite, parent_invite, waitlist_* (5), email_verified_welcome

### 7.3 Notification Preferences
**Status**: IMPLEMENTED

- `email_notifications` preference (opt-out)
- `task_reminder_days` configurable per user
- `GET/PUT /api/notifications/settings`

### 7.4 Multi-Channel Notifications (Phase 1.5)
**Issues**: #548

- 3 channels: in-app bell, email, ClassBridge message
- ACK system with persistent reminders (24h until acknowledged)
- Notification suppression per source
- Background reminder job every 6 hours

---

## 8. Parent Features

### 8.1 Parent Dashboard (v3.1)
**Status**: IMPLEMENTED | **Issues**: #540-#544, #557, #688, #692

**Design Principles:**
- No scroll / single viewport at 1080p
- Urgency-first: overdue → due today → upcoming
- Progressive disclosure
- Single child selection model (pills)

**Layout:**
1. **Icon-only sidebar** — Always icon-only on desktop, hamburger on mobile
2. **Child filter pills** — Toggle selection (no "All Children" button)
3. **Today's Focus header** — Greeting + urgency badges + inspiration quote
4. **Alert banner** — Red (overdue) + amber (pending invites)
5. **Quick actions** — + icon popover (Upload Documents, New Task)
6. **Collapsible student detail panel** — Courses, materials, tasks by urgency
7. **Calendar** — Moved to Tasks page (#691)

### 8.2 My Kids Page
**Status**: IMPLEMENTED | **Issues**: #236, #237, #301, #700

- Colored child avatars with initials (8-color palette)
- Enhanced child cards: avatar, stats, progress bar, deadline countdown
- Quick actions: Courses, Tasks, Edit
- + icon popover for Add Child, Add Class, Class Materials, Quiz History
- Teachers section with Add Teacher modal
- Parent-managed child password reset

### 8.3 Parent-Child Linking
**Status**: IMPLEMENTED | **Issues**: #35-#38, #547

- Path 1: Create child with name only (no email required)
- Path 2: Link existing student by email (with LinkRequest approval for active students)
- Path 3: Google Classroom discovery
- Many-to-many via `parent_students` join table

### 8.4 Parent Navigation
**Status**: IMPLEMENTED | **Issues**: #206, #529, #530

Sidebar items: Overview | Child Profiles | Courses | Course Materials | Tasks | Messages | Tutorial | Help

### 8.5 Parent UX Simplification
**Status**: IMPLEMENTED | **Issues**: #201-#206

- Single dashboard API endpoint (replaces 5+ waterfall calls)
- Status-first dashboard (replaces calendar-dominant layout)
- One-click study generation
- Filter cascade fix
- Modal nesting reduction

---

## 9. Student Features

### 9.1 Student Dashboard (v2 — "Focused Command Center")
**Status**: IMPLEMENTED | **Issues**: #708

**Layout:**
1. **Hero section** — Greeting + urgency pills + stat chips
2. **Notification alerts** — Parent/teacher request cards
3. **Quick actions** — Upload Materials, Create Course, Generate Study Guide, Sync Classroom
4. **Coming Up timeline** — Unified assignments + tasks (next 7 days)
5. **Recent materials** + course chips
6. **Onboarding card** for new students

### 9.2 Student Dashboard v3 — Study Hub
**Issues**: #1022-#1029

- Navigation: Home, Study, Tasks, Messages, Help (5 items)
- Study Hub (`/study`): course list + materials per course + upload + quiz stats
- Tasks grouped by urgency: Overdue / Today / This Week / Later

### 9.3 Student Self-Enrollment
**Status**: IMPLEMENTED | **Issues**: #250, #251

- Browse available courses
- `POST /api/courses/{id}/enroll` — rejects private courses
- `DELETE /api/courses/{id}/enroll` — unenroll

---

## 10. Teacher Features

### 10.1 Teacher Dashboard
**Status**: PARTIAL

- Courses teaching list with student counts
- Manual course creation
- Multi-Google account management
- Messages section
- Teacher communications (email monitoring)

### 10.2 Course Roster Management
**Status**: IMPLEMENTED | **Issues**: #225-#227

- Add students by email (creates invite if not registered)
- Remove students from courses
- Assign teacher to course during creation/editing
- Course-aware invites (auto-enroll on acceptance)

### 10.3 Manual Assignment Creation
**Status**: IMPLEMENTED | **Issues**: #49

- Full CRUD: `POST/PUT/DELETE /api/assignments/`
- Student notifications on new assignment
- Overdue badge + Google Classroom badge
- Create/Edit/Delete hidden for GC-synced assignments

### 10.4 Teacher Types
**Status**: IMPLEMENTED

- **School Teacher**: Via Google Classroom sync, may or may not be on EMAI
- **Private Tutor**: Independent educator, creates own courses
- Shadow + invite flow for non-EMAI school teachers

### 10.5 Teacher Invites
**Status**: PARTIAL | **Issues**: #252-#254

- Teacher invites parent to ClassBridge (implemented)
- Invite email templates for unregistered/registered teachers
- Resend/re-invite on demand (not implemented, #253)

---

## 11. Admin Features

### 11.1 Admin Dashboard
**Status**: IMPLEMENTED

- Platform stats (users, courses, study guides)
- User management table: search, filter by role, pagination
- Role management

### 11.2 Audit Logging
**Status**: IMPLEMENTED | **Issues**: §6.14

- Tracks: login, register, CRUD operations, Google sync
- `audit_logs` table with user_id, action, resource_type, IP, user_agent
- `GET /api/admin/audit-logs` — paginated, filterable
- Admin UI at `/admin/audit-log`

### 11.3 Inspiration Messages
**Status**: IMPLEMENTED | **Issues**: #230-#233

- Role-specific motivational messages (20 per role)
- JSON seed files, database storage
- Admin CRUD at `/admin/inspiration`
- Displayed in dashboard greeting and email footers

### 11.4 Admin Waitlist Management
**Status**: IMPLEMENTED | **Issues**: #1115

- Summary stats bar (Total, Pending, Approved, Registered, Declined)
- Filterable table with bulk approve
- Admin notes, send reminders

### 11.5 Admin AI Usage Management
**Status**: IMPLEMENTED | **Issues**: #1121

- 3-tab panel: Overview, Usage History, Credit Requests
- Adjust limits, reset counts, view per-user history
- Approve/decline credit requests

### 11.6 Admin Email Template Management
**Status**: NOT IMPLEMENTED | **Issues**: #513

- View/edit HTML email templates from admin dashboard
- DB override → filesystem fallback
- Live preview with sample data
- Phase 2

### 11.7 Broadcast History Enhancement
**Status**: NOT IMPLEMENTED | **Issues**: #514

- View full broadcast body, reuse, resend
- Phase 2

---

## 12. Performance Analytics

**Status**: IMPLEMENTED | **Issues**: #469-#474

### Data Pipeline
- `grade_records` table (student_id, course_id, grade, percentage, source)
- Google Classroom sync → StudentAssignment → GradeRecord
- Seed service: 26 demo records across 3 courses

### Analytics Service
- `compute_summary()` — overall + per-course averages, trend, completion rate
- `compute_trend_points()` — chronological data points
- `generate_ai_insight()` — on-demand OpenAI analysis
- `get_or_create_weekly_report()` — cached weekly report (24h TTL)

### Frontend
- `/analytics` page with Recharts: LineChart (trends), BarChart (course averages)
- Summary cards: average, completion, graded count, trend badge
- Child selector for parents, time range + course filters
- AI insights panel (on-demand to manage API costs)

---

## 13. Contextual Notes System

**Status**: IMPLEMENTED | **Issues**: #1084-#1090, #1179

### Core
- One note per user per course material (upsert semantics)
- Auto-save with 1s debounce
- Floating draggable panel UX
- Task creation from notes (quick task or linked task)

### Text Selection to Notes
- `useTextSelection` hook detects highlighted text
- "Add to Notes" floating amber pill
- Blockquote insertion with auto-save
- Persistent yellow highlight rendering on study guides
- Click-to-remove highlight
- Parent read-only view of child's highlights/notes
- Per-user highlight isolation

### Components
- `NotesPanel` — Floating, draggable, closable panel
- `NotesFAB` — Persistent bottom-right floating action button
- `SelectionTooltip` — Floating pill near text selection

---

## 14. Teacher Resource Links

**Status**: IMPLEMENTED | **Issues**: #1319-#1326

### Features
- Auto-extract URLs from uploaded documents and teacher communications
- YouTube URL normalization (youtube.com, youtu.be, embed formats)
- YouTube oEmbed enrichment (title, thumbnail)
- Topic-based grouping from document formatting
- "Videos & Links" tab on Course Material Detail page
- Embedded YouTube players with topic sections
- Manual link add/edit/delete

### Data Model
- `resource_links` table: url, resource_type, title, topic_heading, thumbnail_url, youtube_video_id

---

## 15. Image Retention in Study Guides

**Status**: IMPLEMENTED | **Issues**: #1308-#1313

### Pipeline
1. **Extract** — Images from PDF/DOCX/PPTX during upload
2. **Store** — `content_images` table (BLOB, compressed to max 800px)
3. **Describe** — Reuse Vision OCR descriptions (no new AI cost)
4. **Prompt** — Include image metadata in AI prompts (`[IMG-N]` markers)
5. **Render** — `AuthImage` component fetches via authenticated Axios
6. **Fallback** — Unplaced images in "Additional Figures" section

### Cost Impact
- +5-10% per generation ($0.035-0.055 vs $0.03-0.05)
- No new AI API calls (reuses existing Vision OCR)

---

## 16. AI Help Chatbot

**Status**: IMPLEMENTED | **Issues**: #1355-#1363, #1779, #1778, #1921

### Architecture
- RAG-powered: embed query → vector search → LLM response
- Expanded YAML knowledge base with additional articles (#1779, #1778, #1921)
- Fixed chatbot search gaps and broken links (§6.103 requirements)
- Claude API for chat (switched from OpenAI, #1378)
- In-memory vector store (cosine similarity <10ms)
- Rate limited: 30 requests/hour per user

### Widget UX
- Bottom-right FAB (56px circle), above NotesFAB
- 380x520px panel (desktop), full-width bottom sheet (mobile)
- Welcome message with role-based suggestion chips
- Context-aware chips based on current page
- Markdown rendering, video embeds (YouTube/Loom)
- Session-only messages (no DB persistence)

### What It Is NOT
- Not a general AI chatbot (ClassBridge help only)
- No user data access (no courses, grades, messages)
- No persistent conversation history
- No proactive popups

---

## 17. Waitlist System

**Status**: IMPLEMENTED | **Issues**: #1106-#1115, #1124

### Flow
1. Landing page (`/`) → "Join Waitlist" CTA
2. Waitlist form (`/waitlist`) → name, email, role checkboxes
3. Confirmation email sent to user + admin notification
4. Admin reviews → approve/decline
5. Approval email with invite token (14-day expiry)
6. Token-gated registration (`/register?token=`)

### Admin Panel
- Summary stats bar (Total, Pending, Approved, Registered, Declined)
- Filterable table with bulk approve
- Remind, re-approve, admin notes

### Feature Flag
- `WAITLIST_ENABLED` env var (default: true for Phase 1, false for Phase 2)

---

## 18. AI Usage Limits

**Status**: IMPLEMENTED | **Issues**: #1116-#1121

### Quota System
- Default: 10 AI generations per user
- `ai_usage_count` / `ai_usage_limit` on User model
- Warning at 80% usage (2 remaining)
- Limit reached → "Request More" flow

### Credit Request Flow
1. User submits request (amount + reason)
2. Admin notification
3. Admin approves/declines with amount
4. User's `ai_usage_limit` increased

### API
- `GET /api/ai-usage` — current usage
- `POST /api/ai-usage/request` — request more credits
- `GET /api/admin/ai-usage` — all users with stats
- `PATCH /api/admin/ai-usage/requests/{id}/approve` — approve with amount

---

## 19. Security & Compliance

### 19.1 Security Hardening Phase 1
**Status**: IMPLEMENTED | **Issues**: #176-#184

| Area | Fix |
|------|-----|
| JWT Secret Key | No hardcoded default; crashes in prod if not set (#179) |
| Admin Self-Registration | Blocked admin from public registration (#176) |
| CORS | Explicit origin allowlist, no `*` (#177) |
| Google OAuth | CSRF state parameter, server-side token storage (#178) |
| RBAC Gaps | 12 permission gates updated across 6 route files (#181) |
| Logging | Auth required, input validation (#182) |
| Student Passwords | `UNUSABLE_PASSWORD_HASH` sentinel for invite-pending (#182) |

### 19.2 Security Hardening Phase 2
**Status**: IMPLEMENTED | **Issues**: #140, #141, #184

| Area | Fix |
|------|-----|
| Rate Limiting | `slowapi` on auth (5/min), AI (10/min), upload (20/min) (#140) |
| Security Headers | HSTS, CSP, X-Frame-Options, X-Content-Type-Options (#141) |
| LIKE Injection | Escaped `%` and `_` wildcards in search terms (#184) |
| Bot Protection | Honeypot hidden field + minimum completion time validation (#1934, #1935) |

**Bot protection** applied to all public forms: survey, waitlist signup, registration, login.

### 19.3 Compliance
- **Standards**: FERPA, MFIPPA, PIPEDA, GDPR
- **Audit logging**: All sensitive actions logged
- **Data retention**: 1-year auto-archive, 7-year permanent delete
- **Future**: Account deletion, data export, consent management

---

## 20. UI/UX Design System

### 20.1 Theme System
**Status**: IMPLEMENTED

| Theme | Accent | Description |
|-------|--------|-------------|
| Light (default) | Teal (#49b8c0) | Clean, bright UI |
| Dark | Purple (#8b5cf6) / Cyan (#22d3ee) | Deep dark with glow |
| Focus | Sage (#5a9e8f) / Amber (#c47f3b) | Warm muted tones for study |

- 50+ CSS custom properties with per-theme overrides via `[data-theme]`
- `ThemeContext.tsx` with `useTheme()` hook
- OS preference auto-detection via `prefers-color-scheme`
- Persisted to `localStorage`

### 20.2 Design Philosophy
Inspired by Canadian consumer-tech leaders:

| Principle | Inspired By | Application |
|-----------|-------------|-------------|
| Clarity over cleverness | Shopify Admin | Every element earns its place |
| Warm minimalism | Wealthsimple | Supportive, not clinical |
| Progressive disclosure | Figma | Show what matters now |
| Contextual intelligence | Notion | Right info, right time, right role |
| Forgiving design | Stripe Dashboard | Undo over confirm |

### 20.3 Layout (turbo.ai-inspired)
**Status**: PARTIAL | **Issues**: #198-#200, #557

- Icon-only sidebar with hover tooltips (always collapsed on desktop)
- Hamburger overlay on mobile (<768px)
- Simplified header: logo + search + notifications + avatar
- `DashboardLayout` shared component for all roles

### 20.4 Component Library

| Component | Purpose |
|-----------|---------|
| `ConfirmModal` + `useConfirm` | Custom confirmation dialogs (replaces browser `confirm()`) |
| `AddActionButton` | 40x40px + icon popover (Dashboard, Tasks, My Kids, Course Material Detail) |
| `PageSkeleton` / `ListSkeleton` / `CardSkeleton` | Loading skeleton animations |
| `ErrorBoundary` | Graceful render error catching |
| `ToastProvider` + `useToast()` | Success/error/info notifications |
| `GlobalSearch` | Ctrl+K search across courses, guides, tasks, content |
| `CalendarView` | Month/Week/3-Day/Day with drag-and-drop |
| `NotesPanel` + `NotesFAB` | Floating draggable notes |
| `HelpChatbot` | RAG-powered help widget |
| `ContentCard` + `AuthImage` | Markdown rendering with authenticated images |
| `LottieLoader` | Animation loader (Phase 2, #424) |

### 20.5 Logo & Branding
**Status**: IMPLEMENTED | **Issues**: #308, #309, #427

| Logo Type | Usage | Theme Support |
|-----------|-------|---------------|
| Auth Logo (280px) | Login, Register, Reset Password | Transparent BG (all themes) |
| Header Icon (80px) | Dashboard header | Transparent BG (all themes) |
| Landing Hero Logo (300px) | Landing page hero | N/A |
| Favicons | Browser tab, PWA | Multiple formats (PNG, ICO, SVG) |

### 20.6 Flat (Non-Gradient) Style
**Status**: NOT IMPLEMENTED | **Issues**: #486-#489

- Default flat/solid buttons, tabs, backgrounds
- Gradient available as opt-in toggle (low priority)
- 30+ gradient instances across 14 CSS files to replace

### 20.7 Design Consistency Initiative
**Status**: NOT IMPLEMENTED | **Issues**: #1246-#1254

- Universal page shell (`DashboardLayout` + `PageNav`)
- Shared CSS patterns: `.btn-primary`, `.section-card`, `.list-row`, `.empty-state`
- Page migration to shared patterns
- CSS cleanup and orphan removal

### 20.8 Upload Modal Redesign (Two-Step Wizard)
**Status**: NOT IMPLEMENTED | **Issues**: §6.28

- Step 1: Add material (file drop zone, paste text, class selector)
- Step 2: Generate study tools (card-based tool selection)
- "Just Upload" shortcut to skip AI tools
- Progressive wizard with slide animation

### 20.9 UI/UX Polish (March 2026)
**Status**: IMPLEMENTED

| Fix | Issue |
|-----|-------|
| Sidebar `position:fixed` to prevent hover layout shift | #1922 |
| Wizard class dropdown filtered by selected child | #1923 |
| Child selector on upload modal for course-materials page | #1907 |
| Consistent generation spinners across AI tools | #1904 |
| FAB Class Material opens UploadMaterialWizard inline | #1931 |
| Recent Activity panel expands in simplified view | #1945 |
| Create Class button visible text CTA | #1950 |
| MyKidsPage upload modal child selector + class filtering | #1952 |

### 20.10 Mobile Responsive
**Status**: PARTIAL | **Issues**: #152

- CSS breakpoints: 600px, 768px, 1024px
- 15/20 CSS files have `@media` breakpoints
- 44px minimum touch targets
- Full-screen modals on small screens

### 20.11 Interactive Tutorials
**Status**: IMPLEMENTED | **Issues**: #1208-#1210

- Role-based tutorial pages at `/tutorial`
- Step-by-step viewer with progress dots
- Parent: 9 steps, Student: 9 steps, Teacher: 6 steps, Admin: 6 steps
- SVG placeholder illustrations (real screenshots planned, #1209)

---

## 21. Mobile App

**Status**: PARENT MVP COMPLETE | **Issues**: #364-#380

### Tech Stack
- React Native 0.81.5 + TypeScript + Expo SDK 54
- React Navigation 7 + TanStack React Query 5
- Expo Go distribution (no App Store for pilot)

### Screens (8 total)

| Screen | API Endpoint |
|--------|-------------|
| ParentDashboard | `GET /api/parent/dashboard` |
| ChildOverview | `GET /api/parent/children/{id}/overview` |
| Calendar | Dashboard assignments + tasks |
| MessagesList | `GET /api/messages/conversations` |
| Chat | `GET /api/messages/conversations/{id}` |
| Notifications | `GET /api/notifications/` |
| Profile | `GET /api/auth/me` |
| Login | `POST /api/auth/login` |

### Mobile Boundary
- **Mobile**: View dashboard, child details, calendar, messages, notifications, mark tasks complete
- **Web only**: Registration, course management, study material generation, teacher linking, admin functions

### Post-Pilot Roadmap
- Phase 3: Push notifications, offline caching, API versioning
- Phase 4: Student + teacher screens, camera upload, App Store launch

---

## 22. Monetization & Payments

**Status**: NOT IMPLEMENTED | **Issues**: #1384-#1392

### Subscription Tiers

| Tier | Price | AI Credits/Month |
|------|-------|-----------------|
| Free | $0 | 10 (auto-reset) |
| Plus | $5/mo | 500 |
| Unlimited | $10/mo | Unlimited |

### Credit Packs (a la carte)

| Pack | Credits | Price |
|------|---------|-------|
| Starter | 50 | $2.00 |
| Standard | 200 | $5.00 |
| Bulk | 500 | $10.00 |

### Digital Wallet
**Status**: IMPLEMENTED | **Issues**: #1854

- Credit package system with tiers
- Transaction tracking
- Wallet balance management

### Planned Components
- **Stripe Integration**: Customer creation, webhooks, Checkout, Customer Portal
- **Invoice Module**: Auto-increment numbers, line items, 13% HST, branded PDF

---

## 23. Pre-Launch Survey System

**Status**: IMPLEMENTED | **Issues**: #1890-#1894

### Survey Flow
1. Public survey page at `/survey` with role selection (parent / student / teacher)
2. 8-10 role-specific questions per audience
3. Question types: `single_select`, `multi_select`, `likert`, `likert_matrix`, `free_text`
4. Session-based anonymous responses with `sessionStorage` persistence
5. Waitlist link presented after survey completion

### Bot Protection
- Honeypot hidden field + minimum completion time validation (#1934, #1935)

### Admin Analytics Dashboard
- Response analytics with horizontal bar charts, pie charts, matrix views
- Admin email + in-app notifications on survey completion
- Per-question breakdown by role

---

## 24. Bot Protection

**Status**: IMPLEMENTED | **Issues**: #1934, #1935

- Honeypot hidden field (invisible to users, traps bots)
- Minimum completion time validation (rejects instant submissions)
- Applied to all public forms: survey, waitlist signup, registration, login

---

## 25. Performance Optimization

**Status**: IMPLEMENTED | **Issues**: #1954-#1967

### Backend Optimizations
| Optimization | Detail |
|-------------|--------|
| N+1 query elimination | Eager loading (`selectinload`) across 7 route files |
| Database indexes | 16 new indexes across 11 models |
| Connection pooling | PostgreSQL `pool_size=10`, `max_overflow=20`, `pool_pre_ping` |
| Token blacklist cache | In-memory cache (60s TTL), eliminates per-request DB query |
| Dashboard pagination | Tasks capped at 20, conversations at 10 |
| Batch enrollment API | Single call replaces N individual enrollment status checks |

### Frontend Optimizations
| Optimization | Detail |
|-------------|--------|
| Axios timeout | 30s default, 120s for AI/upload operations |
| Visibility-aware polling | `usePageVisible` hook pauses polling when tab hidden |
| Affected components | NotificationBell, MessagesPage, useAIUsage |

### Requirements
- Section 10.0 Performance Standards added to REQUIREMENTS.md

---

## 26. Course Planning (Phase 3)

**Status**: NOT IMPLEMENTED | **Issues**: #500-#508, #511

### Features
- **School board integration** — TDSB, PDSB, YRDSB, HDSB, OCDSB catalogs
- **Course catalog** — Board-specific, prerequisite chains, streams
- **Academic plans** — Multi-year (Grade 9-12) with semester rows
- **Graduation engine** — OSSD requirements validation (30 credits, compulsory checklist)
- **AI recommendations** — Board-specific, goal-aware course suggestions
- **University alignment** — Map plans to university program requirements
- **Semester planner** — Browse courses, prerequisite indicators, workload balance
- **Multi-year planner** — 4-column grid with drag-and-drop

---

## 27. WOW Features — Parent Value & Engagement (Phase 2, March 2026)

Features addressing pilot feedback: *"I don't see a WOW factor."* Core principle: **Parents First, Responsible AI.**

### 27.1 Smart Daily Briefing (§6.61, #1403)
Proactive daily summary telling parents what matters today across all children. Pure SQL aggregation ($0 AI cost). Optional morning email digest via SendGrid.

### 27.2 Help My Kid — One-Tap Study Actions (§6.62, #1407)
Parent sees upcoming test → taps "Help Study" → AI generates practice material → child gets notification. Source material linking via self-referential FK on `study_guides` (no new tables).

### 27.3 Global Search + Smart Shortcuts (§6.17, #1410)
Unified search (Ctrl+K) with SQL ILIKE ($0 cost). Smart presets: "due" → shows overdue items; child name → child snapshot. Action buttons on results for AI generation.

### 27.4 Weekly Progress Pulse (§6.63, #1413)
Sunday evening email digest: per-child completed/overdue/upcoming summary. Pure SQL + SendGrid ($0).

### 27.5 Parent-Child Study Link (§6.64, #1414)
Bidirectional feedback loop: parent generates quiz → child notified → child completes → parent sees score + weak areas.

### 27.6 Dashboard Redesign (§6.65, #1415)
Clean, persona-based layouts with 3-section max per role:
- Parent v5: Daily Briefing + Child Snapshot + Quick Actions
- Student v4: Coming Up + Recent Study + Quick Actions
- Teacher v2: Student Alerts + My Classes + Quick Actions
- Admin v2: Platform Health + Recent Activity + Quick Actions

### 27.7 Responsible AI Parent Tools (§6.66, #1421)

| Tool | For Parent | For Student | AI Cost |
|------|-----------|-------------|---------|
| **"Is My Kid Ready?"** | Readiness score + gap areas | Must answer 5 questions | ~$0.02 |
| **Parent Briefing Notes** | Plain-language topic summary | Never sees it | ~$0.01 |
| **Practice Problem Sets** | "I gave extra practice" | Must solve problems | ~$0.02 |
| **Weak Spot Report** | Trends over time | Sees own progress | $0.00 |
| **Conversation Starters** | Dinner table prompts | N/A | ~$0.005 |

**Revised Help Study Menu:** Primary = Quick Assessment, Practice Problems, Parent Briefing. Secondary = Quiz, Study Guide, Flashcards.

## 28. Future Phases

### Phase 2+: TeachAssist Integration + Polish
- TeachAssist grade import
- Admin email template management (#513)
- Broadcast history enhancement (#514)
- Lottie animation loader (#424)
- Show/hide password toggle (#420)
- Welcome & verification emails (#509, #510)

### Phase 3: Course Planning
- Full Ontario OSSD course planning system (§6.47)

### Phase 4: Tutor Marketplace
- Tutor profiles, search, recommendations
- Booking workflow
- Payment integration
- Extends `teacher_type=private_tutor` (no new role)

### Phase 5: AI Email Communication Agent
- Compose messages inside ClassBridge
- AI formats and sends email to teacher
- AI-powered reply suggestions
- Searchable email archive

---

## Appendix A: API Endpoint Summary

**Total implemented endpoints: 80+**

Key endpoint groups:
- `/api/auth/*` — Registration, login, token refresh, onboarding, email verification
- `/api/google/*` — OAuth, course sync, assignment sync
- `/api/courses/*` — CRUD, enrollment, roster
- `/api/course-contents/*` — CRUD, upload, images, links
- `/api/study/*` — Generate study guide/quiz/flashcards, manage guides
- `/api/tasks/*` — CRUD, assignable users
- `/api/messages/*` — Conversations, recipients, unread count
- `/api/notifications/*` — CRUD, settings, unread count
- `/api/parent/*` — Children, linking, dashboard, teacher linking
- `/api/analytics/*` — Grades, summary, trends, AI insights
- `/api/notes/*` — CRUD, children access
- `/api/admin/*` — Users, stats, audit logs, broadcast, waitlist, AI usage
- `/api/ai-usage/*` — Usage stats, credit requests
- `/api/waitlist/*` — Join, verify token
- `/api/help/*` — Chatbot RAG endpoint
- `/api/search` — Global search
- `/api/inspiration/*` — Random message, admin CRUD
- `/api/quiz-results/*` — Save, list, stats
- `/api/resource-links/*` — Edit, delete
- `/api/survey/*` — Public survey questions, submit responses, admin analytics
- `/api/wallet/*` — Balance, transactions, credit packages

## Appendix B: Data Model Summary

**Total tables: 30+**

| Table | Purpose |
|-------|---------|
| users | All user accounts |
| students | Student profile records |
| teachers | Teacher profile records |
| parent_students | Many-to-many parent-student links |
| courses | Course records |
| student_courses | Student enrollment |
| assignments | Google Classroom + manual assignments |
| course_contents | Course materials (documents) |
| study_guides | AI-generated study materials |
| tasks | Task/todo items |
| conversations | Message threads |
| messages | Individual messages |
| notifications | In-app notifications |
| audit_logs | Security audit trail |
| invites | Unified invite system |
| teacher_google_accounts | Multi-Google account support |
| student_teachers | Direct parent-teacher linking |
| grade_records | Grade data for analytics |
| progress_reports | Cached weekly reports |
| inspiration_messages | Motivational quotes |
| notes | Contextual notes |
| resource_links | Extracted URLs from documents |
| content_images | Images extracted from documents |
| waitlist | Pre-launch waitlist |
| ai_limit_requests | AI credit requests |
| quiz_results | Quiz attempt history |
| broadcasts | Admin broadcast history |
| link_requests | Parent-student approval linking |
| notification_suppressions | Per-source notification muting |
| survey_questions | Pre-launch survey questions per role |
| survey_responses | Anonymous survey response data |
| source_files | Multi-file upload tracking (GCS) |
| wallet_transactions | Digital wallet credit transactions |
| token_blacklist | JWT token blacklist with in-memory cache |

## Appendix C: Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.13+, SQLAlchemy 2.0, Pydantic 2.x |
| Frontend | React 19, TypeScript, Vite, React Router 7, TanStack React Query |
| Mobile | React Native 0.81.5, Expo SDK 54, TypeScript |
| Database | SQLite (dev), PostgreSQL (prod) |
| AI | OpenAI (gpt-4o-mini), Claude (Haiku for moderation, API for chatbot) |
| Auth | JWT (access + refresh), OAuth2, Google OAuth |
| Email | SendGrid + Gmail SMTP fallback |
| Storage | Google Cloud Storage (production) |
| Deploy | GCP Cloud Run, auto-deploy on merge to master |
| Charts | Recharts |
| PDF | html2pdf.js |
| Rate Limiting | slowapi |
| Scheduling | APScheduler |
| OCR | Tesseract, Google Vision |
| Testing | pytest (backend), Vitest (frontend), Jest (mobile) |

---

*This feature catalog was generated by analyzing 1,969 GitHub issues, 60+ requirement sections across 8 requirement files, design audit reports, and the full codebase architecture. It represents the complete state of ClassBridge as of March 20, 2026. Production: classbridge.ca (live since March 6, 2026). Backend tests: 1,004.*
