# Feature Flags System — Detailed Design

**Issue:** #TBD (epic)
**Author:** Claude Code
**Date:** 2026-03-01
**Status:** Draft — Pending Review

---

## 1. Problem Statement

ClassBridge has features at various stages of readiness (Phase 1, 1.5, 2, 3+). Currently, all implemented features are always visible to their authorized roles. There is no mechanism to:

1. **Disable incomplete/untested features** in production (e.g., School Board Integration before DTAP approval)
2. **Gradually roll out features** to subsets of users (beta testing)
3. **Kill-switch** a misbehaving feature without a code deploy
4. **Gate premium features** separately from subscription tiers

The admin team needs a centralized panel to toggle features on/off at runtime without code changes.

---

## 2. Goals

| Goal | Description |
|------|-------------|
| **Admin-controlled** | Admins toggle features from `/admin/features` page — no .env or code deploy needed |
| **Instant effect** | Toggling a flag immediately hides/shows the feature for all users |
| **Backend + Frontend** | Both API endpoints AND UI elements respect flags |
| **Audit trail** | Every toggle change is logged to the existing `audit_logs` table |
| **Seed defaults** | On first deploy, seed known features with sensible defaults (e.g., School Board Integration = OFF) |
| **Zero downtime** | Feature flag checks add negligible overhead (<1ms per request) |

---

## 3. Architecture Overview

```
┌────────────────────────────────┐
│  Admin Feature Flags Page      │
│  /admin/features               │
│  Toggle switches + descriptions│
└───────────┬────────────────────┘
            │ PATCH /api/admin/features/{key}
            ▼
┌────────────────────────────────┐
│  Backend: feature_flags table  │
│  key (PK) | enabled | metadata│
│  Cached in memory (60s TTL)    │
└───────────┬────────────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
┌──────────┐  ┌──────────────┐
│ Backend  │  │ Frontend     │
│ Guard    │  │ Guard        │
│ require_ │  │ useFeature   │
│ feature()│  │ Flag() hook  │
│ dep      │  │ + context    │
└──────────┘  └──────────────┘
```

---

## 4. Database Model

### `feature_flags` table

```python
# app/models/feature_flag.py

class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key         = Column(String(100), primary_key=True, index=True)  # e.g. "school_board_integration"
    enabled     = Column(Boolean, default=False, nullable=False)
    label       = Column(String(200), nullable=False)                # Human-readable name
    description = Column(Text, nullable=True)                        # Longer explanation
    category    = Column(String(50), default="general")              # Group: "integration", "ai", "admin", etc.
    phase       = Column(String(20), nullable=True)                  # "phase-1", "phase-2", "phase-3"
    updated_at  = Column(DateTime, default=func.now(), onupdate=func.now())
    updated_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
```

**Rationale:**
- `key` as PK — simple string lookups, no auto-increment ID needed
- `category` — groups flags in the admin UI (Integration, AI, Admin, etc.)
- `phase` — informational, shows which roadmap phase the feature belongs to
- No `created_at` — flags are seeded at startup, the seed date is irrelevant

---

## 5. Seed Data (Initial Feature Flags)

On startup, the system inserts missing flags (idempotent — does NOT overwrite existing values). This follows the existing `main.py` startup migration pattern.

```python
FEATURE_FLAG_SEEDS = [
    {
        "key": "school_board_integration",
        "enabled": False,
        "label": "School Board Integration",
        "description": "Board-specific course catalogs, student-board linking, board selection in student profiles. Requires DTAP approval for each board.",
        "category": "integration",
        "phase": "phase-3",
    },
    {
        "key": "mcp_integration",
        "enabled": False,
        "label": "MCP Protocol Integration",
        "description": "Model Context Protocol server and client. Enables AI assistants (Claude Desktop, Cursor) to interact with ClassBridge data.",
        "category": "ai",
        "phase": "phase-2",
    },
    {
        "key": "tutor_marketplace",
        "enabled": False,
        "label": "Tutor Marketplace",
        "description": "Public tutor profiles, availability scheduling, parent booking flow, tutor dashboard.",
        "category": "feature",
        "phase": "phase-4",
    },
    {
        "key": "brightspace_lms",
        "enabled": False,
        "label": "Brightspace LMS Integration",
        "description": "D2L Brightspace OAuth2 connection, course/assignment sync, per-institution registration.",
        "category": "integration",
        "phase": "phase-2",
    },
    {
        "key": "teachassist_integration",
        "enabled": False,
        "label": "TeachAssist Integration",
        "description": "TeachAssist grade scraping and sync for Ontario schools.",
        "category": "integration",
        "phase": "phase-2",
    },
    {
        "key": "ai_insights",
        "enabled": True,
        "label": "AI Insights",
        "description": "GPT-powered holistic child academic analysis with strengths, concerns, and action items.",
        "category": "ai",
        "phase": "phase-2",
    },
    {
        "key": "mock_exams",
        "enabled": True,
        "label": "AI Mock Exam Generator",
        "description": "AI-generated multiple choice exams with timer, scoring, and explanations.",
        "category": "ai",
        "phase": "phase-2",
    },
    {
        "key": "course_planning",
        "enabled": True,
        "label": "Course Planning",
        "description": "Multi-year academic planning with AI recommendations and graduation tracking.",
        "category": "feature",
        "phase": "phase-2",
    },
]
```

**Adding new flags:** Developers simply add a new entry to `FEATURE_FLAG_SEEDS`. The startup function inserts it if the key doesn't exist. Admins can then enable/disable it from the UI.

---

## 6. Backend Implementation

### 6.1 Feature Flag Service (`app/services/feature_flags.py`)

```python
from functools import lru_cache
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

_cache: dict[str, bool] = {}
_cache_expiry: datetime = datetime.min

CACHE_TTL_SECONDS = 60

def _refresh_cache(db: Session) -> None:
    global _cache, _cache_expiry
    flags = db.query(FeatureFlag).all()
    _cache = {f.key: f.enabled for f in flags}
    _cache_expiry = datetime.utcnow() + timedelta(seconds=CACHE_TTL_SECONDS)

def is_feature_enabled(db: Session, key: str) -> bool:
    """Check if a feature flag is enabled. Returns False for unknown keys."""
    if datetime.utcnow() > _cache_expiry:
        _refresh_cache(db)
    return _cache.get(key, False)

def invalidate_cache() -> None:
    """Force cache refresh on next check (called after admin toggle)."""
    global _cache_expiry
    _cache_expiry = datetime.min
```

**Design decisions:**
- **In-memory cache with 60s TTL** — Avoids DB query on every request. Single-instance deployment (Cloud Run) means no multi-node consistency issues.
- **Unknown key = False** — Safe default. If a flag key is misspelled, the feature stays off.
- **Cache invalidation** — Admin toggle immediately invalidates, so changes take effect within milliseconds for that instance.

### 6.2 Backend Guard Dependency (`app/api/deps.py`)

```python
from app.services.feature_flags import is_feature_enabled

def require_feature(flag_key: str):
    """FastAPI dependency factory — returns 404 if feature is disabled."""
    def checker(db: Session = Depends(get_db)):
        if not is_feature_enabled(db, flag_key):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feature not available",
            )
    return checker
```

**Usage in routes:**

```python
# app/api/routes/course_planning.py
@router.get("/course-planning/catalogs")
def list_catalogs(
    db: Session = Depends(get_db),
    _flag: None = Depends(require_feature("school_board_integration")),
    user: User = Depends(require_role(UserRole.PARENT, UserRole.STUDENT)),
):
    ...
```

**Why 404 instead of 403?** — A disabled feature should appear as if it doesn't exist, not as a permission error. This prevents confusion ("I have the right role, why can't I access it?") and avoids leaking information about hidden features.

### 6.3 Admin API Endpoints (`app/api/routes/admin.py`)

```
GET  /api/admin/features              — List all feature flags (admin only)
PATCH /api/admin/features/{key}       — Toggle a feature flag (admin only)
GET  /api/features/enabled            — Public: list of enabled flag keys (for frontend)
```

**Endpoint details:**

```python
# GET /api/admin/features
# Response: list of FeatureFlagResponse
class FeatureFlagResponse(BaseModel):
    key: str
    enabled: bool
    label: str
    description: str | None
    category: str
    phase: str | None
    updated_at: datetime | None
    updated_by_name: str | None  # resolved from users table

# PATCH /api/admin/features/{key}
# Request body:
class FeatureFlagUpdate(BaseModel):
    enabled: bool

# Response: FeatureFlagResponse
# Side effects: audit log entry, cache invalidation

# GET /api/features/enabled
# Response: {"enabled_features": ["ai_insights", "mock_exams", "course_planning"]}
# Auth: any authenticated user (no role requirement)
# Purpose: Frontend uses this to decide what to show/hide
```

### 6.4 Audit Logging

Every toggle produces an audit log entry via the existing `log_action()` helper:

```python
log_action(
    db,
    user_id=current_user.id,
    action="feature_flag_toggle",
    resource_type="feature_flag",
    resource_id=flag.key,
    details={"key": flag.key, "enabled": new_value, "previous": old_value},
    ip_address=request.client.host,
)
```

---

## 7. Frontend Implementation

### 7.1 Feature Flags Context (`frontend/src/context/FeatureFlagContext.tsx`)

```typescript
interface FeatureFlagContextType {
  enabledFeatures: Set<string>;
  isFeatureEnabled: (key: string) => boolean;
  isLoading: boolean;
}

// Provider wraps the app (inside AuthProvider, after login)
// Fetches GET /api/features/enabled on mount + every 60s
// Stores enabled keys in a Set for O(1) lookups
```

### 7.2 `useFeatureFlag` Hook

```typescript
export function useFeatureFlag(key: string): boolean {
  const { isFeatureEnabled } = useContext(FeatureFlagContext);
  return isFeatureEnabled(key);
}
```

### 7.3 `<FeatureGate>` Component

```typescript
interface FeatureGateProps {
  flag: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;  // optional "coming soon" placeholder
}

export function FeatureGate({ flag, children, fallback = null }: FeatureGateProps) {
  const enabled = useFeatureFlag(flag);
  return enabled ? <>{children}</> : <>{fallback}</>;
}
```

### 7.4 Usage in Navigation (`DashboardLayout.tsx`)

```typescript
// Before (always shown):
items.push({ label: 'Find a Tutor', path: '/tutor-marketplace', icon: '...' });

// After (conditionally shown):
if (isFeatureEnabled('tutor_marketplace')) {
  items.push({ label: 'Find a Tutor', path: '/tutor-marketplace', icon: '...' });
}
```

### 7.5 Usage in Route Protection (`App.tsx`)

```typescript
<Route path="/tutor-marketplace" element={
  <FeatureGate flag="tutor_marketplace" fallback={<Navigate to="/dashboard" />}>
    <ProtectedRoute allowedRoles={['parent', 'student']}>
      <TutorMarketplacePage />
    </ProtectedRoute>
  </FeatureGate>
} />
```

### 7.6 Feature Constants (`frontend/src/constants/features.ts`)

```typescript
// Centralized flag key constants to prevent typos
export const FEATURES = {
  SCHOOL_BOARD_INTEGRATION: 'school_board_integration',
  MCP_INTEGRATION: 'mcp_integration',
  TUTOR_MARKETPLACE: 'tutor_marketplace',
  BRIGHTSPACE_LMS: 'brightspace_lms',
  TEACHASSIST_INTEGRATION: 'teachassist_integration',
  AI_INSIGHTS: 'ai_insights',
  MOCK_EXAMS: 'mock_exams',
  COURSE_PLANNING: 'course_planning',
} as const;
```

---

## 8. Admin Feature Flags Page (`/admin/features`)

### 8.1 UI Wireframe

```
┌─────────────────────────────────────────────────────┐
│  Feature Management                                 │
│  Control which features are available to users       │
│                                                     │
│  ┌─ Filter: [All ▾] [Search...            ]        │
│  │                                                  │
│  │  INTEGRATION                                     │
│  │  ┌──────────────────────────────────────────┐    │
│  │  │ 🔌 School Board Integration    [  OFF  ] │    │
│  │  │ Phase 3 · Board-specific course catalogs,│    │
│  │  │ student-board linking. Requires DTAP.    │    │
│  │  │ Last changed: never                      │    │
│  │  └──────────────────────────────────────────┘    │
│  │  ┌──────────────────────────────────────────┐    │
│  │  │ 🔌 Brightspace LMS Integration [  OFF  ] │    │
│  │  │ Phase 2 · D2L Brightspace OAuth2, per-   │    │
│  │  │ institution sync.                        │    │
│  │  │ Last changed: never                      │    │
│  │  └──────────────────────────────────────────┘    │
│  │                                                  │
│  │  AI                                              │
│  │  ┌──────────────────────────────────────────┐    │
│  │  │ 🤖 MCP Protocol Integration    [  OFF  ] │    │
│  │  │ Phase 2 · MCP server/client for AI       │    │
│  │  │ assistants.                              │    │
│  │  │ Last changed: never                      │    │
│  │  └──────────────────────────────────────────┘    │
│  │  ┌──────────────────────────────────────────┐    │
│  │  │ 🤖 AI Insights                 [  ON   ] │    │
│  │  │ Phase 2 · GPT-powered child analysis.    │    │
│  │  │ Last changed: 2026-02-28 by admin@...    │    │
│  │  └──────────────────────────────────────────┘    │
│  │                                                  │
│  │  FEATURE                                         │
│  │  ┌──────────────────────────────────────────┐    │
│  │  │ ⭐ Tutor Marketplace           [  OFF  ] │    │
│  │  │ Phase 4 · Public tutor profiles, booking.│    │
│  │  │ Last changed: never                      │    │
│  │  └──────────────────────────────────────────┘    │
│  └──────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────┘
```

### 8.2 Toggle Confirmation

Toggling a feature shows a confirmation dialog:

```
┌────────────────────────────────────┐
│  Disable "AI Insights"?            │
│                                    │
│  This will immediately hide the    │
│  feature for all users.            │
│                                    │
│  [Cancel]  [Disable Feature]       │
└────────────────────────────────────┘
```

---

## 9. Feature Flag Enforcement Points

For the **initial delivery** (Phase 1 — School Board Integration OFF), these are the specific enforcement points:

### 9.1 School Board Integration (`school_board_integration`)

| Layer | File | What to guard |
|-------|------|---------------|
| Backend | `app/api/routes/course_planning.py` | School board-scoped catalog endpoints |
| Backend | `app/api/routes/profile.py` | `school_board_id` field in student edit |
| Frontend | `DashboardLayout.tsx` | Hide "Course Planning" nav if flag is off (or show but hide board-specific sections) |
| Frontend | `MyKidsPage.tsx` / Edit Child modal | Hide "School Board" dropdown |
| Frontend | `CoursePlanningPage.tsx` | Hide board-scoped catalog browser |

### 9.2 MCP Integration (`mcp_integration`)

| Layer | File | What to guard |
|-------|------|---------------|
| Backend | `main.py` | Skip MCP server mount if flag is off |
| Backend | `app/api/routes/api_keys.py` | Hide/disable API key creation if MCP is off |
| Frontend | `DashboardLayout.tsx` | Hide "API Keys" nav item |
| Frontend | `APIKeysPage.tsx` | Show "coming soon" or redirect |

### 9.3 Tutor Marketplace (`tutor_marketplace`)

| Layer | File | What to guard |
|-------|------|---------------|
| Backend | `app/api/routes/tutors.py` | All tutor marketplace endpoints |
| Frontend | `DashboardLayout.tsx` | Hide "Find a Tutor" and "Tutor Dashboard" nav items |
| Frontend | `TutorMarketplacePage.tsx` | Redirect if accessed directly |
| Frontend | `TutorDashboardPage.tsx` | Redirect if accessed directly |

---

## 10. Migration & Startup

Following the existing `main.py` pattern (idempotent `ALTER TABLE` in try/except):

```python
# In main.py startup_event():

# 1. Create feature_flags table (handled by Base.metadata.create_all)
# 2. Seed default flags
def _seed_feature_flags(conn):
    """Insert default feature flags if they don't exist (idempotent)."""
    for seed in FEATURE_FLAG_SEEDS:
        result = conn.execute(
            text("SELECT key FROM feature_flags WHERE key = :key"),
            {"key": seed["key"]}
        )
        if result.fetchone() is None:
            conn.execute(
                text("""
                    INSERT INTO feature_flags (key, enabled, label, description, category, phase)
                    VALUES (:key, :enabled, :label, :description, :category, :phase)
                """),
                seed
            )
    conn.commit()
```

---

## 11. Implementation Plan (Sub-Issues)

| # | Task | Effort | Dependencies |
|---|------|--------|--------------|
| 1 | **FeatureFlag model + seed migration** | S | None |
| 2 | **Feature flag service (cache + check)** | S | #1 |
| 3 | **`require_feature()` dependency** | S | #2 |
| 4 | **Admin API endpoints** (list, toggle) | M | #1, #2 |
| 5 | **Public `/api/features/enabled` endpoint** | S | #2 |
| 6 | **Frontend FeatureFlagContext + hook** | M | #5 |
| 7 | **Admin Feature Management page** | M | #4, #6 |
| 8 | **Guard: School Board Integration** | M | #3, #6 |
| 9 | **Guard: MCP Integration** | S | #3, #6 |
| 10 | **Guard: Tutor Marketplace** | S | #3, #6 |
| 11 | **Guard: Brightspace LMS** | S | #3, #6 |
| 12 | **Tests** | M | All above |

**Total effort:** ~2 batches of parallel agent work

---

## 12. API Contract

### `GET /api/admin/features`
**Auth:** Admin only
**Response 200:**
```json
[
  {
    "key": "school_board_integration",
    "enabled": false,
    "label": "School Board Integration",
    "description": "Board-specific course catalogs...",
    "category": "integration",
    "phase": "phase-3",
    "updated_at": null,
    "updated_by_name": null
  }
]
```

### `PATCH /api/admin/features/{key}`
**Auth:** Admin only
**Request:**
```json
{ "enabled": true }
```
**Response 200:**
```json
{
  "key": "school_board_integration",
  "enabled": true,
  "label": "School Board Integration",
  "description": "Board-specific course catalogs...",
  "category": "integration",
  "phase": "phase-3",
  "updated_at": "2026-03-01T10:30:00",
  "updated_by_name": "Admin User"
}
```

### `GET /api/features/enabled`
**Auth:** Any authenticated user
**Response 200:**
```json
{
  "enabled_features": ["ai_insights", "mock_exams", "course_planning"]
}
```

---

## 13. Non-Functional Requirements

| NFR | Target |
|-----|--------|
| **Latency** | Feature check < 1ms (in-memory cache) |
| **Cache TTL** | 60 seconds (configurable via `FEATURE_FLAG_CACHE_TTL` env var) |
| **Availability** | Flag check defaults to `False` on DB error (fail closed) |
| **Audit** | Every toggle logged with user, timestamp, old/new value |
| **Scalability** | If moving to multi-instance, switch to Redis-based cache |

---

## 14. Future Enhancements (Out of Scope for v1)

- **Per-user flags** — Enable a feature for specific users (beta testers)
- **Percentage rollout** — Enable for X% of users
- **Environment-specific** — Different defaults for dev/staging/prod
- **Flag dependencies** — "Feature B requires Feature A to be enabled"
- **Scheduled toggles** — "Enable feature X on date Y"

These are intentionally deferred. The current design is a simple on/off toggle per feature, which covers the stated requirements.
