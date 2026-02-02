# Parent-Student Registration & Linking

## Overview
ClassBridge uses a many-to-many relationship between parents and students. Parent linking is optional — students can use the platform independently. A student can have multiple parents (mother, father, guardian), and a parent can have multiple children.

## Data Model

### `parent_students` Join Table
```python
class RelationshipType(str, enum.Enum):
    MOTHER = "mother"
    FATHER = "father"
    GUARDIAN = "guardian"
    OTHER = "other"

parent_students = Table(
    "parent_students",
    Base.metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("parent_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("student_id", Integer, ForeignKey("students.id"), nullable=False),
    Column("relationship_type", Enum(RelationshipType), default=RelationshipType.GUARDIAN),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
```

**Note:** This replaces the previous `Student.parent_id` single FK column. The Student model now has a `parents` relationship via `secondary=parent_students`.

### Relationship Types
- `mother` — Biological or adoptive mother
- `father` — Biological or adoptive father
- `guardian` — Legal guardian
- `other` — Other relationship

## Three Registration Paths

### Path 1: Parent Invites Student (Unified Invite System)
1. Parent clicks "Invite Student" on ParentDashboard
2. `POST /api/invites/` creates an invite with `invite_type='student'` and metadata `{"relationship_type": "mother"}`
3. Invite email sent with a link to `/accept-invite?token=...`
4. Student clicks link → fills out name + password → `POST /api/auth/accept-invite`
5. System creates User (role=student), Student record, auto-links via `parent_students`
6. Student is logged in immediately (JWT returned)

See `.claude/skills/unified-invites.md` for full invite system details.

### Path 2: Self-Registered Student
1. Student registers at `/register` with role=student
2. System auto-creates `Student` record (via auth.py register endpoint)
3. Links to Google Classroom, manages own courses
4. No parent required — platform fully functional
5. Can be linked to parent(s) later if desired

### Path 3: Link After the Fact
1. Parent links to existing student via:
   - **By email**: `POST /api/parent/children/link` with `relationship_type`
   - **Google Classroom discovery**: `POST /api/parent/children/discover-google` → `POST /api/parent/children/link-bulk`
2. Creates new `parent_students` entry
3. Multiple parents can link to the same student

## API Endpoints

### Parent Endpoints (parent role only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/parent/children` | GET | List all linked children (with relationship_type) |
| `/api/parent/children/link` | POST | Link to existing student by email |
| `/api/parent/children/discover-google` | POST | Discover students via Google Classroom |
| `/api/parent/children/link-bulk` | POST | Bulk link discovered students |
| `/api/parent/children/{student_id}/overview` | GET | Child's courses, assignments, study guides |

### Invite Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/invites/` | POST | Create student invite (parent role) |
| `/api/auth/accept-invite` | POST | Accept invite and create account |

## Request/Response Schemas

### LinkChildRequest
```python
class LinkChildRequest(BaseModel):
    student_email: str
    relationship_type: str = "guardian"
```

### ChildSummary
```python
class ChildSummary(BaseModel):
    student_id: int
    user_id: int
    full_name: str
    grade_level: int | None
    school_name: str | None
    relationship_type: str | None
```

### LinkChildrenBulkRequest
```python
class LinkChildrenBulkRequest(BaseModel):
    user_ids: list[int]
    relationship_type: str = "guardian"
```

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app/models/student.py` | Student model + `parent_students` join table + `RelationshipType` enum |
| `app/models/invite.py` | Invite model for student invitations |
| `app/api/routes/parent.py` | Parent endpoints (link, list, overview, discover) |
| `app/api/routes/invites.py` | Create/list invite endpoints |
| `app/api/routes/auth.py` | Register (auto-creates Student) + accept-invite endpoint |
| `app/api/routes/messages.py` | Parent/teacher recipient lookup via `parent_students` join |
| `app/jobs/assignment_reminders.py` | Iterates `parent_students` for reminder notifications |
| `app/schemas/parent.py` | LinkChildRequest, ChildSummary, ChildOverview, etc. |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/pages/ParentDashboard.tsx` | Link child modal (with relationship type), invite student modal |
| `frontend/src/pages/AcceptInvite.tsx` | Accept invite page |
| `frontend/src/api/client.ts` | `parentApi.linkChild()`, `invitesApi.create()`, `authApi.acceptInvite()` |

## Implementation Notes
- The `parent_students` table allows multiple parents per student (no unique constraint on student_id alone)
- A unique constraint exists on (parent_id, student_id) to prevent duplicate links
- Assignment reminders iterate all `parent_students` rows, so each parent gets their own notifications
- Messages route uses `parent_students` join to determine valid parent↔teacher recipients
- Auto-create: registering as student auto-creates a `Student` record; registering as teacher auto-creates a `Teacher` record
