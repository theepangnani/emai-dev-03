# Parent-Student Registration & Linking

## Overview
ClassBridge uses a many-to-many relationship between parents and students. Parent linking is optional — students can use the platform independently. A student can have multiple parents (mother, father, guardian), and a parent can have multiple children.

## Data Model

### `parent_students` Join Table
```sql
CREATE TABLE parent_students (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER NOT NULL REFERENCES users(id),
    student_id INTEGER NOT NULL REFERENCES students(id),
    relationship_type VARCHAR(50) NOT NULL DEFAULT 'guardian',  -- mother, father, guardian, other
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_id, student_id)
);
```

**Note:** This replaces the previous `Student.parent_id` single FK column.

### Relationship Types
- `mother` — Biological or adoptive mother
- `father` — Biological or adoptive father
- `guardian` — Legal guardian
- `other` — Other relationship

## Three Registration Paths

### Path 1: Parent-Created Student
1. Parent fills out form in Parent Dashboard (child name, email, grade, school)
2. `POST /api/parent/children/register` creates:
   - `User` record (role=student, no password)
   - `Student` record (grade_level, school_name)
   - `parent_students` entry with relationship_type
3. Invite email sent to student's email with a secure token (via SendGrid)
4. Student clicks invite link → `POST /api/auth/accept-invite` with token + new password
5. Student can now log in independently

### Path 2: Self-Registered Student
1. Student registers at `/auth/register` with role=student
2. Links to Google Classroom, manages own courses
3. No parent required — platform fully functional
4. Can be linked to parent(s) later if desired

### Path 3: Link After the Fact
1. Parent links to existing student via:
   - **By email**: `POST /api/parent/children/link`
   - **Google Classroom discovery**: `POST /api/parent/children/discover-google` → `POST /api/parent/children/link-bulk`
2. Creates new `parent_students` entry
3. Multiple parents can link to the same student

## API Endpoints

### Parent Endpoints (parent role only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/parent/children` | GET | List all linked children |
| `/api/parent/children/register` | POST | Create a student account for a child |
| `/api/parent/children/link` | POST | Link to existing student by email |
| `/api/parent/children/discover-google` | POST | Discover students via Google Classroom |
| `/api/parent/children/link-bulk` | POST | Bulk link discovered students |
| `/api/parent/children/{student_id}/overview` | GET | Child's courses, assignments, study guides |

### Auth Endpoints (Unified Invite System)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/accept-invite` | POST | Accept invite and set password (unified for student + teacher invites) |

**Note:** Uses the shared `invites` table with `invite_type='student'`. See REQUIREMENTS.md Section 6.3 for the unified invite system.

## Request/Response Schemas

### RegisterChildRequest
```python
class RegisterChildRequest(BaseModel):
    full_name: str
    email: EmailStr
    grade_level: Optional[int]       # e.g., 5-12
    school_name: Optional[str]
    relationship_type: str = "guardian"  # mother, father, guardian, other
```

### AcceptInviteRequest
```python
class AcceptInviteRequest(BaseModel):
    token: str
    password: str
```

### LinkChildRequest (updated)
```python
class LinkChildRequest(BaseModel):
    student_email: str
    relationship_type: str = "guardian"
```

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app/models/student.py` | Student model + `parent_students` join table |
| `app/models/user.py` | User model with invite_token fields |
| `app/api/routes/parent.py` | Parent endpoints (register, link, list, overview) |
| `app/api/routes/auth.py` | Accept invite endpoint |
| `app/schemas/parent.py` | Request/response schemas |
| `app/services/email_service.py` | Send invite emails via SendGrid |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/pages/ParentDashboard.tsx` | Register child form, linked children list |
| `frontend/src/api/client.ts` | `parentApi.registerChild()`, `authApi.acceptInvite()` |

## Implementation Notes
- Invite tokens should expire after 7 days
- Add `invite_token` and `invite_token_expires` columns to `User` model
- The `parent_students` table has a UNIQUE constraint on (parent_id, student_id)
- When a parent registers a child, the User is created without a password (hashed_password=NULL)
- The student cannot log in until they accept the invite and set a password
- Existing `Student.parent_id` column should be migrated to `parent_students` entries then removed
