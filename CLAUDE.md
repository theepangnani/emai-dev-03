# CLAUDE.md

## Project Overview
EMAI (ClassBridge) — AI-powered education platform (parents, students, teachers, admins). Google Classroom integration, AI study tools, messaging, teacher email monitoring.

## Tech Stack
- **Backend:** FastAPI, Python 3.13+, SQLAlchemy 2.0, Pydantic 2.x
- **Frontend:** React 19, TypeScript, Vite, React Router 7, TanStack React Query, Axios
- **DB:** SQLite (dev), PostgreSQL (prod)
- **AI:** OpenAI (gpt-4o-mini) | **Auth:** JWT, OAuth2 | **Email:** SendGrid
- **Deploy:** GCP Cloud Run

## Commands
```bash
# Backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pytest

# Frontend (from frontend/)
npm run dev    # :5173
npm run build  # tsc -b && vite build
npm run lint
```

## Architecture
- `app/api/routes/` — Routers (mounted under `/api`)
- `app/api/deps.py` — `get_db()`, `get_current_user()`, `require_role(*roles)`
- `app/models/` — SQLAlchemy models
- `app/schemas/` — Pydantic schemas (`from_attributes = True`)
- `app/services/` — Business logic
- `app/core/` — config, security, logging
- `app/db/database.py` — Engine, session, `Base`
- `frontend/src/pages/` — Route components
- `frontend/src/components/` — Reusable UI
- `frontend/src/context/AuthContext.tsx` — Auth state (JWT in localStorage)
- `frontend/src/api/client.ts` — Axios with Bearer interceptor

## Key Patterns
- **RBAC:** `UserRole` enum (PARENT, STUDENT, TEACHER, ADMIN). Backend: `require_role()`. Frontend: `ProtectedRoute` + `allowedRoles`.
- **Auth:** Register/Login → JWT in localStorage → Axios interceptor
- **DB tables** created at startup via `create_all()` (no Alembic). New columns need `ALTER TABLE` migrations in `main.py`.
- **API prefix:** `/api`. Frontend base URL: `VITE_API_URL` (default `http://localhost:8000`)

## Config
Backend: `.env` (`DATABASE_URL`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `OPENAI_API_KEY`, `SENDGRID_API_KEY`)
Frontend: `frontend/.env.production` (`VITE_API_URL`)

## Rules for Claude
1. **No unrequested features.** Only implement exactly what is asked. Do not add "wow factor" extras, bonus UI, or speculative enhancements.
2. **Run lint + tests before every commit.** Run `npm run build` and `npm run lint` (frontend) and `pytest` (backend) before committing. If tests or lint fail, fix them before pushing.
3. **Update test mocks when changing hooks/APIs.** When modifying a shared hook (e.g., `useConfirm`, `useAIUsage`), find and update ALL test files that mock it.
4. **One concern per PR.** Each PR should address a single issue. Do not bundle unrelated changes.
5. **Minimal changes only.** Fix the specific issue without refactoring surrounding code, adding comments, or "improving" things that weren't asked about.
6. **Parallel sessions: use an integration branch.** When multiple Claude sessions run in parallel, each should push to its own feature branch. All feature branches must be merged into a shared integration branch (e.g., `integrate/batch-name`) where conflicts are resolved. Only then merge the integration branch to master as a single PR. Never push multiple independent branches directly to master in parallel.
