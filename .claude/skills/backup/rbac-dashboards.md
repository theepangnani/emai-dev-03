# Role-Based Access Control & Dashboards

## Overview
EMAI implements role-based access control (RBAC) with four roles: Student, Parent, Teacher, and Admin. Each role has a dedicated dashboard and role-restricted API endpoints.

## Architecture

### Role Dispatcher Pattern
`Dashboard.tsx` is a thin dispatcher that routes to role-specific dashboard components based on `user.role`:
- `StudentDashboard` (default) - courses, assignments, study tools, Google Classroom
- `ParentDashboard` - linked children, child progress monitoring, link child by email
- `TeacherDashboard` - courses teaching, Google Classroom sync button, manual course creation, multi-Google accounts, messages, communications
- `AdminDashboard` - platform stats, user management table with search/filter/pagination

### Shared Layout
`DashboardLayout.tsx` extracts the common header, nav, and welcome section shared across all dashboards.

### Backend Role Checking
`app/api/deps.py` provides `require_role(*roles)` dependency factory:
```python
from app.api.deps import require_role
from app.models.user import UserRole

@router.get("/endpoint")
def my_endpoint(current_user: User = Depends(require_role(UserRole.ADMIN))):
    ...
```

### Frontend Route Protection
`ProtectedRoute` component supports optional `allowedRoles` prop:
```tsx
<ProtectedRoute allowedRoles={['admin']}>
  <AdminPage />
</ProtectedRoute>
```

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app/api/deps.py` | `get_current_user()`, `require_role()` |
| `app/api/routes/parent.py` | GET /children, POST /children/link, GET /children/{id}/overview |
| `app/api/routes/admin.py` | GET /users (paginated+filter+search), GET /stats |
| `app/api/routes/courses.py` | GET /courses/teaching (teacher-only) |
| `app/schemas/parent.py` | LinkChildRequest, ChildSummary, ChildOverview |
| `app/schemas/admin.py` | AdminUserList, AdminStats |
| `app/models/user.py` | UserRole enum (STUDENT, PARENT, TEACHER, ADMIN) |
| `app/models/student.py` | Student model + `parent_students` join table + `RelationshipType` enum |
| `app/models/invite.py` | Unified invite model for student + teacher invitations |
| `app/models/teacher.py` | Teacher model with `TeacherType` enum |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/pages/Dashboard.tsx` | Role dispatcher (switch on user.role) |
| `frontend/src/components/DashboardLayout.tsx` | Shared header, nav, welcome section |
| `frontend/src/pages/StudentDashboard.tsx` | Student view with courses, assignments, study tools |
| `frontend/src/pages/ParentDashboard.tsx` | Parent view with register child, link child, children list |
| `frontend/src/pages/TeacherDashboard.tsx` | Teacher view with courses, manual creation, Google accounts, communications |
| `frontend/src/pages/AdminDashboard.tsx` | Admin view with stats, user management |
| `frontend/src/components/ProtectedRoute.tsx` | Route guard with optional allowedRoles |
| `frontend/src/pages/AcceptInvite.tsx` | Unified invite acceptance page |
| `frontend/src/api/client.ts` | parentApi, adminApi, invitesApi, coursesApi.teachingList |

## API Endpoints

### Parent Endpoints (parent role only)
- `GET /api/parent/children` - List linked children
- `POST /api/parent/children/link` - Link child by email
- `POST /api/parent/children/discover-google` - Discover students via Google Classroom
- `POST /api/parent/children/link-bulk` - Bulk link discovered students
- `GET /api/parent/children/{student_id}/overview` - Child's courses, assignments, study guide count
- `POST /api/parent/children/{student_id}/sync-courses` - Trigger course sync for child
- `POST /api/invites/` - Create student or teacher invite (parent→student, teacher/admin→teacher)
- `GET /api/invites/sent` - List invites sent by current user
- `POST /api/auth/accept-invite` - Accept invite and create account (public)
- See `.claude/skills/parent-student.md` for full parent-student relationship details
- See `.claude/skills/unified-invites.md` for the unified invite system

### Admin Endpoints (admin role only)
- `GET /api/admin/users?role=&search=&skip=&limit=` - Paginated user list
- `GET /api/admin/stats` - User counts by role, total courses/assignments

### Teacher Endpoints (teacher role only)
- `GET /api/courses/teaching` - Courses where current user is the teacher
- `POST /api/google/courses/sync` - Sync Google Classroom courses (sets `teacher_id`) (Issue #52)
- `POST /api/teacher/courses` - Create a course manually (Issue #42, future)
- `POST /api/teacher/courses/{id}/students` - Add student to course (future)
- `POST /api/teacher/courses/{id}/assignments` - Create assignment (Issue #49, future)
- `GET /api/teacher/google-accounts` - List linked Google accounts (Issue #41, future)
- `POST /api/teacher/google-accounts` - Link a new Google account (future)
- `DELETE /api/teacher/google-accounts/{id}` - Unlink a Google account (future)
- See `.claude/skills/teacher-platform.md` for full teacher platform details

## Parent-Student Relationship
- **Many-to-many** via `parent_students` join table (see `.claude/skills/parent-student.md` for full details)
- A student can have zero, one, or many parents; a parent can have many children
- Parent linking is optional — students can use the platform independently
- Three onboarding paths: parent-created student, self-registered student, linked after the fact
- `relationship_type` field: mother, father, guardian, other

## Shared Features (All Roles)
- **Task Manager & Calendar**: Personal tasks + role-aware calendar (see `.claude/skills/task-calendar.md`)
  - `GET /api/tasks/` - List tasks
  - `POST /api/tasks/` - Create task
  - `GET /api/calendar/events` - Role-aware calendar events (tasks + assignments)
  - `POST /api/calendar/google-sync` - Push to Google Calendar
  - Calendar shows different data per role (students see assignments, parents see children's assignments, etc.)

## Adding a New Role-Specific Feature
1. Add backend endpoint with `require_role(UserRole.ROLE_NAME)` dependency
2. Add API client method in `client.ts`
3. Add UI to the appropriate role dashboard component
4. If it needs a new route, add to `App.tsx` with `<ProtectedRoute allowedRoles={['role']}>`

## Test Accounts
| Role | Email | Password |
|------|-------|----------|
| Teacher | theepang@gmail.com | (user's password) |
| Student | teststudent@test.com | test1234 |
| Parent | testparent@test.com | test1234 |
| Teacher | testteacher@test.com | test1234 |
| Admin | testadmin@test.com | test1234 |
