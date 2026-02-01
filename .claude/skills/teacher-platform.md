# Teacher & Private Tutor Platform

## Overview
ClassBridge supports two categories of teachers. Platform teachers (on EMAI) register and manage courses directly. Non-EMAI school teachers are discovered via Google Classroom sync as shadow records and invited to join.

## Teacher Types

### Platform Teacher (`is_platform_user=true`)
- Registers on EMAI with `role=teacher`
- `Teacher` record created automatically at registration
- `teacher_type`: `school_teacher` or `private_tutor`
- Can create/manage courses manually
- Can connect multiple Google accounts
- Full dashboard access: courses, messaging, communications, student rosters

### Shadow Teacher (`is_platform_user=false`)
- Discovered during Google Classroom sync (parent or student syncs a course)
- System creates a `Teacher` record with name/email from Google Classroom
- No `User` record yet — cannot log in
- Appears as the teacher on synced courses (read-only reference)
- Receives invite email to join ClassBridge
- On invite acceptance: `User` record created, `is_platform_user` set to `true`, full access granted

## Data Model

### Updated `Teacher` Model
```python
class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # nullable for shadow teachers
    school_name = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    teacher_type = Column(String(50), default="school_teacher")  # school_teacher, private_tutor
    is_platform_user = Column(Boolean, default=True)

    # Shadow teacher fields (from Google Classroom)
    google_email = Column(String(255), nullable=True)
    google_name = Column(String(255), nullable=True)

    # Invite flow
    invite_token = Column(String(255), nullable=True)
    invite_token_expires = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### `teacher_google_accounts` Table
```sql
CREATE TABLE teacher_google_accounts (
    id INTEGER PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
    google_email VARCHAR(255) NOT NULL,
    google_id VARCHAR(255),
    access_token VARCHAR(512),
    refresh_token VARCHAR(512),
    account_label VARCHAR(100),       -- e.g., "Personal", "School"
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(teacher_id, google_email)
);
```

**Note:** For teachers, Google OAuth tokens move from `User.google_access_token`/`google_refresh_token` to this multi-account table. Non-teacher roles (parent, student) continue using the single tokens on `User`.

## Registration & Onboarding Flows

### Flow 1: Teacher Self-Registration
1. Teacher registers at `/auth/register` with `role=teacher`
2. System creates `User` + `Teacher` record (`is_platform_user=true`)
3. Teacher selects `teacher_type` (school_teacher or private_tutor)
4. Teacher can immediately create courses manually
5. Optionally connects one or more Google accounts to sync courses

### Flow 2: Shadow Teacher Discovery + Invite
1. Parent/student syncs Google Classroom
2. For each course, system checks if the course teacher exists in EMAI
3. If not found: create a shadow `Teacher` record (`is_platform_user=false`, `user_id=NULL`)
4. Store `google_email` and `google_name` from Google Classroom data
5. Send invite email to the teacher's Google email
6. Teacher clicks invite link → `/accept-invite` page (unified invite flow)
7. Teacher sets password → system creates `User` record, links to `Teacher`, sets `is_platform_user=true`
8. Teacher now has full platform access

### Flow 3: Manual Course Creation (Platform Teachers)
1. Teacher creates a course via `POST /api/teacher/courses`
2. Provides: name, subject, description
3. Course created with `teacher_id` set, no `google_classroom_id`
4. Teacher adds students by email via `POST /api/teacher/courses/{id}/students`
5. Students receive notification they were added to a course

### Flow 4: Multi-Google Account Sync
1. Teacher links a Google account via `POST /api/teacher/google-accounts`
2. OAuth flow stores tokens in `teacher_google_accounts`
3. Teacher can label each account (e.g., "Personal", "Springfield High")
4. Sync pulls courses from each linked account independently
5. Teacher can unlink accounts via `DELETE /api/teacher/google-accounts/{id}`

## API Endpoints

### Teacher Endpoints (teacher role only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/teacher/courses` | POST | Create a course manually |
| `/api/teacher/courses/{id}/students` | POST | Add student to course by email |
| `/api/teacher/courses/{id}/assignments` | POST | Create assignment for a course |
| `/api/teacher/google-accounts` | GET | List linked Google accounts |
| `/api/teacher/google-accounts` | POST | Link a new Google account (OAuth) |
| `/api/teacher/google-accounts/{id}` | DELETE | Unlink a Google account |
| `/api/courses/teaching` | GET | List all courses taught (existing) |

### Auth Endpoints (Unified Invite System)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/accept-invite` | POST | Accept invite and set password (unified for student + teacher invites) |

**Note:** Uses the shared `invites` table with `invite_type='teacher'`. The invite carries metadata (google_email, google_name) to link the shadow Teacher record on acceptance.

## Request/Response Schemas

### CreateCourseRequest (teacher manual creation)
```python
class CreateCourseRequest(BaseModel):
    name: str
    subject: Optional[str]
    description: Optional[str]
```

### AddStudentToCourseRequest
```python
class AddStudentToCourseRequest(BaseModel):
    student_email: str
```

### GoogleAccountResponse
```python
class GoogleAccountResponse(BaseModel):
    id: int
    google_email: str
    account_label: Optional[str]
    is_primary: bool
    created_at: datetime
```

### AcceptInviteRequest (unified)
```python
class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: Optional[str]              # required for teacher invites
    teacher_type: Optional[str]           # only for teacher invites: school_teacher or private_tutor
```
**Note:** The endpoint resolves `invite_type` from the `invites` table record. For teacher invites, `full_name` and `teacher_type` are required.

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app/models/teacher.py` | Updated Teacher model with type, platform flag, invite fields |
| `app/models/teacher_google_account.py` | TeacherGoogleAccount model (new) |
| `app/api/routes/teacher.py` | Teacher endpoints (new): courses, Google accounts |
| `app/api/routes/auth.py` | Unified accept-invite endpoint (handles both student + teacher) |
| `app/schemas/teacher.py` | Teacher request/response schemas (new) |
| `app/services/google_classroom.py` | Updated to support multi-account sync |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/pages/TeacherDashboard.tsx` | Updated: course creation, Google account management |
| `frontend/src/pages/AcceptInvite.tsx` | Unified invite acceptance page (handles student + teacher) |
| `frontend/src/api/client.ts` | `teacherApi` methods (new) |

## Implementation Notes
- When creating a `Teacher` record at registration, default `teacher_type` to `school_teacher`
- Shadow teachers have `user_id=NULL` until they accept the invite
- Invite tokens expire after 30 days (longer than student invites since teachers may be slower to respond)
- The existing `POST /api/courses/` endpoint should be deprecated in favor of `POST /api/teacher/courses`
- Google Classroom sync logic needs to check `teacher_google_accounts` for teacher tokens instead of `User.google_access_token`
- When a shadow teacher matches an existing User (by email), merge rather than create a new User
