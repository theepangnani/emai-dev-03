# Parallel Claude Session Prompts — Phase 1 Completion

> **Instructions:** Open 5 separate Claude Code sessions. In each, run the checkout command first, then paste the prompt.
> **Merge order:** Session 4 → Session 1 → Session 2 → Session 3 → Session 5

---

## Session 1: Teacher Platform Features

### Setup
```bash
git checkout feature/session-1-teacher-platform
```

### Prompt

```
You are working on the EMAI/ClassBridge project on branch `feature/session-1-teacher-platform`.

Read CLAUDE.md and REQUIREMENTS.md first for full project context.

Your scope is GitHub issues #57, #58, #59, #62. Implement these teacher platform features:

## Issue #58 — Add `is_platform_user` flag to Teacher model
- In `app/models/teacher.py`, add a Boolean column `is_platform_user` with default `False`
- When `is_shadow=False` and `user_id` is set, `is_platform_user` should be `True`
- Add an ALTER TABLE migration in `main.py` migration block following the existing pattern (check column exists, try/except, conn.commit). Use DEFAULT FALSE.
- Update any queries/endpoints that filter by shadow status to also expose `is_platform_user`
- Update `app/schemas/teacher.py` to include the field in responses

## Issue #62 — `teacher_google_accounts` table
- The model `app/models/teacher_google_account.py` already exists. Verify it has: teacher_id (FK), google_email, google_id, access_token, refresh_token, account_label, is_primary, created_at
- Create `app/api/routes/teacher_accounts.py` with endpoints:
  - `GET /teacher/google-accounts` — list linked accounts for current teacher
  - `POST /teacher/google-accounts` — link new Google account (OAuth flow)
  - `DELETE /teacher/google-accounts/{id}` — unlink account
- Create `app/schemas/teacher_account.py` for request/response models
- Register the router in `main.py` with `prefix="/api"`
- Modify `app/services/google_classroom.py` sync to use per-account tokens when teacher has entries in `teacher_google_accounts`, falling back to User-level tokens

## Issue #57 — Auto-send invite email to shadow teachers
- In `app/services/google_classroom.py`, find `_resolve_teacher_for_course()` (or the function that creates shadow teachers)
- After creating a shadow Teacher record, check for existing pending TEACHER invite for that google_email
- If none exists, create an `Invite` record with `invite_type=InviteType.TEACHER`, `email=google_email`, `expires_at=30 days`
- Send invite email using `send_email()` from `app/services/email_service.py` with a template mentioning the student's name and course
- Add tests in `tests/test_teacher_platform.py`

## Issue #59 — Teacher Dashboard course management view
- In `frontend/src/pages/TeacherDashboard.tsx`, add a "My Courses" section:
  - Fetch `GET /api/courses` (filtered to teacher's courses)
  - Show each course with a source badge: "Google Classroom" (if `google_classroom_id` exists) or "Manual"
  - Display student count per course
  - "Sync Courses" button that calls Google Classroom sync endpoint
  - "Create Course" button linking to course creation
  - Show `last_synced` timestamp per course
- Add corresponding CSS in the teacher dashboard styles

## CONSTRAINTS
- Do NOT modify: email_service.py core functions, notification model, frontend router (App.tsx), invite model
- Follow existing patterns: Pydantic v2 schemas with `ConfigDict(from_attributes=True)`, `require_role()` for auth, try/except migrations
- Write pytest tests for all new backend endpoints
- Commit atomically per issue with descriptive messages
```

---

## Session 2: Document Repository & Content Storage

### Setup
```bash
git checkout feature/session-2-document-repo
```

### Prompt

```
You are working on the EMAI/ClassBridge project on branch `feature/session-2-document-repo`.

Read CLAUDE.md and REQUIREMENTS.md first for full project context.

Your scope is GitHub issues #28, #61, #114. Implement document repository and content storage features:

## Issue #28 — Central Document Repository
### Backend
- Create `app/models/document.py` with Document model:
  - id (PK), user_id (FK users.id), course_id (FK courses.id, nullable), title (String), description (Text), file_type (String), file_path (String — GCS URL or local path), file_size (Integer), is_public (Boolean default False), shared_with (JSON — list of user_ids or roles), tags (JSON), created_at, updated_at
- Add to `app/models/__init__.py`
- Create `app/schemas/document.py` with DocumentCreate, DocumentUpdate, DocumentResponse
- Create `app/api/routes/documents.py` with endpoints:
  - `POST /documents/upload` — multipart upload, store file, create record
  - `GET /documents/` — list with filtering (by course, tags, search query)
  - `GET /documents/{id}` — get document details
  - `GET /documents/{id}/download` — serve file or return signed URL
  - `DELETE /documents/{id}` — soft delete
  - `PUT /documents/{id}/share` — update sharing settings
- Full-text search on title and description fields
- Role-based access: parents see their own + shared, teachers see course docs, admins see all
- Register router in `main.py` with `prefix="/api"`

### Frontend
- Create `frontend/src/pages/DocumentsPage.tsx`:
  - List/grid view toggle for documents
  - Upload button with drag-and-drop zone
  - Search bar and course filter dropdown
  - Each document card: title, type icon, size, date, shared status
  - Click to preview (PDF viewer for PDFs) or download
  - Share button opens sharing modal
- Add route in `frontend/src/App.tsx`: `/documents` protected for all roles
- Add "Documents" link to sidebar in `frontend/src/components/DashboardLayout.tsx`

## Issue #114 — GCS File Storage
- Create `app/services/storage_service.py`:
  - If `GCS_BUCKET_NAME` env var is set, use Google Cloud Storage
  - If not set, fall back to local `uploads/` directory (dev mode)
  - Functions: `upload_file(file, path) -> url`, `get_signed_url(path) -> url`, `delete_file(path)`
  - Path format: `/{user_id}/{course_id or 'general'}/{filename}`
  - Storage caps: 500MB per course, 2GB per user — check before upload
- Add `GCS_BUCKET_NAME` to `app/core/config.py` Settings (optional field)

## Issue #61 — Content Privacy Controls & Version History
- Add to existing `app/models/course_content.py`:
  - `visibility` column: String, values "private"/"shared"/"public", default "private"
  - `version` column: Integer, default 1
  - `previous_version_id` column: FK to self (nullable) for version chain
- Add ALTER TABLE migrations in `main.py` for these new columns
- Update `app/api/routes/course_contents.py`:
  - Filter content by visibility based on requester's role/relationship
  - `POST /course-contents/{id}/new-version` — create new version linked to previous
  - `GET /course-contents/{id}/versions` — list version history
- Update frontend course content display to show visibility badge and version info

## CONSTRAINTS
- Do NOT modify: teacher model, teacher routes, notification system, email service
- For file uploads, use FastAPI's `UploadFile` with `python-multipart`
- Use existing auth patterns: `get_current_user`, `require_role()`
- Write pytest tests for all new endpoints
- Commit atomically per issue
```

---

## Session 3: Notifications & Invite Improvements

### Setup
```bash
git checkout feature/session-3-notifications-invites
```

### Prompt

```
You are working on the EMAI/ClassBridge project on branch `feature/session-3-notifications-invites`.

Read CLAUDE.md and REQUIREMENTS.md first for full project context.

Your scope is GitHub issues #238, #253, #254, #260, #261. Implement notification and invite improvements:

## Issue #260 — Inspirational Messages in All Emails
- In `app/services/email_service.py`, the helper `add_inspiration_to_email(html_content, db, role)` already exists
- Update ALL email-sending call sites to use this helper before sending:
  - `app/services/email_service.py` — any direct sends
  - `app/api/routes/invites.py` — invite emails
  - `app/api/routes/messages.py` — message notification emails
  - `app/api/routes/auth.py` — password reset emails
  - `app/api/routes/admin.py` — broadcast emails
  - `app/jobs/assignment_reminders.py` — assignment reminder emails
  - `app/jobs/task_reminders.py` — task reminder emails
  - Any other email sending locations
- The function needs a db session and recipient role. For each call site:
  - If db session is available, pass it directly
  - If role is unknown, use "parent" as default (most common recipient)
  - If inspiration lookup fails, send email without it (graceful degradation)
- Style the footer: italic quote text, smaller font, horizontal rule separator above
- Write tests verifying the inspiration footer is appended

## Issue #253 — Resend Invite on Demand
- The endpoint `POST /api/invites/{invite_id}/resend` already exists in `app/api/routes/invites.py`
- Verify it: refreshes `expires_at` to 30 days from now, generates new token, resends email
- Add rate limiting: max 1 resend per hour per invite (check `updated_at` or add a `last_resent_at` column)
- Add frontend UI in teacher and parent dashboards:
  - "Sent Invites" section showing: recipient email, type, status (pending/accepted/expired), date
  - "Resend" button for pending/expired invites
  - Visual status indicators (green=accepted, yellow=pending, red=expired)

## Issue #254 — Email Notification on Existing Student Enrollment
- In `app/api/routes/courses.py`, find the `add_student_to_course()` endpoint
- After the in-app notification creation, add email sending:
  - Look up student's email via their User record
  - Send email: subject "{teacher_name} enrolled you in {course_name} on ClassBridge"
  - Include link to course page: `{frontend_url}/courses/{course_id}`
  - Use `add_inspiration_to_email()` for the footer

## Issue #238 — Notify Parent When Teacher Enrolls Child
- In the same `add_student_to_course()` endpoint in `app/api/routes/courses.py`:
  - After enrolling the student, query `parent_students` to find the student's parents
  - For each parent, create a Notification: type=SYSTEM, title="New course enrollment", content="{teacher_name} enrolled {child_name} in {course_name}"
  - Set notification `link` to `/courses/{course_id}`
  - Also send email notification to each parent with the same info

## Issue #261 — Notification Click Opens Popup Modal
- In `frontend/src/components/NotificationBell.tsx`:
  - Replace inline text expand with a modal popup
  - On notification click → set `selectedNotification` state, render modal overlay
  - Modal shows: bold title, full content (no truncation), relative timestamp, close button (X)
  - Click outside modal to dismiss
  - If notification has a `link` field, show a "Go to..." button in modal footer
  - Mark notification as read on modal open (keep existing behavior)
- In `frontend/src/components/NotificationBell.css`:
  - Use shared `.modal-overlay` / `.modal` pattern from `Dashboard.css`
  - Add notification-specific styles

## CONSTRAINTS
- Do NOT modify: teacher model, document/content models, teacher dashboard, scheduler.py core
- Do NOT change the signature of `send_email()` or `send_email_sync()` — only modify call sites
- Follow existing notification creation pattern (check existing code for examples)
- Write pytest tests for issues #253, #254, #238
- Write frontend tests for #261 if test patterns exist
- Commit atomically per issue
```

---

## Session 4: Security & Infrastructure Hardening

### Setup
```bash
git checkout feature/session-4-security-infra
```

### Prompt

```
You are working on the EMAI/ClassBridge project on branch `feature/session-4-security-infra`.

Read CLAUDE.md and REQUIREMENTS.md first for full project context.

Your scope is GitHub issues #67, #68, #69, #73, #142. Implement security and infrastructure hardening:

## Issue #68 — Encrypt Google OAuth Tokens at Rest
- Create `app/core/encryption.py`:
  - Use `cryptography.fernet` for symmetric encryption
  - Key derived from a new `ENCRYPTION_KEY` setting in `app/core/config.py` (required in prod, auto-generated in dev)
  - Functions: `encrypt_token(plaintext: str) -> str`, `decrypt_token(ciphertext: str) -> str`
  - Encrypted values stored as base64 strings in DB
- In `app/models/user.py`, the existing `google_access_token` and `google_refresh_token` fields stay as String columns
- Modify Google OAuth callback (`app/api/routes/google_classroom.py`) to encrypt tokens before storing
- Modify Google API calls (`app/services/google_classroom.py`, `app/services/gmail_monitor.py`) to decrypt tokens before use
- Add a one-time migration helper to encrypt existing plaintext tokens (run once, idempotent)
- Add `cryptography` to requirements.txt if not already present
- Also encrypt tokens in `teacher_google_accounts` table

## Issue #67 — Prevent Duplicate APScheduler Jobs
- In `app/services/scheduler.py` and `main.py` startup:
  - Before adding each job, check if it already exists: `scheduler.get_job(job_id)`
  - Use explicit `job_id` strings for each job (e.g., "assignment_reminders", "task_reminders", etc.)
  - If job exists, replace it; if not, add it
  - Add a `SCHEDULER_ENABLED` config flag (default True). Set to False to disable scheduler (useful for multi-worker deploys where only 1 worker runs the scheduler)
  - Log scheduler job status on startup

## Issue #69 — JWT Storage Strategy (Document + Harden)
- This is primarily a documentation + incremental hardening task:
  - Add `SameSite=Strict` and `Secure` flags if cookies are used anywhere
  - Add CSP header `script-src 'self'` to security headers middleware (if not already present)
  - Ensure the existing 401 interceptor in `frontend/src/api/client.ts` clears tokens properly
  - Add a short comment block in `frontend/src/context/AuthContext.tsx` documenting the threat model: "JWT in localStorage — acceptable for internal school tool with CSP headers. XSS mitigated by input sanitization + CSP."
  - Do NOT migrate to httpOnly cookies (too disruptive) — just harden what exists

## Issue #73 — Database Index Migration
- In `main.py` migration block, add CREATE INDEX statements (use IF NOT EXISTS for PostgreSQL, try/except for SQLite):
  - `messages`: index on `(conversation_id, created_at)`
  - `notifications`: index on `(user_id, read, created_at)` — may already exist as composite
  - `assignments`: index on `(course_id, due_date)`
  - `courses`: index on `(teacher_id)`, index on `(google_classroom_id)`
  - `students`: index on `(user_id)`
  - `study_guides`: index on `(user_id, course_id)`
  - `tasks`: index on `(assigned_to, due_date)`
  - `audit_logs`: index on `(user_id, created_at)`
- Check which indexes already exist in the ORM model definitions and only add missing ones as migrations
- Each CREATE INDEX in its own try/except block

## Issue #142 — Input Validation & Field Length Limits
- Audit all Pydantic schemas in `app/schemas/` and add field constraints:
  - `title` fields: `max_length=200`
  - `description` / `content` fields: `max_length=10000`
  - `name` fields: `max_length=100`
  - `email` fields: `EmailStr` type (from pydantic)
  - `url` fields: `HttpUrl` type or regex pattern validation
  - String fields that accept user input: strip whitespace with `field_validator`
- Add `min_length=1` for required string fields to prevent empty strings
- Do NOT change existing tests — but do add new validation tests in `tests/test_validation.py`

## CONSTRAINTS
- Do NOT modify: teacher dashboard, document models, notification bell, email templates
- Do NOT change JWT auth flow (keep localStorage) — only harden
- For encryption: make it backward-compatible — decrypt should handle both encrypted and plaintext values gracefully during transition
- Every migration in main.py must follow the pattern: own try/except, own conn.commit()
- Write tests for encryption utility and validation constraints
- Commit atomically per issue
```

---

## Session 5: Testing & Admin Multi-Role

### Setup
```bash
git checkout feature/session-5-testing-admin
```

### Prompt

```
You are working on the EMAI/ClassBridge project on branch `feature/session-5-testing-admin`.

Read CLAUDE.md and REQUIREMENTS.md first for full project context.

Your scope is GitHub issues #80, #156, #255. Implement E2E tests, PostgreSQL CI, and admin role management:

## Issue #255 — Admin Role Management UI
### Backend
- Create endpoint in `app/api/routes/users.py`:
  - `PUT /api/users/{user_id}/roles` — admin-only endpoint
  - Body: `{ "roles": ["parent", "teacher"] }`
  - Validate all role strings are valid UserRole values
  - Call `user.set_roles(roles)` (method should already exist on User model)
  - Auto-create missing profile records:
    - If "teacher" in roles and no Teacher record → create Teacher(user_id=user.id, is_shadow=False, is_platform_user=True)
    - If "student" in roles and no Student record → create Student(user_id=user.id)
  - Do NOT delete profile records when removing a role (preserve data)
  - Return updated user with current roles
- Add schema in `app/schemas/user.py`: `RoleUpdateRequest` with `roles: list[str]`

### Frontend
- In `frontend/src/pages/AdminDashboard.tsx`:
  - Add a "Manage Roles" button in the user list table for each user
  - On click → open modal with checkboxes for: Parent, Student, Teacher, Admin
  - Pre-check current roles
  - Save button calls `PUT /api/users/{user_id}/roles`
  - Show success toast on save, refresh user list
  - Style the modal using shared `.modal-overlay` / `.modal` from `Dashboard.css`

### Tests
- Add tests in `tests/test_admin_roles.py`:
  - Test adding a role creates profile record
  - Test removing a role preserves profile record
  - Test non-admin cannot access endpoint
  - Test invalid role name returns 422

## Issue #80 — E2E Smoke Tests (Playwright)
- Set up Playwright in `frontend/`:
  - `npm install -D @playwright/test`
  - Create `frontend/playwright.config.ts` with baseURL pointing to localhost:5173
  - Create `frontend/e2e/` directory for test files
- Write smoke tests in `frontend/e2e/smoke.spec.ts`:
  - **Login flow:** Navigate to /login, enter credentials, verify dashboard loads
  - **Dashboard load:** Verify role-specific dashboard renders (check for known elements)
  - **Messages page:** Navigate to /messages, verify list renders
  - **Notifications:** Click notification bell, verify dropdown opens
  - **Courses page:** Navigate to /courses, verify course cards render
- Create a seed data helper or use test fixtures for consistent test data
- Add `playwright` script to `frontend/package.json`
- Do NOT add Playwright to CI yet (that requires the backend running) — just make it runnable locally

## Issue #156 — PostgreSQL Test Coverage in CI
- In `.github/workflows/deploy.yml`, modify the test job:
  - Add a PostgreSQL service container:
    ```yaml
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: emai_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    ```
  - Run pytest TWICE: once with SQLite (existing), once with `DATABASE_URL=postgresql://test:test@localhost:5432/emai_test`
  - Both must pass for CI to be green
- Add `psycopg2-binary` to requirements.txt if not present
- Fix any test failures that appear only on PostgreSQL (common issues: BOOLEAN defaults, DATETIME vs TIMESTAMPTZ, Enum storage)

## CONSTRAINTS
- Do NOT modify: teacher model, document models, email service, notification model, courses routes
- Admin role endpoint should be the ONLY change to `users.py`
- For Playwright: use test IDs (`data-testid`) if elements need identification — add them to existing components only if necessary
- Do NOT modify `main.py` migration block (Session 4 handles that)
- Commit atomically per issue
```

---

## Post-Merge Checklist

After all sessions are done and branches are merged (in order: 4 → 1 → 2 → 3 → 5):

1. `git checkout feature/phase-1`
2. Merge each branch sequentially, resolving conflicts in `main.py` and `models/__init__.py`
3. Run full test suite: `pytest` and `cd frontend && npm test`
4. Manual smoke test on localhost
5. Create PR from `feature/phase-1` → `master`
