# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Parallel Agent Streams

When launching multiple parallel agent streams for feature development, **always** use `isolation: "worktree"` on every Agent tool call. This gives each stream its own isolated git worktree (a separate working directory cloned from the current branch) so streams never write to the same files simultaneously.

**Critical rules for agent prompts:**
- Each stream agent MUST commit its changes before finishing (use `git add -A && git commit -m "..."` via Bash)
- If Bash is not available, the agent should note all files changed so the merge agent can pick them up from the worktree path
- After all streams complete, launch a dedicated merge agent to: read all worktrees, resolve conflicts in hotspot files (main.py, DashboardLayout.tsx, etc.), write merged files to main working directory, commit, then `git worktree remove --force` each worktree
- Never let streams write directly to `c:/dev/emai/class-bridge-phase-2` (the main working directory) when running in parallel

## Project Overview

EMAI (ClassBridge) is an AI-powered education management platform connecting parents, students, teachers, and admins. It integrates with Google Classroom, provides AI study tools (guides, quizzes, flashcards), parent-teacher messaging, and teacher email/announcement monitoring.

## Tech Stack

- **Backend:** FastAPI (Python 3.13+), SQLAlchemy 2.0, Pydantic 2.x
- **Frontend:** React 19, TypeScript, Vite, React Router 7, TanStack React Query, Axios
- **Database:** SQLite (dev: `emai.db`), PostgreSQL (prod)
- **AI:** OpenAI API (gpt-4o-mini)
- **Auth:** JWT (python-jose), OAuth2 Bearer, bcrypt
- **Google:** Classroom API, Gmail API, OAuth2
- **Email:** SendGrid
- **Scheduling:** APScheduler (assignment reminders, teacher comm sync)
- **Deployment:** Google Cloud Platform (Cloud Run, Cloud SQL)

## Common Commands

### Backend
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pytest
```

### Frontend (from `frontend/`)
```bash
npm install
npm run dev        # Vite dev server on :5173
npm run build      # tsc -b && vite build
npm run lint       # eslint
```

API docs available at `http://localhost:8000/docs` (Swagger) and `/redoc`.

## Architecture

### Backend Structure (`app/`)
- `api/routes/` — FastAPI routers, all mounted under `/api` prefix in `main.py`
- `api/deps.py` — Shared dependencies: `get_db()`, `get_current_user()`, `require_role(*roles)` factory
- `models/` — SQLAlchemy ORM models (User, Student, Teacher, Course, Assignment, StudyGuide, Conversation, Message, Notification, TeacherCommunication, Invite)
- `schemas/` — Pydantic request/response models (`from_attributes = True` for ORM mode)
- `services/` — Business logic (AI generation, Google Classroom sync, email, file processing)
- `jobs/` — APScheduler background jobs (assignment reminders at 8am, teacher comm sync every 15min)
- `core/config.py` — Pydantic BaseSettings loaded from `.env`
- `core/security.py` — JWT creation, password hashing/verification
- `core/logging_config.py` — Structured logging with auto log-level (DEBUG dev, WARNING prod)
- `db/database.py` — SQLAlchemy engine, session factory, `Base` declarative class

### Frontend Structure (`frontend/src/`)
- `pages/` — Route-level page components (Login, Register, Dashboard, StudyGuide, Messages, etc.)
- `components/` — Reusable UI (ProtectedRoute, DashboardLayout, NotificationBell)
- `context/AuthContext.tsx` — Auth state provider (JWT in localStorage, user info)
- `api/client.ts` — Axios instance with Bearer token interceptor and 401 redirect handling

### Key Patterns
- **RBAC:** `UserRole` enum (PARENT, STUDENT, TEACHER, ADMIN). Backend uses `require_role()` dependency. Frontend uses `ProtectedRoute` with `allowedRoles` prop and `Dashboard.tsx` dispatches to role-specific dashboard components.
- **Auth flow:** Register → POST `/api/auth/register` (creates User + role-specific profile). Login → POST `/api/auth/login` → JWT stored in localStorage → Axios interceptor injects Bearer header.
- **Google OAuth:** Frontend redirects to `/api/google/connect` → Google consent → callback at `/api/google/callback` → tokens stored on User record → courses synced to DB.
- **DB tables created at startup** via `Base.metadata.create_all()` in `main.py` (no Alembic migrations in use yet).
- **Many-to-many:** Parent-Student relationship uses `parent_students` join table with `relationship_type`.
- **Invite system:** Unified `Invite` model handles both student and teacher invitations with `invite_type` discriminator and `metadata_json` for context.

### API URL Scheme
All routes prefixed with `/api`. Frontend API base URL defaults to `http://localhost:8000` (configurable via `VITE_API_URL` env var). CORS currently allows all origins.

## Configuration

Backend config via `.env` file (see `.env.example`). Key settings: `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OPENAI_API_KEY`, `SENDGRID_API_KEY`.

Frontend production env: `frontend/.env.production` (set `VITE_API_URL`).

## Current State

Phase 1 (MVP) in progress on `feature/ai-study-tools` branch. See `REQUIREMENTS.md` for full PRD with phased roadmap and GitHub issue tracking. Design diagrams in `design/`. No tests written yet.
