# Unified Invite System

## Overview
ClassBridge uses a shared invite system for both student and teacher invitations. Invites are stored in a single `invites` table with an `invite_type` discriminator. The accept-invite flow creates the appropriate User + profile records and auto-links relationships.

## Data Model

### `invites` Table
```python
class InviteType(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"

class Invite(Base):
    __tablename__ = "invites"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, index=True)
    invite_type = Column(Enum(InviteType), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    invited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metadata_json = Column(JSON, nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Token Expiry
- **Student invites:** 7 days
- **Teacher invites:** 30 days

### Metadata JSON
Stores context-specific data:
- Student invite from parent: `{"relationship_type": "mother"}`
- Teacher invite: `{"teacher_type": "school_teacher"}` (optional)

## API Endpoints

### Invite Management
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/invites/` | POST | Parents (student invites), Teachers/Admins (teacher invites) | Create and send invite |
| `/api/invites/sent` | GET | Any authenticated user | List invites sent by current user |

### Accept Invite (Auth)
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/accept-invite` | POST | None (public) | Accept invite, create account, return JWT |

## Request/Response Schemas

### InviteCreate
```python
class InviteCreate(BaseModel):
    email: EmailStr
    invite_type: str        # "student" or "teacher"
    metadata: dict | None   # e.g., {"relationship_type": "mother"}
```

### AcceptInviteRequest
```python
class AcceptInviteRequest(BaseModel):
    token: str
    password: str
    full_name: str
```

### InviteResponse
```python
class InviteResponse(BaseModel):
    id: int
    email: str
    invite_type: str
    token: str
    expires_at: datetime
    invited_by_user_id: int
    metadata_json: dict | None
    accepted_at: datetime | None
    created_at: datetime
```

## Accept-Invite Flow

1. Validate token (exists, not expired, not already accepted)
2. Check email not already registered
3. Create `User` with appropriate role (student or teacher)
4. Create `Teacher` or `Student` profile record
5. **If student invite from parent:** auto-link via `parent_students` join table using `relationship_type` from metadata
6. **If teacher invite:** optionally set `teacher_type` from metadata
7. Mark invite as accepted (`accepted_at` set)
8. Return JWT token (user is logged in immediately)

## Email Integration
Uses `app/services/email_service.py` (SendGrid) to send invite emails with a link to `{frontend_url}/accept-invite?token={token}`.

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app/models/invite.py` | Invite model + InviteType enum |
| `app/schemas/invite.py` | InviteCreate, InviteResponse, AcceptInviteRequest |
| `app/api/routes/invites.py` | POST /invites/, GET /invites/sent |
| `app/api/routes/auth.py` | POST /auth/accept-invite |
| `app/services/email_service.py` | SendGrid email delivery |

### Frontend
| File | Purpose |
|------|---------|
| `frontend/src/pages/AcceptInvite.tsx` | Accept invite page (reads token from URL) |
| `frontend/src/pages/ParentDashboard.tsx` | "Invite Student" button + modal |
| `frontend/src/api/client.ts` | `invitesApi.create()`, `invitesApi.listSent()`, `authApi.acceptInvite()` |
| `frontend/src/App.tsx` | `/accept-invite` route |

## Implementation Notes
- Tokens are generated with `secrets.token_urlsafe(32)`
- Duplicate pending invites to the same email+type are rejected
- The invite email is fire-and-forget (doesn't block on send failure)
- Invites are soft-completed (accepted_at set) rather than deleted
- The frontend `/accept-invite` page is public (no auth required)
