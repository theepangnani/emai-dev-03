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

### 10.0 Performance Standards (#1954–#1967)

#### 10.0.1 Backend Query Efficiency
- **No N+1 queries:** Every endpoint that returns ORM objects with relationships MUST use eager loading (`selectinload` / `joinedload`) via shared options helpers. Lazy loading of relationships in response builders is prohibited.
- **Batch queries over loops:** Never query the database inside a loop. Use `.in_()` filters or JOINs to batch-fetch related records.
- **DB round trips per endpoint:** Standard CRUD endpoints MUST complete in ≤ 4 DB round trips (query + commit). Dashboard/aggregation endpoints ≤ 8.

#### 10.0.2 Database Indexing
- Every foreign key column MUST have an index (either single-column or as the leading column of a composite index).
- Columns used in `.filter()` across 2+ endpoints MUST be indexed (e.g., `status`, `is_active`, `role`, `guide_type`).
- Frequently queried column pairs SHOULD have composite indexes (e.g., `(user_id, archived_at)`, `(course_id, content_type)`).

#### 10.0.3 Connection Pooling
- Production PostgreSQL engine MUST configure `pool_size`, `max_overflow`, `pool_pre_ping`, and `pool_recycle`.
- SQLite development mode is exempt from pooling requirements.

#### 10.0.4 Frontend Network Resilience
- **Default request timeout:** All Axios requests MUST have a default timeout (30s). Long-running operations (AI generation, file upload) may override with explicit higher timeout.
- **AbortController cleanup:** `useEffect` hooks that make API calls SHOULD use `AbortController` to cancel in-flight requests on unmount.
- **Visibility-aware polling:** Polling intervals (notifications, messages, AI usage) MUST pause when `document.visibilityState === 'hidden'` and resume on focus.

#### 10.0.5 Token & Auth Performance
- Token blacklist lookups SHOULD be cached in-memory (LRU, TTL ≤ 60s) to avoid +1 DB query per authenticated request.

#### 10.0.6 Pagination
- List endpoints returning unbounded results MUST support pagination or enforce a default LIMIT. Parent dashboard, admin user lists, and search results must not load full tables into memory.

### 10.1 Data Privacy & User Rights

ClassBridge handles student data subject to FERPA, PIPEDA, and MFIPPA. The following capabilities are required (implementation deferred to Phase 2+):

- **Account Deletion**: Users can request full account deletion. System must cascade-delete or anonymize all related records (tasks, messages, parent-student links, study materials, Google tokens).
- **Data Export**: Users can request a machine-readable export (JSON/CSV) of all personal data (GDPR Article 20, PIPEDA right of access).
- **Consent Management**: Track and store user consent for data collection, Google OAuth scopes, and email communications. Allow users to withdraw consent.
- **Data Retention**: Define retention periods for inactive accounts, expired invites, and completed tasks. Auto-purge after defined periods.
- **Minor Data Protection**: Student accounts (especially those created by parents) require additional protections — no marketing emails, limited data sharing, parental consent for under-13 users.
- **Audit Logging**: Log access to sensitive data (parent viewing child data, admin viewing user list) for compliance auditing. **Phase 1 implementation complete** — see §6.14. Future: log export, alerting, archival to external storage.

### 10.2 Accessibility (WCAG 2.1 AA)

ClassBridge targets WCAG 2.1 Level AA compliance for all user-facing pages. Added March 2026 based on comprehensive frontend audit.

- **Contrast:** All text meets 4.5:1 contrast ratio on its background (WCAG 1.4.3)
- **Form Accessibility:** All inputs have labels; errors use `aria-invalid` + `aria-describedby` (WCAG 1.3.1, 3.3.1)
- **Semantic HTML:** Native `<button>`, `<a>`, `<table>` elements; no `div role="button"` (WCAG 4.1.2)
- **Motion:** All animations respect `prefers-reduced-motion: reduce` (WCAG 2.3.3)
- **Touch Targets:** Minimum 44px on touch devices (WCAG 2.5.5)
- **Responsive:** Standard breakpoints only (480px, 768px, 1024px); minimum 11px font size
- **Testing:** axe-core in CI pipeline; Lighthouse accessibility score >= 90; manual screen reader testing quarterly

**GitHub Issues:** #2148 (WCAG audit), #2472–#2486 (accessibility batch), #2611–#2619 (audit remediation)

See §6.18.1 in features-part2.md for detailed requirements and acceptance criteria.

---

## 11. Success Metrics (KPIs)

- Parent engagement rate
- Student grade improvement
- Daily active users
- Retention rate
- Teacher adoption rate

---

