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
