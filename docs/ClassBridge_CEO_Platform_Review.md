# ClassBridge — CEO Platform Review (EXPANSION Mode)

**Date:** 2026-03-22
**Reviewer:** Claude Opus 4.6 (1M context) — Mega Plan Review Skill
**Branch:** master
**Mode:** SCOPE EXPANSION — Pure 10x Vision
**Project:** ClassBridge (EMAI) — AI-powered education platform

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Audit](#2-system-audit)
3. [Step 0: Scope Challenge & Mode Selection](#3-step-0-scope-challenge--mode-selection)
4. [Section 1: Architecture Review](#4-section-1-architecture-review)
5. [Section 2: Error & Rescue Map](#5-section-2-error--rescue-map)
6. [Section 3: Security & Threat Model](#6-section-3-security--threat-model)
7. [Section 4: Data Flow & Interaction Edge Cases](#7-section-4-data-flow--interaction-edge-cases)
8. [Section 5: Code Quality Review](#8-section-5-code-quality-review)
9. [Section 6: Test Review](#9-section-6-test-review)
10. [Section 7: Performance Review](#10-section-7-performance-review)
11. [Section 8: Observability & Debuggability](#11-section-8-observability--debuggability)
12. [Section 9: Deployment & Rollout](#12-section-9-deployment--rollout)
13. [Section 10: Long-Term Trajectory](#13-section-10-long-term-trajectory)
14. [Required Outputs](#14-required-outputs)
15. [Completion Summary](#15-completion-summary)

---

## 1. Executive Summary

ClassBridge is a substantial Phase 1 education platform — soft-launched March 6, 2026 at classbridge.ca with an April 14, 2026 full launch planned. The platform serves parents, students, teachers, and administrators with Google Classroom integration, AI-powered study tools (streaming generation), gamification (XP/streaks/badges), messaging, a RAG-powered chatbot, and a waitlist/survey system.

**This review was conducted in SCOPE EXPANSION mode** — focused on identifying the architectural moves that transform ClassBridge from a feature-rich MVP into a category-defining "Learning Operating System."

### Key Findings

| Area | Score | Critical Items |
|------|-------|---------------|
| Architecture | C- (current), B+ target | No event bus, no domain boundaries, business logic in routes |
| Error Handling | 4 CRITICAL GAPS | Content safety fail-open, wallet non-atomic, silent email failures, Google credential refresh silently ignored |
| Security | 7/10 | Prompt injection partial, rate limiting ineffective on Cloud Run, content moderation gaps |
| Testing | Good baseline, gaps | 195 backend + 258 frontend tests, but zero E2E, SQLite-only |
| Performance | 2 critical N+1s | Student search O(N) on total students, data export N+1 |
| Observability | Minimal | Text logs only, no metrics, no tracing, no alerting |
| Deployment | Functional but risky | No staging, no canary, no migration rollback |

### Key Decisions Made

| # | Decision | Choice |
|---|----------|--------|
| 1 | Review mode | SCOPE EXPANSION (Pure 10x vision) |
| 2 | Event bus timing | Start now — foundation for Sept bundle |
| 3 | Content safety | Fail-closed with bypass flag |
| 4 | Prompt injection defense | Full input scanning on all AI inputs |
| 5 | Empty content handling | Block + explain when < 50 chars extracted |
| 6 | E2E test introduction | Incremental with each batch |
| 7 | Stash cleanup | Audit and clean now |

---

## 2. System Audit

### Current System State

- **Backend:** 53 API route files, 47 models, 50+ services
- **Frontend:** 100+ pages across 4 role dashboards (Parent, Student, Teacher, Admin)
- **Tech Stack:** FastAPI + React 19 + TypeScript + Vite + TanStack Query
- **Database:** SQLite (dev), PostgreSQL (prod)
- **AI:** Anthropic Claude (streaming study guides, content safety) + OpenAI GPT-4o-mini (quizzes, flashcards, chatbot)
- **Deploy:** GCP Cloud Run, auto-deploys on merge to master

### What's In Flight

- **49 git stashes** — significant accumulated WIP across many feature branches, some over a year old
- **Recent commits** (last 2 weeks): streaming study guide generation, bug report enhancements, race condition fixes — mostly stabilization work
- **Untracked files:** 5 docs in `docs/` (Email Setup Guide, Mentor Priority Plan, Phase2 Analysis, Project Plan)

### Known Pain Points

- Architecture rated **C-** for DDD maturity (per technical.md) — business logic still lives in route handlers
- Tests run on **SQLite only** — PostgreSQL divergences have caused production bugs
- **No TODOS.md** existed (created as part of this review)
- **49 stashes** represent abandoned or forgotten work context

### Phase 2 Roadmap Status

- **Phase 2A "The Hook"** (March 15): Daily Briefing + Help My Kid — IMPLEMENTED
- **Phase 2B "The Dashboard"** (March 22 = review date): Persona-based layouts — IMPLEMENTED
- **Phase 2C/D/E** (March 29 – April 14): Loop, Retention, Polish — in progress
- **September 2026 Retention Bundle**: 7 batches planned (April–July), XP system, badges, assessment countdown, multilingual, Pomodoro, report cards
- **Phase 3/4/5**: Course planning, tutor marketplace, AI email agent — future

### Taste Calibration

**Style References (Well-Designed — Emulate These):**

| File | Why It's Good |
|------|--------------|
| `app/services/xp_service.py` (665 LOC) | A+ exemplar. Fail-safe architecture (never raises), excellent logging at every decision point, anti-gaming checks, clean constant definitions. Template for all future services. |
| `app/api/deps.py` (104 LOC) | A. Token blacklist cache with TTL + LRU prune. `require_role()` factory pattern. Security-first. Lean. |
| `frontend/src/hooks/useStudyGuideStream.ts` (740 LOC) | A. SSE streaming with buffered flushing, abort controller cleanup, mounted-state tracking. Production-grade async React. |
| `frontend/src/api/client.ts` | A. Exponential backoff, queue-based token refresh, deploy readiness gates. Enterprise-grade infrastructure. |

**Anti-Patterns (Avoid Repeating):**

| File | What's Wrong |
|------|-------------|
| `main.py` (~150 lines of migrations) | Raw ALTER TABLE SQL in startup. Exception swallowing (`pass`). No rollback on partial failure. |
| `app/api/routes/study.py` | 45+ imports. Business logic in route handler. Untestable. |
| `frontend/src/pages/ParentDashboard.tsx` (893 LOC) | 15+ useState hooks, localStorage scattered, modal ref hell. God component. |
| `frontend/src/pages/StudentDashboard.tsx` (925 LOC) | Same problems. Duplicates utilities from ParentDashboard. |

---

## 3. Step 0: Scope Challenge & Mode Selection

### Premise Challenge

1. **Is this the right problem to solve?** ClassBridge has shipped an impressive amount of features for a soft launch. The question isn't "is the product right?" — the problem space is validated. The real question is: **is the foundation ready to scale from soft launch to a platform school boards adopt?**

2. **Actual user/business outcome?** Critical inflection point — soft-launched 16 days ago, April 14 launch in 23 days. But the 10x question goes beyond April: can this architecture support a tutor marketplace, Ontario curriculum integration, and multi-school-board deployment?

3. **What if we did nothing?** The feature set is rich. But 49 stashes, SQLite-only tests, C- architecture grade, and no TODOS.md suggests the codebase is accumulating velocity debt. The risk isn't "missing features" — it's "shipping features on a foundation that cracks under real usage."

### Dream State Mapping

```
CURRENT STATE                    THIS REVIEW                    12-MONTH IDEAL
+---------------------+         +-----------------+           +----------------------+
| Feature-rich MVP     |         | Identify gaps    |           | Scalable multi-tenant |
| Soft-launched        |  --->   | between current  |   --->    | SaaS with school      |
| 4-role dashboards    |         | state and        |           | board partnerships,   |
| AI tools working     |         | production       |           | tutor marketplace,    |
| C- architecture      |         | readiness        |           | Ontario curriculum    |
| SQLite-only tests    |         |                  |           | integration, mobile   |
| 49 stashed WIPs      |         |                  |           | app in stores         |
+---------------------+         +-----------------+           +----------------------+
```

### 10x Check

The 10x version transforms ClassBridge from a *tool parents use* into a **learning operating system** that families and schools can't live without:

- **Real-time learning graph**: Every interaction feeds a per-student knowledge graph. Parents see not just "what happened" but "what my child knows and doesn't know" as a living map.
- **Predictive interventions**: Use the learning graph + assessment dates to predict grade outcomes and trigger interventions *before* a test, not after.
- **Teacher-as-first-class-citizen**: Teachers upload curriculum -> ClassBridge generates differentiated materials per student based on their knowledge graph -> parents see what's coming and prep their kids.
- **School board dashboard**: Admin role evolves into board-level analytics — aggregate learning trends, identify struggling cohorts, compliance reporting.

### Platonic Ideal

> "I open ClassBridge and it already knows what my kid should be working on today. It shows me a 30-second summary of yesterday's progress, flags that a math test is in 3 days and my kid hasn't reviewed Chapter 7, and gives me a single button: 'Help them prepare.' I tap it, and 2 minutes later my kid has a personalized study guide, practice quiz, and flashcard set for exactly the topics they're weak on."

### Delight Opportunities

1. **"Study streak shared with parent"** — Streak milestone triggers parent notification with celebration. Emotional connection, zero AI cost.
2. **"Quiz of the Day"** — Auto-generated 5-question daily quiz from recent materials. Gamified with XP. Daily habit loop.
3. **"Teacher gratitude"** — One-tap "thank you" from parent to teacher. Gratitude counter on teacher dashboard. No competitor has this.
4. **"Smart study time suggestions"** — Analyze session timestamps to suggest optimal study windows. Pure data analysis.
5. **"Weekly family report card email"** — Beautiful HTML email with streak flame, XP, quizzes, study time. Parents forward to grandparents. Viral growth mechanic.

---

## 4. Section 1: Architecture Review

### Current Architecture

```
                         +-------------------------------------+
                         |            main.py                   |
                         |  (startup, migrations, scheduler,    |
                         |   40+ route imports, readiness gate) |
                         +----------------+--------------------+
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
     +--------v--------+      +----------v----------+      +--------v--------+
     |  app/api/routes/ |      |   app/services/     |      |   app/models/   |
     |  (53 route files)|----->|  (50+ services)     |----->|  (47 models)    |
     |  ! Business      |      |  ! Some coupled to  |      |  OK Clean       |
     |  logic in routes |      |  routes/models      |      |  OK Multi-role  |
     +-----------------+      +---------------------+      +-----------------+
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
     +--------v--------+      +----------v----------+      +--------v--------+
     |   External APIs  |      |    Database          |      |   GCS Storage   |
     |  OpenAI/Anthropic|      |  SQLite(dev)/PG(prod)|      |  classbridge    |
     |  SendGrid, Gmail |      |  ! No repository    |      |  -files         |
     |  Google Classroom|      |  layer               |      |                 |
     +-----------------+      +---------------------+      +-----------------+
```

### 10x Target Architecture: Learning Operating System

```
  +------------------------------------------------------------------+
  |                     API GATEWAY / BFF                              |
  |  (FastAPI - thin routing, auth, rate limiting, request shaping)    |
  +-----------+----------------+--------------+-----------------------+
              |                |              |
  +-----------v------+ +------v-------+ +---v----------------------+
  | EDUCATION DOMAIN | | STUDY DOMAIN | | KNOWLEDGE GRAPH DOMAIN   |
  |                  | |              | |                          |
  | - Courses        | | - Materials  | | - Per-student graph      |
  | - Assignments    | | - Guides     | | - Topic mastery          |
  | - Enrollments    | | - Quizzes    | | - Knowledge gaps         |
  | - Grades         | | - Flashcards | | - Predictive scores      |
  | - Calendar       | | - Sessions   | | - Curriculum mapping     |
  +-------+----------+ +------+-------+ +-------+------------------+
          | events             | events          | events
  +-------v--------------------v-----------------v------------------+
  |                    EVENT BUS                                     |
  |  (Domain events - async, persistent, replayable)                 |
  |  StudentStudied, QuizCompleted, MaterialUploaded,                |
  |  GradeReceived, StreakBroken, AssessmentDetected                 |
  +-------+--------------------+------------------+-----------------+
          |                    |                   |
  +-------v------+ +----------v-------+ +---------v--------------+
  | GAMIFICATION | | INTELLIGENCE     | | COMMUNICATION          |
  | DOMAIN       | | DOMAIN           | | DOMAIN                 |
  |              | |                  | |                        |
  | - XP/Streaks | | - AI Generation  | | - Messages             |
  | - Badges     | | - Predictions    | | - Notifications        |
  | - Levels     | | - Interventions  | | - Digests              |
  | - Leaderboard| | - Recommendations| | - Teacher Comms        |
  +--------------+ | - Content Safety | | - Parent Briefings     |
                   +------------------+ +------------------------+
                              |
                   +----------v----------+
                   | INTEGRATION DOMAIN  |
                   |                     |
                   | - Google Classroom   |
                   | - Ontario Curriculum |
                   | - LMS Plugins       |
                   | - Tutor Marketplace  |
                   +---------------------+
```

### Key Architectural Moves

**Move 1: Event Bus (the spine)** — Every user action becomes a domain event. Currently `xp_service.award_xp()` is called directly from 6 endpoints. In the 10x version, those endpoints emit events and gamification, knowledge graph, notifications, and analytics all subscribe independently. This is the single most important architectural change.

**Move 2: Knowledge Graph Domain (the brain)** — Doesn't exist yet. Every `MaterialUploaded` feeds topics into the graph. Every `QuizCompleted` updates mastery scores. Every `GradeReceived` calibrates predictions. Becomes the source of truth for "what does this student know?"

**Move 3: Intelligence Domain (the nervous system)** — AI evolves from a utility to a decision-maker: "This student should study Chapter 7 because their mastery is 40% and the test is in 3 days."

**Move 4: Plugin Architecture for Integrations** — Google Classroom is hard-wired. Adding TeachAssist or Brightspace should be a new plugin, not a codebase change.

### Coupling: Before vs After

```
BEFORE (current):                    AFTER (10x):
+---------+                          +---------+
| study.py|-->  xp_service           | study.py|--> emit(MaterialGenerated)
|         |-->  notification_service  |         |
|         |-->  ai_service            +---------+
|         |-->  streak_service              |
|         |-->  storage_service        +----v------+
+---------+                            | EVENT BUS |
     |                                 +----+------+
5 direct dependencies                      |
                                 +---------+---------+
                                 |         |         |
                            xp_service  notif   knowledge
                                                  graph
                                 0 direct dependencies from study.py
```

### Scaling Characteristics

| At 10x load (500 users) | At 100x load (5,000 users) |
|--------------------------|---------------------------|
| AI API costs (~$500/mo) | AI costs unsustainable (~$5,000/mo) without BYOK or caching |
| SQLite dev/PG prod divergence causes bugs | Need read replicas or connection pooling upgrade |
| In-memory rate limiting resets on deploy | Need Redis-backed rate limiting |
| Single Cloud Run instance bottleneck | Need horizontal scaling + WebSocket infrastructure |

### Single Points of Failure

1. **OpenAI API** — all study generation, quizzes, flashcards, content safety. No fallback provider.
2. **main.py migrations** — if startup migration fails, app starts with broken schema. No rollback.
3. **SendGrid** — all email. No fallback.
4. **GCS** — all file storage. If GCS is down, no uploads, no file serving.

---

## 5. Section 2: Error & Rescue Map

### Error & Rescue Registry

| METHOD/CODEPATH | EXCEPTION CLASS | RESCUED? | USER SEES | CRITICAL? |
|-----------------|----------------|----------|-----------|-----------|
| ai_service: check_content_safe | anthropic.*Error | YES (fail-open) | NOTHING (silent pass) | **CRITICAL** |
| ai_service: non-stream generate | anthropic.*Error | NO RETRY | 500 error | HIGH |
| ai_service: stream generate | anthropic.*Error | YES (retry 2x) | SSE error event | OK |
| email: batch send | Exception per-email | YES (skip) | Silent skip | **CRITICAL** |
| email: inspiration footer | Exception | YES (swallow) | Missing footer | MEDIUM |
| google: credential refresh | RefreshError | pass (bare) | Silent stale | **CRITICAL** |
| gmail: parse_message | KeyError/TypeError | NO | Entire fetch 500 | HIGH |
| gcs: upload/download | GoogleCloudError | NO | 500 error | HIGH |
| wallet: debit_wallet | DB flush error | NO | Partial debit | **CRITICAL** |
| notification: DB add | DB error | NO | 500 (even if primary succeeded) | MEDIUM |
| file: empty extraction | N/A | PARTIAL | Empty study guide | HIGH |
| scheduler: job duplicate | N/A | NO | Duplicate email | MEDIUM |

### 4 CRITICAL GAPS

1. **Content safety fail-open** (`ai_service.py` lines 86-88) — If Anthropic API is down, unsafe content passes through to a K-12 platform with no disclosure. **Decision: Fix to fail-closed with bypass flag.**

2. **Email delivery not tracked** (`email_service.py` lines 67-68, 94-95) — Batch emails silently skip failed recipients. Parent never knows they missed a notification.

3. **Google credential refresh silently ignored** (`google_classroom.py` lines 143-147, 159-163) — Bare `pass` on refresh failure. No logging. Downstream calls fail mysteriously.

4. **Wallet debit non-atomic** (`wallet_service.py` lines 84-91) — DB flush failure after in-memory debit = inconsistent state. User may be double-charged on retry.

### Streaming vs Non-Streaming Inconsistency

| Feature | Streaming | Non-Streaming |
|---------|-----------|---------------|
| Retry on transient error | YES (2x with backoff) | NO |
| Graceful error to user | YES (SSE error event) | NO (500 error) |
| User experience on failure | "Service temporarily unavailable" | Blank error page |

**Recommendation:** Unify all AI generators to use retry logic.

---

## 6. Section 3: Security & Threat Model

### Overall Security Posture: 7/10

### Threat Assessment Summary

| # | Threat | Likelihood | Impact | Mitigated? | Risk |
|---|--------|-----------|--------|------------|------|
| 1 | LLM Prompt Injection | High | High | Partial | **HIGH** |
| 2 | Rate Limiting (Cloud Run) | High | Medium | No | **HIGH** |
| 3 | Content Safety Gaps (K-12) | Medium | High | Partial | **HIGH** |
| 4 | Token Blacklist Persistence | Medium | High | Partial | **MEDIUM** |
| 5 | Study Guide IDOR | Medium | High | Partial | **MEDIUM** |
| 6 | Rate Limiting (Auth/AI) | Medium | High | Partial | **MEDIUM** |
| 7 | File Upload Security | Low | High | Partial | **MEDIUM** |
| 8 | Task Assignment IDOR | Low | High | Yes | LOW |
| 9 | Message Access IDOR | Low | High | Yes | LOW |
| 10 | Notes Access IDOR | Low | Medium | Yes | LOW |
| 11 | Grades IDOR | Medium | High | Yes | LOW |
| 12 | SQL Injection | Low | High | Yes | LOW |
| 13 | Admin Access Control | Low | Critical | Yes | LOW |
| 14 | Password Strength | Low | High | Yes | LOW |
| 15 | Email Validation | Low | Medium | Yes | LOW |
| 16 | User Data Exposure | Low | Medium | Partial | LOW |

### HIGH Risk Findings

**1. LLM Prompt Injection** — `check_content_safe()` only covers `focus_prompt`. `custom_prompt` and `assignment_description` (teacher-uploaded content) bypass safety entirely. A malicious PDF could jailbreak the AI.

**Decision: Full input scanning on all text inputs that reach the AI.**

**2. Rate Limiting on Cloud Run** — `slowapi` uses in-memory storage (`memory://`). Resets on every cold start. Doesn't share state across instances. Attacker can distribute requests.

**3. Content Safety Gaps** — Teacher uploads, student notes, and messages have NO content moderation. On a K-12 platform serving minors.

### What's Well-Secured

- IDOR protections: Tasks, messages, notes, grades properly scoped with whitelist patterns
- Admin endpoints: `require_role(ADMIN)` on all admin routes
- SQL injection: `escape_like()` + SQLAlchemy parameterization throughout
- Password policy: 8-char min with uppercase/lowercase/digit/special
- Auth flow: JWT with blacklist, refresh tokens
- CI security scanning: Bandit (SAST), GitLeaks (secrets), pip-audit + npm audit

### 10x Security Target

For school board adoption, security needs to be demonstrably excellent:

| Current (7/10) | 10x Target (9.5/10) |
|-----------------|---------------------|
| RBAC + IDOR guards | All current controls |
| JWT + blacklist | + Redis-backed rate limiting |
| In-memory rate limiting | + Content moderation on ALL user-generated content |
| Partial prompt guard | + Prompt injection defense on ALL AI inputs |
| No content scanning | + SOC2 Type II certification |
| No compliance cert | + Annual penetration test |
| No pen test | + FERPA compliance documentation |
| | + Immutable audit trail |

---

## 7. Section 4: Data Flow & Interaction Edge Cases

### Core Data Flow: Upload -> AI Generation -> Student Consumption

```
+---------+     +--------------+     +--------------+     +----------+     +----------+
|  UPLOAD  |---->|  VALIDATION  |---->|  EXTRACTION  |---->| AI GEN   |---->| DISPLAY  |
| (file)   |     | (type/size)  |     | (OCR/parse)  |     | (guide/  |     | (student |
|          |     |              |     |              |     |  quiz)   |     |  sees)   |
+----+-----+     +------+-------+     +------+-------+     +----+-----+     +----+-----+
     |                  |                    |                   |                |
     v                  v                    v                   v                v
[nil file?]       [too large?]         [empty text?]       [API down?]     [stale cache?]
[0 bytes?]        [wrong type?]        [corrupt PDF?]      [timeout?]      [partial render?]
[wrong ext?]      [spoofed magic?]     [no OCR engine?]    [unsafe?]       [encoding issue?]
[10+ files?]      [name collision?]    [image-only PDF?]   [malformed?]    [missing images?]
```

### Shadow Path Analysis

| Node | Shadow Path | Handled? | Gap? |
|------|------------|----------|------|
| UPLOAD: nil file | No file attached | YES | OK |
| UPLOAD: 0 bytes | Empty file | PARTIAL | UX gap — unclear error |
| UPLOAD: 10+ files | Exceeds cap | YES | OK |
| VALIDATION: too large | >20MB | YES | OK |
| VALIDATION: spoofed magic | .pdf but .exe content | YES | OK |
| EXTRACTION: empty text | Image-only PDF, no OCR | PARTIAL | **GAP — study guide from nothing** |
| EXTRACTION: corrupt PDF | Malformed structure | PARTIAL | **GAP — may return ""** |
| AI GEN: API down | Anthropic unreachable | PARTIAL | **Inconsistent (stream vs non-stream)** |
| AI GEN: timeout | >60s response | YES (stream) / NO (non-stream) | **Inconsistent** |
| AI GEN: unsafe content | Safety flags input | YES (after fix) | OK |
| AI GEN: malformed JSON | Invalid quiz/flashcard | PARTIAL | **GAP — no schema validation** |
| DISPLAY: missing images | IMG markers but no GCS file | YES | OK — fallback section |
| DISPLAY: encoding | Non-UTF8 characters | PARTIAL | **GAP in file extraction** |

**Decision: Block + explain when extracted text < 50 chars.**

### Interaction Edge Cases

| Interaction | Edge Case | Handled? |
|------------|-----------|----------|
| File upload: double-click | YES — useRef guard + 60s dedup |
| File upload: navigate away mid-upload | PARTIAL — no resume |
| Study guide stream: user navigates away | YES — abort controller |
| Quiz submission: double-click | UNCLEAR — needs verification |
| Dashboard: zero courses/children | YES — EmptyState CTAs |
| Dashboard: 50+ courses | PARTIAL — no virtual scrolling |
| Scheduled jobs: run twice (Cloud Run) | **NO — no dedup** |
| Wallet: double-debit race | **NO — no idempotency key** |
| XP: rapid-fire gaming | YES — anti-gaming cooldowns |

---

## 8. Section 5: Code Quality Review

### DRY Violations

| Violation | Where | Impact |
|-----------|-------|--------|
| `formatRelativeDate()` | ParentDashboard.tsx + StudentDashboard.tsx | Identical function duplicated |
| Urgency tier calculation | ParentDashboard.tsx + StudentDashboard.tsx | Same grouping logic duplicated |
| Email template loading | auth.py lines 50, 71 | Should be in EmailService |
| Email lowercase normalization | auth.py lines 128, 148 | Normalize once at entry |
| Local type redefinitions | Dashboard components redefine Course, Assignment | Should import from api types |
| Error message extraction | `(err as {...})?.response?.data?.detail` | Scattered across 10+ components |
| localStorage try/catch | Every dashboard component | No `useLocalStorage` hook |

### Cyclomatic Complexity Flags

| Method/Component | Branches | Issue |
|-----------------|----------|-------|
| ParentDashboard.tsx render | 20+ conditionals | God component |
| StudentDashboard.tsx render | 15+ conditionals | God component |
| auth.py register() | 10+ branches | Extract to AuthService |
| study.py generate endpoints | 8+ per endpoint | Extract to StudyService |
| main.py startup migrations | 30+ if-checks | Extract to MigrationRunner |

### Under-Engineering Concerns

| Area | Issue |
|------|-------|
| No repository layer | Services query DB directly; knowledge graph will duplicate queries |
| No error taxonomy | Bare `Exception` catches or no catches at all |
| No circuit breaker | Every request tries failed external APIs |
| No idempotency | Wallet debits, quiz saves lack idempotency keys |
| No request correlation | No trace ID flows through the system |

---

## 9. Section 6: Test Review

### Test Inventory

```
Backend:   195 tests across 64 test files (~21,900 lines of test code)
Frontend:  258 tests (vitest) across 18 test files
E2E:       0 tests
Load:      0 tests
```

### Test Coverage Map

| Area | Unit | Integration | E2E | Gap? |
|------|------|------------|-----|------|
| Auth (register/login/refresh) | YES | YES | NO | E2E gap |
| Study guide generation | YES | YES (streaming) | NO | E2E gap |
| XP/Streak/Badge system | YES (40+) | YES | NO | OK |
| File upload + extraction | PARTIAL | YES | NO | Missing corrupt file tests |
| Wallet credit/debit | YES | YES | NO | **Missing race condition tests** |
| Google Classroom sync | YES | YES | NO | **Missing OAuth refresh test** |
| Email delivery | PARTIAL | YES | NO | **Missing batch failure test** |
| Chatbot (RAG) | YES | YES | NO | OK |
| Scheduled jobs | PARTIAL | PARTIAL | NO | **Missing job duplicate tests** |
| Frontend components | YES (258) | NO | NO | **No Playwright/Cypress** |

### Tests That Would Make You Ship at 2 AM on a Friday

1. "Upload a corrupt PDF -> verify user gets clear error, not a blank study guide" — **doesn't exist**
2. "Two concurrent wallet debits -> verify only one succeeds" — **doesn't exist**
3. "Anthropic API returns 500 -> verify non-streaming generation retries" — **doesn't exist** (streaming has it)
4. "Google OAuth token expires mid-sync -> verify re-auth prompt" — **doesn't exist**
5. "Scheduled digest job runs twice -> verify no duplicate emails" — **doesn't exist**

### Test Pyramid Assessment

```
Current:                    Ideal 10x:
     /\                         /\
    /  \  E2E: 0               /  \  E2E: 20+ (Playwright)
   /    \                     /    \
  /------\  Integration:     /------\  Integration: 300+
 / 195    \  195 backend    / 200+   \  (backend + frontend)
/----------\               /----------\
/ 258 vitest\  Unit: 258  / 500+       \  Unit: 500+
/            \  frontend  /              \  (frontend + backend)
```

**Decision: Introduce E2E tests incrementally with each batch of the September retention bundle.**

---

## 10. Section 7: Performance Review

### Slowest Endpoints (P99 Latency)

| Endpoint | P99 | Bottleneck | Severity |
|----------|-----|-----------|----------|
| `GET /courses/students/search` | **10-18s** | Full table scan + N+1 | **CRITICAL** |
| `POST /study/generate` | 18-25s | AI generation (expected) | MEDIUM |
| `POST /users/me/export` | 1.5-3s | N+1 on assignments | HIGH |
| `GET /courses/teachers/search` | 1-3s | Lazy loading .user | MEDIUM |

### N+1 Query Patterns Found

1. **`/courses/students/search`** (courses.py lines 165-181) — Loads ALL students with `db.query(Student).all()`, then 1 User query per student. 1000 students = 1001 queries = 15+ seconds.

2. **`/courses/teachers/search`** (courses.py lines 130-151) — Loads teachers without eager loading `.user` relationship.

3. **Data export `_collect_assignments()`** (data_export_service.py lines 263-282) — Queries Assignment table per StudentAssignment record. 50 assignments = 51 queries.

4. **Data export `_collect_children_data()`** (data_export_service.py lines 84-100) — Queries Student + User per child.

### Missing Database Indexes

| Model | Column | Used In |
|-------|--------|---------|
| Student | `user_id` | Every parent view, dashboard, export |
| CourseContent | `created_by_user_id` | Content creator filtering |
| StudyGuide | `guide_type` | Filtering guides vs quizzes vs flashcards |

### Memory Analysis

| Service | Memory Usage | Risk |
|---------|-------------|------|
| Help Embedding Service | ~1.07 MB (130 chunks, 1536-dim vectors) | LOW |
| Intent Embedding Service | ~0.28 MB (48 anchors) | LOW (but no caching — recomputes on restart) |

### Connection Pool

| Setting | Value | Risk |
|---------|-------|------|
| pool_size | 10 | OK for <50 concurrent |
| max_overflow | 20 | Total capacity: 30 |
| pool_recycle | 1800s | OK |
| pool_pre_ping | True | Prevents stale connections |
| **At 500 users** | **~50 concurrent requests** | **Pool exhaustion risk** |

---

## 11. Section 8: Observability & Debuggability

### Current State

| Aspect | Status |
|--------|--------|
| Logging | Good baseline — rotating files, request middleware |
| Structured logging | **NO** — text-based, can't query in GCP Cloud Logging |
| Metrics | **NO** — no Prometheus, StatsD, or CloudMonitoring |
| Tracing | **NO** — no trace IDs, no request correlation |
| Alerting | **NO** — no Sentry, PagerDuty, or alert rules |
| Dashboards | **NO** — no Grafana, no Cloud Monitoring |
| Health check | YES — `/health` returns version + environment |
| Frontend errors | Partial — `POST /api/errors/log` |

### 10x Target: The Observatory Dashboard

```
+--------------------------------------------------------------------+
|  CLASSBRIDGE OBSERVATORY                    Last 24h    Live        |
+------------------+------------------+------------------------------+
| HEALTH           | USERS            | AI ENGINE                    |
| * API: 99.8%     | DAU: 47          | Generations: 312             |
| * GCS: 100%      | Sessions: 23     | Cost today: $4.21            |
| * AI: 98.2%      | Active now: 8    | Avg latency: 12.3s           |
| * Email: 100%    | New signups: 3   | Safety blocks: 2             |
|                  |                  | Stream errors: 4 (1.3%)      |
+------------------+------------------+------------------------------+
| JOBS             | ENGAGEMENT       | ERRORS (last hour)           |
| OK Digest: Sun 7p| Study guides: 89 | 500 errors: 3                |
| OK Streak: 2am   | Quizzes: 45      | AI timeouts: 7               |
| OK Reminder: 6am | Uploads: 23      | Email failures: 0            |
| Next: Streak     | Avg XP/student:  | GCS errors: 0                |
|   in 14h         |   150            | Rate limits hit: 12          |
|                  | Streaks active:31|                              |
+------------------+------------------+------------------------------+
```

---

## 12. Section 9: Deployment & Rollout

### Current Pipeline

```
Developer -> git push -> GitHub Actions CI
                              |
                    +---------v----------+
                    | CI Pipeline         |
                    | 1. pip install      |
                    | 2. pytest -n auto   |
                    | 3. Bandit (SAST)    |
                    | 4. GitLeaks         |
                    | 5. npm install      |
                    | 6. npm run build    |
                    | 7. npm run lint     |
                    | 8. pip-audit        |
                    | 9. npm audit        |
                    +---------+----------+
                              | (master only)
                    +---------v----------+
                    | Docker Build        |
                    | Multi-stage:        |
                    | Node 20 -> Python 3.13|
                    +---------+----------+
                              |
                    +---------v----------+
                    | GCP Cloud Run       |
                    | 1-3 instances       |
                    | 512Mi / 1 CPU       |
                    | Startup probe       |
                    | Advisory lock on    |
                    |  migrations         |
                    +--------------------+
```

### Assessment

| Aspect | Status | Detail |
|--------|--------|--------|
| Migration safety | RISKY | Raw ALTER TABLE in startup. No rollback. |
| Feature flags | MINIMAL | Only WAITLIST_ENABLED, GOOGLE_CLASSROOM_ENABLED |
| Rollback plan | MANUAL | Git revert + redeploy (~5 min) |
| Zero-downtime | YES | Cloud Run rolling update + readiness gate |
| Canary deploy | NO | All-or-nothing |
| Staging environment | NO | Deploys directly to production |
| Post-deploy verification | MANUAL | Health check only |

### 10x Target

```
CURRENT:                                 10x TARGET:
+----------------------+                 +----------------------------+
| Push to master ->     |                 | Push to main ->             |
| CI -> Docker -> Deploy|                 | CI -> Docker -> Staging      |
| (all-or-nothing)     |    --->         | -> Smoke tests -> Canary     |
| No staging           |                 | -> 10% traffic -> Monitor    |
| No canary            |                 | -> 50% -> 100%              |
| No smoke tests       |                 | Auto-rollback on error       |
| No rollback infra    |                 | spike > 2x baseline          |
+----------------------+                 +----------------------------+
```

---

## 13. Section 10: Long-Term Trajectory

### Technical Debt Inventory

| Debt Type | Items | Impact |
|-----------|-------|--------|
| Code debt | God components (893/925 LOC), 45-import routes, duplicate utils | Slows feature velocity |
| Architecture debt | No event bus, no repository layer, logic in routes | Every new feature increases coupling |
| Operational debt | No structured logging, no metrics, no alerting | Can't debug production efficiently |
| Testing debt | Zero E2E, SQLite-only tests, no load tests | PG divergences cause prod bugs |
| Documentation debt | No TODOS.md (now created), no ADRs | Knowledge concentrated in one person |
| Hygiene debt | 49 git stashes, untracked docs | Cognitive overhead |

### Path Dependency

Two specific concerns:

1. **main.py migrations are irreversible.** Every ALTER TABLE is a one-way door. Adding the knowledge graph (20+ new tables) would make main.py unmaintainable without a migration framework.

2. **Direct service coupling prevents plugin architecture.** Adding new LMS integrations means wiring directly into the same routes Google Classroom touches.

### Reversibility Rating: 3/5

- Easy to reverse: Feature flag changes, UI tweaks, new API endpoints
- Hard to reverse: Schema changes, GCS storage layout, OAuth scope additions
- Impossible to reverse: Sent emails, published study guides, deleted user data

### Phase Trajectory

```
Phase 2 (Sept 2026)          Phase 3 (2027)              Phase 4 (2027-28)
+------------------+         +------------------+         +------------------+
| Retention Bundle  |         | Course Planning   |         | Tutor Marketplace|
| - XP/Streaks     |   -->   | - Ontario Curr.   |   -->   | - Tutor profiles |
| - Badges         |         | - Prereq engine   |         | - Booking system |
| - Multilingual   |         | - Uni pathways    |         | - Payment (Stripe)|
| - Pomodoro       |         | - School board    |         | - Ratings/reviews|
| - Report cards   |         |   integration     |         | - AI matching    |
|                  |         | - Exam prep engine|         |                  |
| ARCH NEEDS:      |         | ARCH NEEDS:       |         | ARCH NEEDS:      |
| - Event bus      |         | - Knowledge graph |         | - Payment domain |
| - Feature flags  |         | - Plugin arch.    |         | - Marketplace    |
| - E2E tests      |         | - Multi-tenant    |         |   domain         |
+------------------+         +------------------+         | - Trust/safety   |
                                                          +------------------+
```

### Flash Tutor — A Step Toward the Learning OS (Deployed April 14, 2026)

The Interactive Learning Engine (CB-ILE-001) represents a significant step toward the "Learning Operating System" vision outlined in this review. Flash Tutor delivers on several 10x aspirations:

- **Knowledge gap detection in action:** SM-2 spaced repetition and adaptive difficulty (easy/medium/challenging) track what each student knows and doesn't know — the foundation of the per-student knowledge graph envisioned in Section 3.
- **Predictive interventions:** Knowledge Decay notifications proactively alert parents when a topic needs review, moving from reactive to predictive support.
- **Parent as learning partner:** Parent Teaching Mode and Career Connect transform the parent role from observer to active participant — exactly the "bridge between families and learning" this review called for.
- **AI cost discipline:** Question bank pre-generation with hint caching achieves 50-65% AI cost reduction, directly addressing the OpenAI cost risk identified in this review and proving the platform can scale AI features sustainably.
- **Anti-gaming maturity:** Session limits, rapid completion detection, and tiered XP demonstrate the anti-gaming rigor needed for school board credibility (VASP/DTAP).

Flash Tutor's architecture (7 services, 16 endpoints, 5 DB tables) follows the service-layer patterns recommended in this review rather than the anti-pattern of business logic in routes.

### The 10x Architecture Path

```
TODAY                    SEPT 2026                  2027
+------------+          +----------------+         +------------------+
| Monolithic  |          | Event-driven   |         | Learning OS      |
| CRUD + AI   |   -->    | + Gamification |   -->   | + Knowledge Graph|
| C- arch     |          | + Observability|         | + Plugin Arch    |
|             |          | B+ arch        |         | + Multi-tenant   |
+------------+          +----------------+         | A arch           |
                                                   +------------------+
```

---

## 14. Required Outputs

### NOT in Scope

| Deferred Item | Rationale |
|--------------|-----------|
| Production readiness fixes | User chose "Pure 10x vision" |
| Specific code changes / PRs | Plan review, not implementation |
| Mobile app review (Expo) | Separate repo |
| Phase 2 repo review | Different codebase |
| Cost optimization (AI spend) | Tactical, not architectural |
| UI/UX design review | Covered in existing HCD Assessment |
| Individual feature review | Scope is platform architecture |

### What Already Exists

| Sub-Problem | Existing Code | Reusable? |
|------------|--------------|-----------|
| Event-driven communication | notification_service.py | Pattern reusable |
| Gamification engine | xp_service.py, streak_service.py, badge_service.py | YES — exemplary |
| AI generation pipeline | ai_service.py with retry + streaming | YES — needs unified retry |
| File processing | file_processor.py with magic bytes + OCR | YES — needs empty gate |
| Role-based access | deps.py require_role() | YES — solid |
| Feature flags | WAITLIST_ENABLED, GOOGLE_CLASSROOM_ENABLED | Pattern exists, needs generalization |
| Search infrastructure | Chatbot unified search | YES — extensible |
| Email infrastructure | email_service.py with SendGrid + SMTP fallback | YES — needs tracking |
| Auth infrastructure | JWT + blacklist + refresh + RBAC | YES — solid |
| CI/CD pipeline | GitHub Actions -> Docker -> Cloud Run | YES — needs staging + canary |

### Failure Modes Registry

| CODEPATH | FAILURE MODE | RESCUED? | TEST? | USER SEES? | LOGGED? |
|----------|-------------|----------|-------|------------|---------|
| ai_service: content_safe | API down -> fail-open | Y | N | SILENT | WARNING |
| ai_service: non-stream gen | Transient API error | NO RETRY | Y(stream) | 500 error | ERROR |
| email: batch send | Per-email failure | Y | N | SILENT | WARNING |
| email: inspiration footer | DB error | Y | N | SILENT | NONE |
| google: credential refresh | Token expired | pass | N | SILENT | NONE |
| gmail: parse_message | Malformed response | N | N | 500 error | NONE |
| gcs: upload/download | Network error | N | N | 500 error | NONE |
| wallet: debit | DB flush failure | N | N | Partial debit | ERROR |
| notification: DB add | DB error | N | N | 500 error | NONE |
| file: empty extraction | Image-only PDF | PARTIAL | N | Empty guide | NONE |
| scheduler: job duplicate | Cloud Run runs 2x | N | N | Duplicate email | NONE |
| student search | N+1 on 1000+ students | N/A | N | 15s+ timeout | NONE |

**CRITICAL GAPS (RESCUED=N + TEST=N + USER SEES=Silent):**
1. Content safety fail-open (decided: fix to fail-closed)
2. Email batch silent failures
3. Google credential refresh silent `pass`
4. Wallet non-atomic debit

---

## 15. Completion Summary

```
+====================================================================+
|            MEGA PLAN REVIEW - COMPLETION SUMMARY                    |
+====================================================================+
| Mode selected        | SCOPE EXPANSION (Pure 10x Vision)           |
| System Audit         | 53 routes, 47 models, 50+ services,         |
|                      | 49 stashes, C- architecture grade            |
| Step 0               | EXPANSION + event bus before Sept bundle     |
+--------------------------------------------------------------------+
| Section 1  (Arch)    | 1 issue: no event bus (decided: build)       |
| Section 2  (Errors)  | 12 error paths mapped, 4 CRITICAL GAPS      |
| Section 3  (Security)| 16 threats assessed, 4 High severity         |
| Section 4  (Data/UX) | 14 shadow paths mapped, 5 unhandled          |
| Section 5  (Quality) | 7 DRY violations, 5 complexity flags         |
| Section 6  (Tests)   | Diagram produced, 5 critical test gaps       |
| Section 7  (Perf)    | 4 N+1 patterns, 3 missing indexes            |
| Section 8  (Observ)  | 5 gaps (no metrics/traces/alerts/dash)       |
| Section 9  (Deploy)  | 3 risks (no staging/canary/migrations)       |
| Section 10 (Future)  | Reversibility: 3/5, 6 debt categories        |
+--------------------------------------------------------------------+
| NOT in scope         | written (7 items)                            |
| What already exists  | written (10 reusable subsystems)             |
| Dream state delta    | written (10 remaining items to ideal)        |
| Error/rescue registry| 12 methods, 4 CRITICAL GAPS                 |
| Failure modes        | 12 total, 4 CRITICAL GAPS                   |
| TODOS.md updates     | 8 items proposed, all accepted               |
| Delight opportunities| 5 identified, all accepted                   |
| Diagrams produced    | 7 (arch, event bus, coupling, data flow,     |
|                      |    observatory, deploy, trajectory)           |
| Stale diagrams found | 0 (no existing ASCII diagrams in codebase)   |
| Unresolved decisions | 0                                            |
+====================================================================+
```

### TODOS Created (see TODOS.md)

| ID | Priority | Description | Effort |
|----|----------|-------------|--------|
| TODO-001 | P0 | Content Safety Fail-Closed Gate | S (1 day) |
| TODO-002 | P0 | Fix 4 Critical Silent Failures | M (2 days) |
| TODO-003 | P1 | Lightweight In-Process Event Bus | L (3-5 days) |
| TODO-004 | P1 | Structured JSON Logging + Correlation IDs | M (2 days) |
| TODO-005 | P1 | Fix N+1 Queries + Add Missing Indexes | S (1 day) |
| TODO-006 | P1 | Redis-Backed Rate Limiting | M (1 day + infra) |
| TODO-007 | P2 | Audit and Clean 49 Git Stashes | S (30 min) |
| TODO-008 | P2 | Migration Framework (Alembic) | L (3-5 days) |
| DELIGHT-001 | Vision | Study Streak Shared with Parent | S (30 min) |
| DELIGHT-002 | Vision | Quiz of the Day | M (2 hours) |
| DELIGHT-003 | Vision | Teacher Gratitude | S (1 hour) |
| DELIGHT-004 | Vision | Smart Study Time Suggestions | S (1 hour) |
| DELIGHT-005 | Vision | Weekly Family Report Card Email | M (2 hours) |

---

*Generated by Claude Opus 4.6 (1M context) — Mega Plan Review Skill — 2026-03-22*
