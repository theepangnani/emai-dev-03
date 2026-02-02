# Teacher & Private Tutor Platform

## Overview
ClassBridge supports two categories of teachers. Platform teachers (on EMAI) register and manage courses directly. Non-EMAI school teachers are discovered via Google Classroom sync as shadow records and invited to join.

## Teacher Types

### TeacherType Enum
```python
class TeacherType(str, enum.Enum):
    SCHOOL_TEACHER = "school_teacher"
    PRIVATE_TUTOR = "private_tutor"
```

### Platform Teacher
- Registers on EMAI with `role=teacher`
- `Teacher` record created automatically at registration (via auth.py)
- Selects `teacher_type` during registration (school_teacher or private_tutor)
- Can create/manage courses manually
- Can connect multiple Google accounts
- Full dashboard access: courses, messaging, communications, student rosters

### Shadow Teacher (Future — not yet implemented)
- Discovered during Google Classroom sync (parent or student syncs a course)
- System creates a `Teacher` record with name/email from Google Classroom
- No `User` record yet — cannot log in
- Appears as the teacher on synced courses (read-only reference)
- Receives invite email to join ClassBridge (via unified invite system)
- On invite acceptance: `User` record created, full access granted

## Data Model

### Current `Teacher` Model
```python
class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    school_name = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    teacher_type = Column(Enum(TeacherType), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user = relationship("User", foreign_keys=[user_id])
```

### Future: `teacher_google_accounts` Table (Issue #41)
For multi-Google account support (all teachers, not just private tutors):
```sql
CREATE TABLE teacher_google_accounts (
    id INTEGER PRIMARY KEY,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id),
    google_email VARCHAR(255) NOT NULL,
    google_id VARCHAR(255),
    access_token VARCHAR(512),
    refresh_token VARCHAR(512),
    account_label VARCHAR(100),
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(teacher_id, google_email)
);
```

## Course Management

### Three Course Sources
| Source | Description | Who Uses It |
|--------|-------------|-------------|
| **Google Classroom Sync** | Import courses from connected Google account | Any teacher with Google Classroom |
| **Manual Course Creation** | Create courses directly in EMAI | Private tutors, teachers without Google |
| **Multi-Account Sync** | Sync from multiple Google accounts | Teachers with personal + school Google accounts |

### Google Classroom Course Sync (Issue #52 — Implemented)
1. Teacher connects Google account via `/api/google/connect`
2. Teacher clicks "Sync Courses" on dashboard → `POST /api/google/courses/sync`
3. Backend fetches courses from Google Classroom API
4. Creates/updates Course records locally with `teacher_id` set
5. Dashboard reloads and shows synced courses
6. Future: use `teacherId=me` filter to only sync courses teacher owns (not PD courses)

### Background Periodic Sync (Issue #53 — Phase 1.5)
- APScheduler job periodically syncs courses for all connected teachers
- Handles token refresh, rate limits, per-teacher error isolation

### Multi-Google Account Support (Issue #41 — Future)
- All teachers (school + private) can link multiple Google accounts
- `teacher_google_accounts` table stores credentials per account
- Each account syncs its own courses independently
- Courses from all accounts appear together on Teacher Dashboard
- Teacher labels accounts (e.g., "Personal", "Springfield High")

## Registration & Onboarding Flows

### Flow 1: Teacher Self-Registration (Implemented)
1. Teacher registers at `/register` with `role=teacher`
2. Selects `teacher_type` (school_teacher or private_tutor) from dropdown
3. System creates `User` + `Teacher` record automatically
4. Teacher can immediately create courses manually
5. Optionally connects Google account to sync courses

### Flow 2: Teacher Invite (Implemented)
1. Another teacher or admin creates invite via `POST /api/invites/` with `invite_type='teacher'`
2. Invite email sent with link to `/accept-invite?token=...`
3. Teacher fills out name + password → `POST /api/auth/accept-invite`
4. System creates User (role=teacher) + Teacher record
5. Teacher is logged in immediately

See `.claude/skills/unified-invites.md` for full invite system details.

### Flow 3: Shadow Teacher Discovery + Invite (Future — Issue #40)
1. Parent/student syncs Google Classroom
2. For each course, system checks if the course teacher exists in EMAI
3. If not found: create a shadow `Teacher` record
4. Send invite via unified invite system
5. Teacher accepts → system creates User, links to Teacher

### Flow 4: Manual Course Creation (Future — Issue #42)
1. Teacher creates a course via `POST /api/teacher/courses`
2. Provides: name, subject, description
3. Teacher adds students by email

## API Endpoints

### Auth Endpoints (current)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | Register with `teacher_type` field (auto-creates Teacher) |
| `/api/auth/accept-invite` | POST | Accept teacher invite (unified) |

### Google Classroom Sync Endpoints (current)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/google/connect` | GET | Get OAuth URL to connect Google account |
| `/api/google/courses/sync` | POST | Sync courses from Google Classroom (sets `teacher_id`) |
| `/api/google/status` | GET | Check Google connection status |
| `/api/courses/teaching` | GET | List all courses taught by current teacher |

### Invite Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/invites/` | POST | Create teacher invite (teacher/admin role) |
| `/api/invites/sent` | GET | List invites sent by current user |

### Teacher Endpoints (future)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/teacher/courses` | POST | Create a course manually (Issue #42) |
| `/api/teacher/courses/{id}/students` | POST | Add student to course by email |
| `/api/teacher/courses/{id}/assignments` | POST | Create assignment for a course (Issue #49) |
| `/api/teacher/google-accounts` | GET | List linked Google accounts (Issue #41) |
| `/api/teacher/google-accounts` | POST | Link a new Google account |
| `/api/teacher/google-accounts/{id}` | DELETE | Unlink a Google account |

## Request/Response Schemas

### UserCreate (registration with teacher_type)
```python
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole
    teacher_type: str | None = None  # only relevant when role=teacher
```

### TeacherResponse
```python
class TeacherResponse(BaseModel):
    id: int
    user_id: int
    school_name: str | None
    department: str | None
    teacher_type: str | None
    created_at: datetime
```

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app/models/teacher.py` | Teacher model with `TeacherType` enum and `teacher_type` column |
| `app/models/invite.py` | Invite model (shared with student invites) |
| `app/api/routes/auth.py` | Register (auto-creates Teacher) + accept-invite |
| `app/api/routes/google_classroom.py` | Google Classroom sync (sets `teacher_id` on courses) |
| `app/api/routes/invites.py` | Create/list invite endpoints |
| `app/schemas/user.py` | UserCreate with optional `teacher_type` |
| `app/schemas/teacher.py` | TeacherResponse schema |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/pages/Register.tsx` | Teacher type selector (conditional on role=teacher) |
| `frontend/src/pages/TeacherDashboard.tsx` | Teacher dashboard with Sync Courses button |
| `frontend/src/pages/AcceptInvite.tsx` | Unified invite acceptance page |
| `frontend/src/api/client.ts` | `authApi.register()` (with teacher_type), `googleApi.syncCourses()`, `invitesApi` |
| `frontend/src/context/AuthContext.tsx` | `register()` accepts teacher_type |

## GitHub Issues
| Issue | Title | Status |
|-------|-------|--------|
| #39 | Auto-create Teacher record at registration | Implemented |
| #40 | Shadow + invite flow for non-EMAI school teachers | Future |
| #41 | Multi-Google account support for all teachers | Future |
| #42 | Manual course creation for teachers | Future |
| #43 | Teacher type distinction (school_teacher vs private_tutor) | Implemented |
| #49 | Manual assignment creation for teachers | Future |
| #52 | Teacher Google Classroom course sync (teacher_id fix) | Implemented |
| #53 | Background periodic Google Classroom sync | Phase 1.5 |

## Implementation Notes
- `teacher_type` is nullable on the Teacher model (not required)
- Registration auto-creates Teacher record; no separate "create profile" step needed
- Teacher invites expire after 30 days (vs 7 days for student invites)
- Shadow teacher support (user_id nullable, is_platform_user flag) is planned but not yet implemented
- Multi-Google account support is planned for all teachers (not just private tutors); currently uses `User.google_access_token`
- Google Classroom sync now sets `teacher_id` on courses (Issue #52 fix)
