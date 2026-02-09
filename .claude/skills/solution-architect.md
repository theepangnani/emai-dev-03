# /solution-architect - Solution Design & Architecture Review

Design and review architecture decisions following DDD (Domain-Driven Design) principles for the ClassBridge platform.

## Architecture Principles

### Domain-Driven Design
This project follows DDD with these bounded contexts:

| Context | Backend Domain | Frontend Domain | Aggregate Roots |
|---------|---------------|-----------------|-----------------|
| **Auth & Identity** | `domains/auth/` | `core/context/` | User |
| **Education** | `domains/education/` | `domains/education/` | Course (owns Assignment, CourseContent) |
| **Study Tools** | `domains/study/` | `domains/study/` | StudyGuide (owns versions) |
| **Tasks & Planning** | `domains/tasks/` | `domains/tasks/` | Task |
| **Communication** | `domains/communication/` | `domains/messages/` | Conversation (owns Messages) |
| **Notifications** | `domains/notifications/` | `shared/` | Notification |

### Backend Architecture (Target)

```
app/
├── domains/{context}/
│   ├── models.py        # SQLAlchemy entities
│   ├── schemas.py       # Pydantic DTOs (decoupled from models)
│   ├── services.py      # Business logic (domain rules, validation)
│   ├── repository.py    # Data access abstraction (SQLAlchemy queries)
│   └── routes.py        # Thin HTTP controllers delegating to services
├── shared/
│   ├── events.py        # Domain event bus (publish/subscribe)
│   ├── repository.py    # BaseRepository with common CRUD
│   └── value_objects.py # Priority, ContentType, UserRole, etc.
├── infrastructure/
│   ├── google/          # Classroom/Gmail anti-corruption layer
│   ├── ai/              # OpenAI adapter
│   ├── email/           # SendGrid adapter
│   └── scheduler/       # APScheduler jobs
├── core/                # Config, security, logging
└── db/                  # Engine, Base, session factory
```

### Frontend Architecture (Target)

```
src/
├── core/
│   ├── api/             # Domain-specific API modules (not monolithic)
│   ├── hooks/           # Shared utility hooks
│   └── context/         # AuthContext (global state)
├── domains/{context}/
│   ├── components/      # Domain UI components
│   ├── hooks/           # Domain data hooks (TanStack Query)
│   └── pages/           # Route-level pages
├── shared/
│   ├── components/      # DashboardLayout, ProtectedRoute, NotificationBell
│   └── styles/          # Global CSS, variables
└── App.tsx
```

## Design Review Checklist

When designing or reviewing a feature:

### 1. Domain Boundaries
- [ ] Does the feature belong to a single bounded context?
- [ ] If it crosses contexts, are interactions through explicit interfaces (events, service calls)?
- [ ] No raw model imports from other domains in route handlers

### 2. Layer Separation
- [ ] Routes are thin controllers (< 20 LOC per handler)
- [ ] Business logic lives in domain services
- [ ] Data access goes through repository methods
- [ ] Schemas are proper DTOs, not ORM mirrors

### 3. Frontend Modularity
- [ ] No page file exceeds ~300 LOC
- [ ] Data fetching uses TanStack Query hooks
- [ ] Domain components are self-contained with co-located CSS
- [ ] Shared state uses React Context or query cache (not prop drilling)

### 4. Cross-Cutting Concerns
- [ ] Authentication: `get_current_user` dependency (backend) / AuthContext (frontend)
- [ ] Authorization: Domain services check permissions, not routes
- [ ] Logging: Structured via `core/logging_config.py`
- [ ] Error handling: Domain exceptions mapped to HTTP status in routes

## Key Patterns

### Repository Pattern
```python
class BaseRepository:
    def __init__(self, db: Session):
        self.db = db

class TaskRepository(BaseRepository):
    def find_for_user(self, user_id: int, filters: TaskFilters) -> list[Task]:
        query = self.db.query(Task).filter(...)
        return query.all()
```

### Domain Service
```python
class TaskService:
    def __init__(self, task_repo: TaskRepository, user_repo: UserRepository):
        self.task_repo = task_repo
        self.user_repo = user_repo

    def assign_task(self, task: Task, assignee_id: int, creator: User) -> Task:
        # Business logic: validate relationship, set fields
        ...
```

### Domain Events
```python
class TaskAssignedEvent(DomainEvent):
    task_id: int
    assigned_to_user_id: int

# Handler in notifications domain:
@event_bus.subscribe(TaskAssignedEvent)
def handle_task_assigned(event):
    notification_service.create(...)
```

### Frontend Query Hook
```typescript
export function useTasks(filters: TaskFilters) {
  return useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => tasksApi.list(filters),
    staleTime: 5 * 60 * 1000,
  });
}
```

## Anti-Patterns to Avoid

- **Anemic models**: Models should not be pure data bags. Move validation and simple business rules onto the model.
- **God routes**: Route handlers doing 50+ LOC of business logic. Extract to services.
- **Cross-domain imports**: `tasks/routes.py` importing `education/models.py` directly. Use repository interfaces.
- **Monolithic frontend files**: Pages > 300 LOC. Extract domain components + hooks.
- **Manual fetch patterns**: Using raw useState + useEffect for API calls. Use TanStack Query.

## Migration Issues

| Issue | Description | Status |
|-------|-------------|--------|
| #127 | Split api/client.ts into domain modules | Open |
| #128 | Extract backend domain services | Open |
| #129 | Introduce repository pattern | Open |
| #130 | Split ParentDashboard into sub-components | Open |
| #131 | Activate TanStack Query | Open |
| #132 | Reorganize backend into domain modules | Open |
| #133 | Reorganize frontend into domain modules | Open |
| #134 | Add domain events | Open |

## Cross-DB Compatibility

Per MEMORY.md:
- Use `String(N)` not `Enum` for cross-DB column types
- Use `DEFAULT FALSE` not `DEFAULT 0` for booleans
- Use `TIMESTAMPTZ` for PostgreSQL, `DATETIME` for SQLite
- Use `field_validator` for normalization in Pydantic schemas
