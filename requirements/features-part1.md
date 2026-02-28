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
- **Non-blocking generation**: AI study material generation is fully non-blocking. Modal closes immediately after submission, a pulsing "Generating..." placeholder row appears in the study materials list, and the user can continue working. On success the placeholder is replaced with the real guide; on failure it shows an error with a dismiss button. Works from both Study Guides page and Parent Dashboard (queues generation and navigates to Study Guides page). On the Course Material detail page, generation shows an inline spinner + pulsing message in the content area (no blocking overlay); the view auto-switches to the target tab so users see progress, and tabs remain navigable during generation
- **Math-aware AI prompts**: Study guide, quiz, and flashcard generation prompts detect math problems, equations, and exercises. When math content is found, the study guide provides step-by-step worked solutions with explanations; quizzes test problem-solving ability with numerical answer choices; flashcards show problems on front and worked solutions on back
- **Comprehensive docx OCR**: All embedded images in .docx files are OCR'd via Tesseract regardless of how much regular text the document contains. This ensures screenshots of math problems, diagrams with text, and scanned worksheets are always extracted

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
- **Tab 2: Study Guide** — shows the generated study guide, or a "Generate Study Guide" button if none exists. During generation, an inline spinner + pulsing message replaces the empty state
- **Tab 3: Quiz** — shows the generated quiz, or a "Generate Quiz" button if none exists. During generation, an inline spinner + pulsing message replaces the empty state
- **Tab 4: Flashcards** — shows the generated flashcards, or a "Generate Flashcards" button if none exists. During generation, an inline spinner + pulsing message replaces the empty state

**Print & PDF Export** (All tabs) — IMPLEMENTED (#764):
- **Print**: Each tab has a Print button that opens a clean print dialog in a new window with formatted content (no sidebar, navigation, or UI controls). Uses embedded print-specific CSS for clean typography
- **Download PDF**: Each tab has a Download PDF button that generates and downloads a formatted A4 PDF using `html2pdf.js` (dynamically imported to minimize initial bundle size). Shows "Exporting..." loading state during generation
- **Static print views**: Quiz prints all questions with correct answers marked (not the interactive stepper). Flashcards print all cards as a numbered front/back list (not the flip-card UI). Document and Study Guide print the rendered content directly
- **Implementation**: Shared utility `exportUtils.ts` with `printElement()` and `downloadAsPdf()` functions

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
- **Date context**: All AI prompts include `Today's date is {YYYY-MM-DD}` so the model can infer the year for ambiguous dates (e.g., "Due Mar 3" → `2026-03-03`). Prompts instruct the model to assume the nearest future occurrence when no year is specified
- **Non-student date filtering**: Prompts instruct the model to only extract actual student deadlines — not historical dates, reference dates, or dates from article/lesson subject matter

**API Changes:**
- Generation endpoints (`/api/study/generate`, `/api/study/quiz/generate`, `/api/study/flashcards/generate`) return optional `auto_created_tasks` array in response
- `GET /api/tasks/` supports `study_guide_id` query parameter to filter tasks linked to a specific study guide
- No new endpoints needed — uses existing task creation logic internally

**Frontend Task Display:**
- Study Guide, Quiz, and Flashcards tabs display a `LinkedTasksBanner` showing auto-created tasks with due date badge and clickable link to the task detail page
- After generating study material, a toast notification shows when tasks were auto-created (e.g., "Task created: Due Mar 3 (due Mar 3, 2026)")
- Tasks are fetched per study guide via `tasksApi.list({ study_guide_id })` in `CourseMaterialDetailPage`

**GitHub Issues:** #195 (AI auto-task creation), #902 (parent_id fix), #920 (date context + UI display)

#### 6.2.4 Quiz Results History (Phase 2) - IMPLEMENTED

Persist quiz attempts and track performance over time.

- **Quiz Result Saving**: Both the dedicated Quiz page (`/study/quiz/:id`) and the inline quiz tab on Course Material Detail page automatically save results on quiz completion via `POST /api/quiz-results/`. Results include score, total questions, percentage, per-question answers, and attempt number
- **Quiz History Page**: Dedicated `/quiz-history` page showing stats cards (Total Attempts, Unique Quizzes, Average Score, Best Score with trend arrow), score trend chart (Recharts line chart), and scrollable attempts list with score bars, retry buttons, and delete
- **Parent-to-Child Access**: Parents see their own quiz results plus linked children's results. Child selector dropdown allows filtering by specific child. Uses `student_user_id` query parameter with `parent_students` join table verification. Multi-role support via `has_role()` check
- **Score Trend Analysis**: Backend compares average of last 5 attempts vs previous 5 to compute trend (improving/declining/stable)
- **View History Link**: Quiz completion screen on both quiz pages shows "View History" link filtered to that specific quiz

**Endpoints:**
- `POST /api/quiz-results/` — Save quiz result
- `GET /api/quiz-results/` — List results (supports `study_guide_id`, `student_user_id` filters)
- `GET /api/quiz-results/stats` — Aggregated stats (supports `student_user_id` filter)
- `GET /api/quiz-results/{id}` — Single result detail
- `DELETE /api/quiz-results/{id}` — Delete result

**GitHub Issues:** #574, #621

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

