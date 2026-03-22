# ClassBridge — TODOS

Deferred work from the Mega Plan Review (2026-03-22, EXPANSION mode).
Each item was reviewed and explicitly approved for tracking.

---

## P0 — Critical (Before April 14 Launch)

### TODO-001: Content Safety Fail-Closed Gate
**What:** Fix `ai_service.py` `check_content_safe()` to BLOCK generation when Anthropic API is unavailable, instead of silently passing content through. Add `safety_checked` flag to all AI responses. Extend `check_content_safe()` to cover `custom_prompt` and `assignment_description` (currently only checks `focus_prompt`).
**Why:** K-12 platform serving minors. Fail-open on content safety is a foundational trust violation. School boards will ask about this.
**Effort:** S (1 day)
**Files:** `app/services/ai_service.py` (lines 59-88), all study.py generation endpoints
**Depends on:** Nothing
**Issue:** #2213

### TODO-002: Fix 4 Critical Silent Failures
**What:** Four independent fixes:
1. **Wallet debit atomicity** — Wrap `debit_wallet()` in explicit transaction so flush failure rolls back both debit and transaction record (`wallet_service.py` lines 84-91) → **#2214**
2. **Google credential refresh logging** — Replace bare `pass` with `logger.warning()` in `google_classroom.py` lines 143-147, 159-163 → **#2215**
3. **Email batch delivery tracking** — Return `{sent, failed, failed_emails}` from `send_emails_batch()` instead of silent skip (`email_service.py` lines 67-68) → **#2216**
4. **Empty file extraction gate** — Block AI generation when extracted text < 50 chars. Show "We couldn't read this document" error (`file_processor.py` / study.py generation endpoints) → **#2217**
**Why:** These are the CRITICAL GAPS from the error/rescue map — silent data loss, inconsistent state, and invisible failures.
**Effort:** M (2 days total, parallelizable)
**Files:** `app/services/wallet_service.py`, `app/services/google_classroom.py`, `app/services/email_service.py`, `app/services/file_processor.py`
**Depends on:** Nothing
**Issues:** #2214, #2215, #2216, #2217

---

## P1 — High (Before September Retention Bundle)

### TODO-003: Lightweight In-Process Event Bus
**What:** Introduce a domain event system. Routes emit events (`StudentStudied`, `QuizCompleted`, `MaterialUploaded`). XP, notifications, streaks, and future knowledge graph subscribe independently. Start with Python asyncio signals or a simple pub/sub pattern. Migrate XP award calls from 6 direct service calls to event subscriptions.
**Why:** Without events, every new feature requires touching every existing feature. The September bundle (XP, badges, multilingual, Pomodoro) will create exponential coupling without this foundation.
**Effort:** L (3-5 days)
**Files:** New `app/shared/events.py`, refactor `app/api/routes/study.py`, `app/services/xp_service.py`
**Depends on:** Nothing
**Issue:** #2218

### TODO-004: Structured JSON Logging + Request Correlation IDs
**What:** Replace text-based logging with structured JSON. Add `trace_id` (UUID per request), `user_id`, `endpoint`, `duration` to every log line. Enable GCP Cloud Logging queries and aggregation. Foundation for the Observatory dashboard.
**Why:** Current text logs can't be queried, aggregated, or alerted on. Debugging production issues requires manual log reading. During rapid September development, structured logs prevent firefighting.
**Effort:** M (2 days)
**Files:** `app/core/logging_config.py`, middleware in `main.py`
**Depends on:** Nothing
**Issue:** #2219

### TODO-005: Fix N+1 Queries + Add Missing Indexes
**What:**
- Fix `/courses/students/search` — replace `db.query(Student).all()` + loop with `selectinload(Student.user)` or batch fetch (`courses.py` lines 165-181)
- Fix `/courses/teachers/search` — add `selectinload(Teacher.user)` (`courses.py` lines 130-151)
- Fix `data_export_service.py` `_collect_assignments()` — batch fetch with `.in_()` (lines 263-282)
- Add indexes: `Student(user_id)`, `CourseContent(created_by_user_id)`, `StudyGuide(guide_type)`
**Why:** Student search is O(N) on total students — becomes 15+ seconds at 500 students. Data export is unnecessarily slow for a legal compliance feature.
**Effort:** S (1 day)
**Files:** `app/api/routes/courses.py`, `app/services/data_export_service.py`, `app/models/student.py`, `app/models/course_content.py`, `app/models/study_guide.py`
**Depends on:** Nothing
**Issue:** #2220

### TODO-006: Redis-Backed Rate Limiting
**What:** Replace `slowapi` in-memory storage (`memory://`) with Redis-backed storage. Current setup resets on every Cloud Run cold start and doesn't share state across instances. Add Redis (GCP Memorystore or Cloud Run sidecar).
**Why:** Auth brute-force protection and AI cost control don't work at scale with in-memory rate limiting. Attacker can distribute requests across Cloud Run instances.
**Effort:** M (1 day code + infrastructure setup)
**Files:** `app/core/rate_limit.py`, Cloud Run config
**Depends on:** Redis infrastructure provisioning
**Issue:** #2221

---

## P2 — Medium (Backlog)

### TODO-007: Audit and Clean 49 Git Stashes
**What:** Review all 49 git stashes. Archive anything valuable as named branches. Delete stale stashes (>3 months old). Document what was in-progress for historical context.
**Why:** Cognitive overhead, potential data loss, and confusion for any new team member. Oldest stashes are from feature/823 era.
**Effort:** S (30 minutes)
**Depends on:** Nothing
**Issue:** #2222

### TODO-008: Migration Framework
**What:** Move ~150 lines of ALTER TABLE SQL from `main.py` startup into a proper migration system (Alembic or timestamped migration files). Each migration should have up() and down(). Currently migrations are one-way doors with no rollback.
**Why:** main.py is a brittle bomb — exception swallowing, no rollback on partial failure, unmaintainable at scale. Knowledge graph (Phase 3) will need 20+ new tables.
**Effort:** L (3-5 days)
**Files:** `main.py` (lines 176-300+), new `migrations/` directory
**Depends on:** Nothing
**Issue:** #2223

---

## Vision — Delight Opportunities

### DELIGHT-001: Study Streak Shared with Parent (#2224)
**What:** When a student hits a streak milestone (7, 14, 30 days), parent gets a notification: "Your child has studied 7 days in a row!" Celebration animation in-app.
**Why:** Emotional connection between parent and child. Zero AI cost. Drives parent engagement.
**Effort:** S (30 min)

### DELIGHT-002: Quiz of the Day (#2225)
**What:** Auto-generate a 5-question daily quiz from the student's most recent materials. Gamified with XP. Daily challenge card on student dashboard. Parents see completion.
**Why:** Creates daily habit loop. Drives daily active usage.
**Effort:** M (2 hours)

### DELIGHT-003: Teacher Gratitude (#2226)
**What:** Parent can send one-tap "thank you" to a teacher. Teachers see gratitude counter on dashboard ("12 parents thanked you this month").
**Why:** No competitor has this. Builds community. Differentiator.
**Effort:** S (1 hour)

### DELIGHT-004: Smart Study Time Suggestions (#2227)
**What:** Analyze XP/streak timestamps to suggest optimal study windows. "Maya usually studies best at 4pm on Tuesdays." Shows on parent briefing.
**Why:** Data-driven insight parents love. Zero AI cost — pure analysis.
**Effort:** S (1 hour)

### DELIGHT-005: Weekly Family Report Card Email (#2228)
**What:** Beautiful HTML email every Sunday: streak flame, XP earned, quizzes completed, study time, AI-generated encouragement. Parents forward to grandparents.
**Why:** Viral growth mechanic. Extends weekly digest with engagement data.
**Effort:** M (2 hours)

---

*Last updated: 2026-03-22 — CEO Plan Review (EXPANSION mode)*
