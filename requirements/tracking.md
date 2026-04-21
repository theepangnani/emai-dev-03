## 12. GitHub Issues Tracking

**Summary (as of Apr 20, 2026):** ~3,770 total issues — ~3,290 closed, ~480 open, 2,110+ commits
- **Features built:** 430+ enhancements closed
- **Bugs fixed:** 445+ bugs closed
- **Other closed:** 1,400+ (pilot prep, docs, testing, infra, misc)

**Apr 20 — CB-DEMO-001 demo modal re-plan (feature issues + §6.135 expansion):**
- CB-DEMO-001 demo modal re-plan — 4 feature issues scoped (#3784 upload copy + dismiss, #3785 Ask chatbox, #3786 Flash Tutor short cycle, #3787 Study Guide chips) + §6.135 requirements expanded (new subsections §6.135.4–§6.135.9) + gamification layer scoped (client-side only; XP/level/streak/quests/achievements/mastery ring) + Path C brand-alignment committed (Space Grotesk + Source Sans 3 + `var(--color-accent)` / `var(--color-accent-warm)`; no new hardcoded hex in demo CSS).
- **REQUIREMENTS update:** §6.135.4 Demo Upload Gating Copy & Dismiss-on-Tab-Change (#3784), §6.135.5 Ask Tab as Conversational Chatbox (#3785), §6.135.6 Flash Tutor Tab as Short Learning Cycle (#3786), §6.135.7 Study Guide Tab as Overview + Suggestion Chips (#3787), §6.135.8 Demo Gamification Layer (cross-cutting), §6.135.9 Demo Visual Alignment Decision — Path C Blend — all added to `requirements/features-part7.md`.
- **Scope discipline:** Ask-tab chatbox extends `POST /api/v1/demo/generate` (or adds `POST /api/v1/demo/ask/turn`) to accept a short conversation history; each turn counts against the existing rate-limit bucket. All other subsections are frontend-only. No new tables, no mastery/ILE persistence, no new content-safety surface.
- Snapshot date: 2026-04-20.

**Apr 20 — CB-DEMO-001 demo page re-plan (Mindgrasp-style UX):**
- **Epic #3758 delivered via PR #3769 (merged to master as `ac2d8df6`):** Single-source picker (sample | paste | gated upload) replaces the always-visible sample + "Use my own text" toggle; per-tab cache preserves generated output when switching Ask ↔ Study Guide ↔ Flash Tutor (source changes clear output but preserve user-typed questions); Flash Tutor renders `FlashcardDeck` flip cards instead of raw JSON; `GatedActionBar` under each completed output (Download PDF / Save / Follow-up / More flashcards) opens inline waitlist upsells. Scrollbar clipping by rounded modal corners fixed.
- **Classification:** Requirement Gap + Design Gap + 3 Bugs (mixed). Original CB-DEMO-001 spec didn't account for single-source UX, per-tab cache, flashcard UI, or gated extras.
- **Delivery model:** 4 parallel worktree streams → `integrate/cb-demo-001-replan` → one master PR. Every child PR passed 2× `/pr-review` with all suggestions resolved or filed as fast-follows before merge. Final integration PR also passed 2× `/pr-review`.
- **Issues closed:** #3758 (epic), #3759 (FlashcardDeck), #3760 (GatedActionBar), #3761 (scroll clip), #3762 (integration + REQUIREMENTS §6.135.2), #3724 (demo UI redesign — superseded by this work).
- **PRs merged:** #3763 (scroll clip), #3764 (GatedActionBar), #3765 (FlashcardDeck), #3767 (integration into `integrate/cb-demo-001-replan`), #3769 (integrate → master).
- **Fast-follows filed (open):** #3766 `waitlistHref` open-redirect guard; #3768 move `streamGenerate` side-effect out of `setTabState` updater (pre-StrictMode); #3770 wire `GatedActionBar.onUpsell` to analytics emitter; #3771 `FlashcardDeck.tsx` stale file-header comment.
- **REQUIREMENTS update:** §6.135.2 "Demo page re-plan (2026-04-20)" added to `requirements/features-part7.md` documenting the Design Gap and shipped spec.
- **Scope discipline:** Frontend-only. No backend, DB, schema, or env-var changes. Cloud Run deploy is a vanilla frontend-artifact swap.
- **Deploy:** Triggered on merge (workflow_dispatch run 24694426427); traffic routing via `gcloud run services update-traffic classbridge --to-latest --project=emai-dev-01` to follow.
- Snapshot date: 2026-04-20.

**Apr 19 — CB-DEMO-001 Production Launch + 30+ Fast-Follow Fixes:**
- **CB-DEMO-001 epic merged to master (#3708):** Instant Trial landing-page experience deployed to production — AI Instant Trial, Tuesday Mirror, Role Switcher, Proof Wall, Compliance page all live at classbridge.ca.
- **Production hotfixes:** feature_flags.variant column missing on prod (500 errors, #3713), redundant settings import shadowing (#3714), expose demo_landing_v1_1 variant to public /api/features (#3716), ship prompts/ in Docker image (demo Generate broken, #3718), demo verification magic link missing /api/v1 prefix (#3721), render demo output as markdown (was showing raw # and ** chars, #3723).
- **UI redesign + polish (PRs #3725, #3727, #3728, #3732, #3733, #3734, #3736):** DemoMascot + SVG icons (Part A), RoleSwitcher SVG icons (UI5), UI3 Generate step + DemoVerifiedPage polish + Copy fallback, UI2 modal chrome + signup + ConversionCard redesign, UI4 TuesdayMirror redesign, UI6 ProofWall redesign, plus consolidated UI redesign + 30+ fast-follow fixes.
- **Backend fast-follows:** indexes + test coverage (#3726), admin + compliance fast-follows bundle (#3729 → #3703/#3704/#3705/#3707/#3681/#3685), backend security fast-follows bundle (#3730 → #3640/#3665/#3655/#3629/#3664), rate-limit race — reserve slot before stream (#3731 → #3666).
- **PR-review cleanup:** un-skip timeout test + cleanup (#3742 → #3737/#3738), GenerateSubGuideModal Router test fix (#3712).
- **ASGF (CB-ASGF-001) issues filed (in-progress):** study guide generation stuck at 'Generating your lesson' — frontend never starts SSE (#3735, fixed via fix/3735a-asgf-stream-frontend, fix/3735b-asgf-slide-parallel), slide generator leaks pending tasks on early consumer close (#3740), frontend may leak previous session's SSE into new session (#3741), distinct visual treatment for failed ASGF slides (#3743).
- **Email digest:** From-name filter + on-demand 24h lookback (#3661 → #3652/#3653).
- **OAuth/Gmail:** correct OAuth scopes for parent Gmail service (#3597).
- **Open enhancements still pending:** verify path double-commits (#3656), location column on waitlist_signups for Proof Wall by_municipality (#3657), demo magic-link token exposed in URL query (#3660), Anthropic pricing hardcoded (#3667), temperature=0.7 hardcoded in stream_demo_completion (#3669), _waitlist_preview_position runs full COUNT per signup (#3670), tighten demo_session.user_agent truncation to 256 chars (#3671), verify /privacy and /terms routes before launch (#3682), verify privacy@classbridge.ca inbox monitored (#3683), CompliancePage prefer Unicode over HTML entities (#3684), lazy-load InstantTrialModal (#3697), AdminDemoSessionsPage bulk-select approve/reject (#3706), /demo/verify-failed route missing (#3722), redesign demo UI (#3724).
- Snapshot date: 2026-04-19.

**Apr 18 — CB-DEMO-001 Instant Trial & Demo Experience kickoff (epic #3599):**
- Epic #3599 opened for Instant Trial landing-page experience (AI Instant Trial + Tuesday Mirror + Role Switcher + Proof Wall); target launch May 13, 2026 with 50/50 A/B, sunset gate May 29 if M4 < 2.0×.
- 13 child issues filed (#3600–#3612); C1 content stream (#3612) authors Tuesday Mirror scripts for 5 Ontario boards (YRDSB/TDSB/DDSB/PDSB/OCDSB), Role Switcher ROM field-trip script, Proof Wall placeholder testimonials + 4 compliance badges, 3 demo prompts (ask/study-guide/flash-tutor), compliance-claims audit, testimonials consent process, REQUIREMENTS §6.135.
- Scope deltas from PRD v1.1: claude-haiku-4-5 (not GPT-4o-mini), Turnstile/PostHog/i18n deferred, "OECM procurement pathway" badge replaced with "Canadian-hosted", Tuesday Mirror names tools per mentor delta #8.
- All 14 streams merged into `integrate/cb-demo-001` (F1/F2/F3/B1/B2/B3/B4/C1/FE1/FE2/FE3/FE4/FE5/#3618). 70+ fast-follow suggestions filed as `CB-DEMO-001-fast-follow`.
- Snapshot date: 2026-04-18.

**Apr 18 — WhatsApp Production Integration + Digest Quality Improvements (CB-PEDI-001):**

*Production WhatsApp:*
- **Twilio setup:** Account created (classbridge), upgraded from trial, Canadian number +1 647-800-8533 purchased
- **WhatsApp Business:** Registered with Meta (Class Bridge Inc.), domain classbridge.ca verified via meta tag, business verification submitted (in review)
- **Template API:** `daily_digest` template approved on Meta + Twilio Content Template Builder (SID: HX5fb1ebf94a75f33d1f88a2955f5f7234)
- **Backend:** `send_whatsapp_template()` with Content API support, truncation safety (content truncated before template wrapping), dual-mode (Content API when SID configured, body-text fallback otherwise)
- **Deploy workflow:** TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN (Secret Manager), TWILIO_WHATSAPP_FROM, TWILIO_WHATSAPP_DIGEST_CONTENT_SID (both now GitHub Actions secrets via #3619)
- **Digest db.rollback():** Added missing rollback on per-parent digest failure to prevent cascading session poisoning (#3452)

*Digest Quality (PR #3626 — 4 issues bundled via 4 parallel worktree streams, 2× /pr-review):*
- **#3471 Sender identity:** Fixed Gmail parser / AI service data mismatch (parser emits sender_name/sender_email/received_at, AI consumer now reads those keys instead of non-existent from/date). Added `_resolve_sender_display()` with fallback to email local-part (e.g., `grade3.teacher` from `grade3.teacher@school.ca`). AI prompt now attributes emails to specific senders.
- **#3472 Noreply detection:** New `email_classifier.py` with `is_automated_sender()` regex matcher covering noreply/do-not-reply/notifications/alerts/mailer-daemon/postmaster/system/automated/bounces patterns. Parser now tags emails with `is_automated` flag. AI prompt prefixes `[AUTO]` so automated emails are grouped under "Automated Notifications" section. 43 new unit tests.
- **#3619 GitHub secrets:** TWILIO_WHATSAPP_FROM and TWILIO_WHATSAPP_DIGEST_CONTENT_SID moved from hardcoded YAML to GitHub Actions secrets for easier rotation.
- **#3620 Delivery status:** New `whatsapp_delivery_status` column (String(20), nullable) on DigestDeliveryLog — tracks "sent"/"failed"/"skipped"/NULL based on try/except AND return value of send_whatsapp_* functions. Startup migration in `app/db/migrations.py`. No more silent WhatsApp failures logged as "delivered".
- **Bonus:** Fixed pre-existing settings-variable-shadowing bug in parent_email_digest_job.py (line 161 was reading twilio_whatsapp_digest_content_sid off the shadowed ParentDigestSettings instead of app config).

- **PRs merged:** #3494, #3578, #3579, #3587, #3589, #3626 (integration PR bundling 4 fix streams)
- **Issues closed:** #3471, #3472, #3585, #3586, #3619, #3620
- **Issues remaining open:** #3591 (OTP template — blocked on Meta verification), #3592 (E2E UI testing), #3593 (Meta verification follow-up)
- **Tests:** 161 passing on integration branch (43 new in test_email_classifier)
- **Parallel agents used:** 4 worktree agents for fix streams + 2 /pr-review rounds

**Apr 14 — CB-ILE-001 M1-M4 Complete, Flash Tutor Fully Deployed:**
- **CB-ILE-001 M1 (Learning Mode + Adaptive):** Component extraction (HintBubble, ExplanationBubble, XpPopBadge, StreakCounter), within-session adaptive difficulty engine, session persistence + resume within 24h (#3203-#3205, PRs #3243, #3246, #3248)
- **CB-ILE-001 M2 (Topic Mastery + Cost Optimization):** Topic mastery tracking + weak areas, Surprise Me weighted selection, Fill-in-the-Blank with de-escalation, question bank pre-generation + hint caching, SM-2 spaced repetition + Memory Glow UI, 4 new ILE badges + student calibration (#3206-#3211, PRs #3245, #3250, #3252-#3255)
- **CB-ILE-001 M3 (Parent Teaching + Polish):** Parent Teaching Mode with personal hints + areas to revisit, Private Practice (hidden scores) + Career Connect, ILE data in daily + weekly parent email digest, Aha Moment detection (CSS confetti celebration) + Knowledge Decay notifications (#3212-#3215, #3272, PRs #3273, #3275-#3277, #3279)
- **CB-ILE-001 M4 (Hardening + Analytics):** Per-session cost logging, anti-gaming (10/day limit + rapid completion detection), admin analytics endpoint, response caching (60s TTL), quiz migration banner, 12 ILE tests, Flash Tutor from study guides (#3216-#3217, #3272, PRs #3274, #3275, #3278)
- **Post-deploy fixes:** Sidebar nav for student+parent, /api prefix on all ILE endpoints, parent hint storage, mastery rollback, cost Decimal, fill-blank de-escalation, CareerConnectCard error boundary (#3280-#3286, PR #3288)
- **Code review stats:** 25+ bugs found and fixed across 16 PRs, 10 enhancement issues filed (#3262-#3271)
- **Parallel agents used:** ~45 worktree agents across implementation, review, and integration phases
- CB-ILE-001 epic #3196: ALL milestones complete (M0-M4), 23 feature issues closed, deployed to production

**Apr 13 — Login Infinite Loop Fix, CB-ILE-001 M0 Review, Multi-Sender Email:**
- **Login infinite loop fixed:** non-memoized `loginWithToken` in `useEffect` dep array caused OAuth callback re-render loop; all 7 AuthContext functions wrapped with `useCallback`, Provider value with `useMemo`, circuit breaker refs added to Login.tsx and Register.tsx (#3233-#3238 via PR #3234)
- **CB-ILE-001 M0 PR review fixes:** session results crash, XP double-award, N+1 queries, parent-child index, CSS theme vars, topic ref equality, content safety check, hint data stripping (#3225-#3231 via PR #3232)
- **CB-ILE-001 M0 foundation:** Interactive Learning Engine database schema (5 tables), session service, API routes, Flash Tutor MCQ UI (#3196 via PR #3224 — open, pending merge)
- **Multi-sender email monitoring:** parents can whitelist multiple teacher email addresses for digest polling (#3178 via PR #3218)
- **Email digest wizard fix:** detect existing Gmail integration on wizard open + hardcoded turquoise → CSS theme variables (#3219, #3220 via PR #3221)
- Requirements updated: CB-ILE-001 added to roadmap (#3196), §6.127 multi-sender feature added (#3178)

**Apr 12-13 — Admin Feature Management, Email Digest Fixes, Upload Wizard:**
- Admin Feature Management deployed (§6.133): DB model, seed, API, frontend page, sidebar gating (#3141-#3157)
- Email Digest production defect fixed: Gmail callback 500 → null guard + logging + specific exceptions (#3031, #3159, #3160 via #3169)
- Email Digest root cause fixed: missing OAuth scopes (userinfo.email, userinfo.profile) — feature never worked for any user (#3176 via #3177)
- Upload Wizard improvements: randomized placeholders, stable React keys, aria-label accessibility (#3165, #3167, #3168, #3171, #3172 via #3169)
- Worksheet endpoint restored after botched merge (#3173, #3174 via #3175)
- Requirements updated: §6.127 OAuth scopes corrected, F-16 multi-sender whitelist added (#3178)
- New suggestion: migrate to OpenID Connect scopes (#3179)

**Apr 9-12 — Customer Database Epic & UTDF Deployment:**
- CB-PCM-001 Customer Database deployed (§6.132): 8 stories, 25 endpoints, 53 tests, 4 new tables (PRs #3106-#3112, merged via #3113)
- 8 PR review fixes for Customer Database (#3114-#3121)
- Post-deploy fixes: trailing slash 404 (#3126/#3135), transparent modal (#3136/#3137), checkbox appearance, surrogate emoji
- CB-UTDF-001 fully deployed (§6.131): all 15 stories live, pg_advisory_lock deadlock fixed (#3070-#3083, #3085, #3091)
- Practice test chip routing fix (#3100/#3102)
- Inspiration messages expanded to 80 per role (#3128-#3132)
- Code block parser fix (#3123), error feedback fix (#3124), stream retry fix (#3127)
- Features-part3.md split into 5 files (#3104)
- GCP cost optimization: DB switch script, deploy.yml fix (#3099)
- Open enhancements created: #3139, #3140, #3141, #3105, #3101, #3089, #3090, #3093, #3097, #3098

**Apr 1 — GitHub Actions Optimization & Repo Privacy:**
- Issue #2817: Security scanning restricted to master-only pushes (PR #2813)
- Issue #2818: Path filters, concurrency groups, and 10/day auto-deploy limit added (PR #2815)
- Issue #2819: Repository changed to private visibility
- Rationale: Private repo bills Actions minutes from 2,000 min/month free tier; optimizations prevent exceeding budget

**Mar 29 — Parent Email Digest Integration (CB-PEDI-001) planned:**
- 15 GitHub issues created (#2642-#2656) for §6.127 Parent Email Digest Integration
- M1 Foundation (April 2026): Gmail OAuth for parents, 3 new DB tables, CRUD routes, setup wizard (#2642-#2647)
- M2 Core Engine (May 2026): Gmail polling, Claude AI summarization, scheduled job, email template (#2648-#2653)
- Test suite (#2654), Phase 2 enhancements (#2655), Phase 3 archive (#2656)
- PRD: CB-PEDI-001-Parent-Email-Digest-PRD-v1.1 — M0 feasibility confirmed (YRDSB forwarding works)

**Week of Mar 22-28 highlights (163 issues closed):**
- CSV Template Import (#2167) — template download, CSV upload with preview/validation, bulk import for courses/students/assignments (§6.67.4)
- Weekly Family Report (#2228) — per-child engagement scores, streaks, quizzes, AI encouragement email (§6.63.1)
- Study Q&A Chatbot Redesign (#2548, #2561) — header/panel restructure, vertical action rows, input/error redesign, focus-visible accessibility
- Ask Chat Bot Flow (#2554) — replaced "Generate Study Material" tooltip with direct chatbot injection + auto-submit
- Admin Dashboard Clickable (#2536, #2544) — Platform Health metrics and Recent Activity items now clickable with keyboard accessibility
- Study Q&A Image Context (#2532) — source image descriptions passed to chatbot context for diagram citation
- Study Q&A Access Fix (#2535) — widened access check to match course material trust circle for enrolled students
- School Report Card Upload (#2286, §6.121) — upload, AI analysis, career path analysis, frontend wiring
- Course Material Metadata (#2395, §6.123) — clickable popovers for class/tasks in all tabs, mobile bottom sheet
- Document Privacy (#2269-#2274) — trust-circle access control, audit logging, access log tab
- Role-Based Messaging Restrictions (#2408, #2423) — enforce recipient restrictions per role
- Race Condition Fixes (#2567, #2569, #2578) — pendingQuestion useEffect chain, FABContext re-render optimization
- PR Review Fixes (#2589) — CSV import RBAC, hashed_password, savepoints, file size limit
- 20+ user-reported bugs fixed (#2520, #2521, #2533, #2570, #2579-#2582)

**Week of Mar 17-23 highlights (156 issues closed):**
- Streaming Study Guide Generation (#2120) — ChatGPT-like SSE streaming UX
- Bug Report System (#2087) — screenshot upload, GCS storage, GitHub issue creation, bot protection
- Pre-Launch Survey System (#1890) — role-specific surveys, admin dashboard, bot protection
- Study Guide Strategy Pattern (#1986) — document type & persona-based generation
- Performance Optimization (#1954-#1959) — N+1 query fixes across 6 route files
- Help KB Expansion (#1779, #2106) — 15 missing feature topics added
- Context-Aware Chatbot Study Q&A (#2060, #2072) — frontend §6.114
- Bot Protection (#1934) — honeypot + timing on all public forms
- SendGrid Click Tracking Fix (#2235-#2236) — disabled click tracking to fix SSL errors
- Defect batch 1 (8 bugs), weekend batch 1 (14 fixes), upload wizard fixes, sidebar fixes

Current feature issues are tracked in GitHub:

### Phase 1 - Completed
- Issue #2: ~~Google Classroom OAuth flow~~ (CLOSED)
- Issue #3: ~~Parent/Student dashboard~~ (CLOSED)
- Issue #4: ~~AI study guide generation~~ (CLOSED)
- Issue #5: ~~Assignment alerts and notifications~~ (CLOSED)
- Issue #6: ~~Frontend React application~~ (CLOSED)
- Issue #8: ~~Parent-teacher secure messaging~~ (CLOSED)
- Issue #15: ~~OpenAI/Vertex AI integration~~ (CLOSED)
- Issue #16: ~~Study guide generation API~~ (CLOSED)
- Issue #17: ~~Quiz generation API~~ (CLOSED)
- Issue #18: ~~Flashcard generation API~~ (CLOSED)
- Issue #19: ~~AI study tools frontend~~ (CLOSED)
- Issue #20: ~~Notification model and API~~ (CLOSED)
- Issue #21: ~~Email notification service~~ (CLOSED)
- Issue #22: ~~Assignment reminder background job~~ (CLOSED)
- Issue #23: ~~Notification UI~~ (CLOSED)
- Issue #32: ~~Role-based dashboards~~ (CLOSED)
- Issue #33: ~~Teacher email monitoring~~ (CLOSED)
- Issue #34: ~~Parent-child linking via Google Classroom discovery~~ (CLOSED)
- Issue #35: ~~Migrate parent-student to many-to-many relationship~~ (CLOSED)
- Issue #36: ~~Parent registers child from Parent Dashboard~~ (CLOSED — via invite flow)
- Issue #37: ~~Student invite email flow~~ (CLOSED)
- Issue #38: ~~Update parent linking endpoints for many-to-many~~ (CLOSED)
- Issue #39: ~~Auto-create Teacher record at registration~~ (CLOSED)
- Issue #40: ~~Shadow + invite flow for non-EMAI school teachers~~ (CLOSED)
- Issue #43: ~~Teacher type distinction (school_teacher vs private_tutor)~~ (CLOSED)
- Issue #48: ~~Unified invite system (shared invites table)~~ (CLOSED)
- Issue #44: ~~Google Classroom courses auto-sync for students~~ (CLOSED)
- Issue #47: ~~Student enrollment in courses~~ (CLOSED)
- Issue #52: ~~Teacher Google Classroom course sync (set teacher_id on synced courses)~~ (CLOSED)
- Issue #56: ~~Parent-student-Google sync flow (onboarding, parent sync, teacher info)~~ (CLOSED)

### Phase 1 - Implemented (Parent-First Platform Revision)
- Issue #60: ~~Parent registers child directly (name, email, grade, school)~~ (CLOSED)
- Issue #82: ~~Study guide model: add version, parent_guide_id, content_hash~~ (CLOSED)
- Issue #83: ~~Role-based study guide limits~~ (CLOSED)
- Issue #84: ~~Study guide duplicate detection endpoint~~ (CLOSED)
- Issue #85: ~~Study guide versioning~~ (CLOSED)
- Issue #86: ~~Role-based study guide visibility~~ (CLOSED)
- Issue #87: ~~Frontend study guide management UI~~ (CLOSED)
- Issue #88: ~~Update REQUIREMENTS.md with study guide management~~ (CLOSED)
- Issue #90: ~~Make student email optional — parent creates child with name only~~ (CLOSED)
- Issue #91: ~~Allow parents and students to create courses~~ (CLOSED)
- Issue #92: ~~Parent assigns courses to linked children~~ (CLOSED)
- Issue #93: ~~Add `created_by_user_id` and `is_private` fields to Course model~~ (CLOSED)
- Issue #94: ~~Disable auto-sync jobs — all Google/Gmail sync must be manual and on-demand~~ (CLOSED)
- Issue #95: ~~Parent Dashboard: course management UI (create, assign, view)~~ (CLOSED)
- Issue #97: ~~Parent Dashboard calendar-centric redesign v1~~ (CLOSED)
- Issue #98: ~~Study guide course assignment — PATCH endpoint + CourseAssignSelect component~~ (CLOSED)
- Issue #99: ~~Parent Dashboard v2: Left navigation + Edit Child modal + child filter toggle~~ (CLOSED)
- Issue #100: ~~Task system: backend model, CRUD API, cross-role assignment~~ (CLOSED)
- Issue #101: ~~Parent Dashboard v2: Day Detail Modal + task calendar integration~~ (CLOSED)
- Issue #102: ~~Parent Dashboard v2: Dedicated Courses page (`/courses`)~~ (CLOSED)
- Issue #103: ~~Parent Dashboard v2: Dedicated Study Guides page (`/study-guides`)~~ (CLOSED)
- Issue #104: ~~Cross-role task assignment — backend model & API~~ (CLOSED)
- Issue #105: ~~Dedicated Tasks page~~ (CLOSED)
- Issue #106: ~~Tasks displayed in calendar~~ (CLOSED)
- Issue #107: ~~Task archival — soft-delete, restore, permanent delete, auto-archive~~ (CLOSED)
- Issue #108: ~~Calendar sticky note cards — priority-colored, expandable~~ (CLOSED)
- Issue #115: ~~Study Guide: Improve formatting and readability~~ (CLOSED)
- Issue #117: ~~Bug: Task status dropdown filters are not working~~ (CLOSED)
- ~~Issue #118: Calendar: Enable editing task due date via drag-and-drop (IMPLEMENTED)~~ ✅
- Issue #123: ~~Bug: Calendar tasks not filtered by selected child in Calendar view~~ (CLOSED)
- Issue #124: ~~Course Page: Add Create Course CTA and flow entry point~~ (CLOSED)
- Issue #125: ~~Tasks Page: Convert Create New Task into a well-formatted modal~~ (CLOSED)
- Issue #51: ~~Deprecate POST /api/courses/ endpoint~~ (SUPERSEDED — endpoint now serves all roles)
- Issue #135: ~~Task entity linking: link tasks to courses, content, and study guides~~ (CLOSED)
- Issue #136: ~~Study guide conversion and duplicate prevention~~ (CLOSED)
- Issue #137: ~~Fix AI response JSON parsing (strip markdown code fences) + confirmation dialogs~~ (CLOSED)
- Issue #138: ~~Clickable entity badges on Tasks page~~ (CLOSED)
- Issue #157: ~~Non-blocking AI study material generation with progress placeholder~~ (CLOSED)
- Issue #158: ~~Add calendar quick-action buttons on Parent Dashboard~~ (CLOSED)
- Issue #159: ~~Fix: make users.email nullable in PostgreSQL for parent-created students~~ (CLOSED)
- Issue #160: ~~Replace native window.confirm with styled ConfirmModal component~~ (CLOSED)
- Issue #161: ~~Add lazy import retry to auto-recover from stale chunks after deploy~~ (CLOSED)
- Issue #162: ~~Backend: Add course_content_id FK to study_guides and is_default to courses~~ (CLOSED)
- Issue #163: ~~Backend: Auto-create default course + CourseContent on study guide generation~~ (CLOSED)
- Issue #164: ~~Frontend: Course Material tabbed detail view (Original / Study Guide / Quiz / Flashcards)~~ (CLOSED)
- Issue #165: ~~Frontend: Refactor Study Guides page to list course materials with child/course filters~~ (CLOSED)

### Phase 1 - Implemented (Teacher & Parent Enhancements)
- ~~Issue #187: Add cascading deletes and unique constraints~~ ✅
- ~~Issue #211: Multi-role support: allow users to hold multiple roles (Phase A)~~ ✅
- ~~Issue #212: Course materials lifecycle management (soft delete, archive, retention)~~ ✅
- ~~Issue #213: Message email notifications with dedup~~ ✅
- ~~Issue #218: Add loading skeleton preloaders to remaining pages~~ ✅
- ~~Issue #219-#224: Manual parent-to-teacher linking~~ ✅
- ~~Issue #225: Teacher adds/removes students from courses~~ ✅
- ~~Issue #226: Assign teacher to course during creation/editing~~ ✅
- ~~Issue #227: Teacher invite via course context~~ ✅
- ~~Issue #230-#233: Role-based inspirational messages~~ ✅
- ~~Issue #234: Teacher linking: send email notification to new teacher~~ ✅
- ~~Issue #235: Teacher linking: send email notification to existing teacher~~ ✅
- ~~Issue #236: MyKids: Add quick stats (course count, active tasks) to child overview cards~~ ✅
- ~~Issue #237: MyKids: Add icons to section headers and remove Courses from parent nav~~ ✅

### Phase 1 - Implemented (Feb 11-12 Sprint)
- ~~Issue #49: Manual assignment creation for teachers~~ ✅
- ~~Issue #112: Task reminders: daily in-app notifications for upcoming task due dates~~ ✅
- ~~Issue #140: Add rate limiting to auth, AI generation, and file upload endpoints~~ ✅
- ~~Issue #141: Add security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)~~ ✅
- ~~Issue #143: Add password reset flow (Forgot Password)~~ ✅
- ~~Issue #149: Implement JWT token refresh mechanism~~ ✅
- ~~Issue #152: Mobile responsive web: CSS breakpoints for 5+ pages~~ ✅
- ~~Issue #155: Add backend route tests for google, study, messages, notifications, admin, invites~~ ✅
- ~~Issue #181: HIGH: Fix RBAC gaps on students, assignments, courses, users, and content routes~~ ✅
- ~~Issue #182: HIGH: Secure logging endpoint and parent-created student passwords~~ ✅
- ~~Issue #184: MEDIUM: Fix LIKE pattern injection in search and study guide routes~~ ✅
- ~~Issue #206: Parent UX: Consolidated parent navigation via My Kids page~~ ✅
- ~~Issue #207: Parent Dashboard: Collapsible/expandable calendar (now defaults to collapsed — #544)~~ ✅
- ~~Issue #208: Fix overdue/due-today count mismatch between dashboard and TasksPage~~ ✅
- ~~Issue #209: Add assignee filter to TasksPage for filtering by student~~ ✅
- ~~Issue #210: Task Detail Page: Inline edit mode with all fields~~ ✅
- ~~Issue #255-#257: Multi-role support Phase B requirements and issues created~~ (PLANNED)
- ~~Issue #258: Admin broadcast messaging: send message + email to all users~~ ✅
- ~~Issue #259: Admin individual messaging: send message + email to a specific user~~ ✅
- ~~Issue #260: Inspirational messages in emails: add role-based quotes to all outgoing emails (PLANNED)~~ ✅
- ~~Issue #261: Notification click opens popup modal with full message content~~ ✅
- ~~Issue #262: Messages page: show all admin messages for every user~~ ✅
- ~~Issue #263: User-to-admin messaging: any user can message admin, all admins get email~~ ✅

### Phase 1 - Implemented (Feb 14 Sprint)
- ~~Issue #144: Fix N+1 query patterns in task list, child list, and reminder job~~ ✅ (fixed in #241)
- ~~Issue #180: HIGH: Add JWT token revocation and rate limiting~~ ✅
- ~~Issue #186: MEDIUM: Fix N+1 queries in messages, tasks, and parent routes~~ ✅ (fixed in #241)
- ~~Issue #241: Performance: Fix N+1 queries in tasks, messages, and parent dashboard~~ ✅
- ~~Issue #246: UX: Parent-first flow improvements~~ ✅
- ~~Issue #250: Student self-enrollment: add browse/enroll/unenroll UI~~ ✅
- ~~Issue #251: Add visibility check to student self-enrollment endpoint~~ ✅
- ~~Issue #252: Teacher invites parent to ClassBridge~~ ✅
- ~~Issue #261: Notification click opens popup modal with full message content~~ ✅
- ~~Issue #262: Messages page: show all admin messages for every user~~ ✅
- ~~Issue #263: User-to-admin messaging: any user can message admin, all admins get email~~ ✅

### Phase 1 - Implemented (Feb 15: CI + Mobile MVP Sprint)
- ~~Issue #247: Accessibility: ARIA labels, keyboard navigation, skip-to-content~~ ✅
- ~~Issue #273: CI hardening: verify test job blocks deploy on failure~~ ✅ (deploy.yml already properly structured; 305 backend + 183 frontend tests passing)
- ~~Issue #308: Update ClassBridge logo and favicon assets~~ ✅
- ~~Issue #309: Admin endpoint to update user email with cascade to invites~~ ✅
- ~~Issue #256: Auto-create profiles on registration~~ ✅
- ~~Issue #257: Multi-role registration with checkbox UI~~ ✅

### Phase 1 - Implemented (Feb 15: Bug Fixes, Test Expansion & Backup Infrastructure)
- ~~Issue #153: Fix FlashcardsPage stale closure bug in keyboard handler~~ ✅ (useRef pattern for stable keyboard event handler)
- ~~Issue #154: Add frontend unit tests (vitest)~~ ✅ (75 new tests: FlashcardsPage 27, QuizPage 15, StudyGuidePage 14, TasksPage 20; total 253 frontend tests)
- ~~Issue #353: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅ (daily backups 02:00 UTC, PITR 7-day, log-based metric + alert policy, 4 scripts + runbook)
- ~~Issue #411: Improve landing page logo clarity and hero branding~~ ✅
- Fix CI test failures: Add `pyproject.toml` with `testpaths = ["tests"]` and update `deploy.yml` — `scripts/load_test.py` matched pytest's `*_test.py` pattern, causing secret key mismatch in test environment ✅

### Phase 1 - Implemented (Feb 15: UI Polish)
- ~~Issue #420: Add show/hide password toggle to all auth pages~~ ✅ (eye icon toggle on Login, Register, Reset Password, Accept Invite)
- ~~Issue #427: Reduce whitespace around logo and increase size~~ ✅ (CSS negative margins to crop built-in PNG padding on auth pages, landing nav/hero, dashboard header)

### Phase 1 - Implemented (Feb 16: Bug Fix)
- ~~Issue #429: Fix study guide 404 for parents (guide ID 8)~~ ✅ (add logging to distinguish "not found" vs "access denied"; exclude archived guides from duplicate detection; change enforce_study_guide_limit to soft-delete instead of hard-delete; improve frontend 404 error message with navigation links)

### Phase 1 - Implemented (Feb 16: Courses Page Fix)
- ~~Issue #435: Courses page: missing styles and course materials not displayed~~ ✅ (add .child-selector/.child-tab CSS to CoursesPage.css; implement inline course content expansion on course cards for parent and student views)

### Phase 1 - Implemented (Feb 16: Hover Buttons Fix)
- ~~Issue #446: Missing hover edit button on course tiles and assign-to-course on material tiles~~ ✅ (add edit ✏️ button to parent child-course tiles and student enrolled-course tiles; add move-to-course 📂 button to course material rows on StudyGuidesPage with course selector modal; add `course_id` to `CourseContentUpdate` schema for reassignment)

### Phase 1 - Implemented (Feb 17: Docx OCR + Math-Aware AI Prompts)
- ~~Issue #532: Word doc embedded screenshots not OCR'd + study guide should solve math problems~~ ✅ (always OCR all embedded images in .docx regardless of text length; enhance study guide/quiz/flashcard AI prompts to detect math problems and provide step-by-step solutions; 7 new unit tests for OCR logic)

### Phase 1 - Implemented (Feb 17: Inline Generation Loading)
- ~~Issue #527: Quiz/Flashcard generation should show inline loading in content area instead of blocking spinner~~ ✅ (replace full-screen overlay with inline spinner + pulsing message in content area on CourseMaterialDetailPage; auto-switch to target tab on generation; tabs remain navigable during generation)

### Phase 1 - Implemented (Feb 17: Navigation & Back Button Fix)
- ~~Issue #529: Missing back button on Course Materials and Courses pages~~ ✅ (add `showBackButton` prop to DashboardLayout; back button uses `navigate(-1)` for true browser history back; enabled on all sub-pages: Courses, Course Materials, CourseDetail, CourseMaterialDetail, MyKids, Tasks, Help, FAQ)
- ~~Issue #530: Parent sidebar missing Courses and Course Materials navigation links~~ ✅ (restore Courses and Course Materials to parent nav items in DashboardLayout sidebar)

### Phase 1 - Implemented (Feb 18: Dashboard Simplification — #540, PR #545)
- ~~Issue #540: Parent Dashboard Simplification — Single Hub with Urgency-First Layout~~ ✅
- ~~Issue #541: Dashboard: Persistent sidebar navigation (replace hamburger)~~ ✅
- ~~Issue #542: Dashboard: Alert banner + unified child filter pills~~ ✅
- ~~Issue #543: Dashboard: Quick Actions bar + Student Detail Panel with urgency-grouped tasks~~ ✅
- ~~Issue #544: Dashboard: Calendar default collapsed + dead code cleanup~~ ✅

### Phase 1 - Implemented (Feb 18: Dashboard UX Polish — #557)
- ~~Issue #557: Parent Dashboard UX: Today's Focus header, icon-only sidebar, collapsible detail panel~~ ✅ (removed redundant status cards; simplified AlertBanner to overdue + invites only; added Today's Focus header with urgency badges and "All caught up!" state; converted sidebar to always icon-only with bigger icons and hover tooltips; made StudentDetailPanel collapsible with summary header; redesigned QuickActionsBar with primary/secondary action hierarchy)

### Phase 1 - Implemented (Feb 21: UI/UX Audit — Phase 1 Improvements, #668)

**Round 1 (Parallel Streams A/B/C):**
- ~~Issue #646: Student Dashboard: Today's Focus header with urgency badges~~ ✅
- ~~Issue #647: Student Dashboard: Assignment urgency sorting with color-coded due dates~~ ✅
- ~~Issue #648: Teacher Dashboard: Class activity summary & at-a-glance overview~~ ✅
- ~~Issue #650: Teacher Dashboard: Upload Material quick action~~ ✅
- ~~Issue #651: Student onboarding card for material upload workflow~~ ✅
- ~~Issue #653: Admin Dashboard: Trend indicators & recent activity feed~~ ✅

**Round 2 (Parallel Streams A/B/C):**
- ~~Issue #649: Auto-create task prompt after study guide generation~~ ✅
- ~~Issue #652: Enhanced empty states with contextual CTAs across all dashboards~~ ✅
- ~~Issue #654: Calendar first-visit expanded state with onboarding tooltip~~ ✅
- ~~Issue #655: Persist filter state in URL query parameters~~ ✅
- ~~Issue #656: Notification center — "View All" page & persistent history~~ ✅
- ~~Issue #658: Standardize navigation items & SVG icons across all roles~~ ✅
- ~~Issue #660: Micro-interactions (button press, card hover, section collapse)~~ ✅

**Round 3 (Parallel Streams A/B/C/D):**
- ~~Issue #657: Refactor ParentDashboard.tsx — extract useParentDashboard hook + TodaysFocusHeader (1668→544 LOC)~~ ✅
- ~~Issue #659: Consistent loading states, last-synced timestamps, retry buttons~~ ✅
- ~~Issue #661: Breadcrumb navigation for all detail pages (desktop trail + mobile back-link)~~ ✅
- ~~Issue #662: Mobile touch: long-press drag, swipe calendar nav, modal scroll fix~~ ✅

### Phase 1 - Implemented (Feb 21: Student Dashboard Redesign — #708, PR #709)
- ~~Issue #708: Student Dashboard: "Focused Command Center" redesign~~ ✅ (hero greeting with urgency pills + stat chips, notification alerts for parent/teacher requests, quick action cards, Coming Up timeline merging assignments + tasks, recent materials, course chips, create course modal, onboarding card, `sd-` CSS prefix scoping, 27 tests updated)

### Phase 1 - Implemented (Feb 22: Print & PDF Export — #764, PR #763)
- ~~Issue #764: Print and Download PDF for study materials~~ ✅ (Print + Download PDF buttons on all 4 Course Material Detail tabs; html2pdf.js dynamic import; static print views for quiz all-questions and flashcards all-cards; shared `exportUtils.ts` utility)

### Phase 1 - Implemented (Mar 9: Enrollment Features — #1574, #1575, #1576)
- ~~Issue #1574: feat: add class_code field to Course model~~ ✅ (PR #1573)
- ~~Issue #1575: feat: enrollment search filters for course browse~~ ✅ (PR #1571)
- ~~Issue #1576: feat: enrollment approval system for courses~~ ✅ (PR #1572)

### Phase 1 - Defect Fixes (Mar 21, 2026 — Defect Batch 1, PR #2102)
- ~~Issue #2093: bug: sub study guide name missing from identifier display~~ ✅ (show sub-guide name in breadcrumb + topic badge on StudyGuidePage)
- ~~Issue #2094: bug/ux: "Upload Material" button on parent dashboard mislabeled~~ ✅ (renamed to "Study" with book icon)
- ~~Issue #2095: bug: sub study guides only visible on master document page~~ ✅ (fetch sibling sub-guides from parent when viewing a sub-guide)
- ~~Issue #2096: bug: Analytics page orphaned with no navigation menus~~ ✅ (wrapped in DashboardLayout and added Analytics nav item)
- ~~Issue #2097: bug: Reset Password in wrong location~~ ✅ (moved from "More" dropdown to Account Settings page)
- ~~Issue #2098: requirement gap: incorrect/uncertain AI answers saveable as study guides~~ ✅ (added uncertainty detection on frontend + backend that blocks saving; see §6.115)
- ~~Issue #2099: bug/regression: "Has sub study guide" tag not showing on materials list~~ ✅ (moved badge from title row to meta row to avoid CSS overflow hidden)
- ~~Issue #2100: bug: clicking View on sub study guide didn't navigate~~ ✅ (route to `/study/guide/${id}` instead of parent's course material page)

### Phase 1 & 2 - Implemented (Mar 17-23, 2026 — 156 issues closed)
- ~~Issue #2120: Streaming Study Guide Generation — SSE streaming with ChatGPT-like UX~~ ✅ (PR #2200, §6.116)
- ~~Issue #2087: User Bug Report with Screenshot → GitHub Issue + Admin Notification~~ ✅ (PR #2088, §6.115)
- ~~Issue #2103: Bug Report Bot Protection — honeypot + cooldown~~ ✅ (§6.115.2)
- ~~Issue #2114: Bug Report GCS signed URLs for screenshots~~ ✅ (§6.115)
- ~~Issue #1890: Pre-Launch Survey System — backend, public pages, admin dashboard~~ ✅ (§6.102)
- ~~Issue #1986: Study Guide Strategy Pattern — document type & persona-based generation~~ ✅ (§6.106)
- ~~Issue #1954-#1959: Performance Optimization — N+1 query fixes across 6 route files~~ ✅ (§6.104)
- ~~Issue #1779: Help KB Expansion — 15 missing feature topics added~~ ✅ (§6.103)
- ~~Issue #2060: Context-Aware Chatbot Study Q&A — frontend §6.114~~ ✅ (PR #2072)
- ~~Issue #2024: Holiday Dates — YRDSB 2026-27 seed data~~ ✅
- ~~Issue #1934: Bot Protection — honeypot + timing on all public forms~~ ✅
- ~~Issue #2235: SendGrid Click Tracking Fix — disabled click tracking to fix SSL errors~~ ✅ (PR #2236)
- ~~Issue #2068: Advisory lock migrations~~ ✅
- ~~Issue #2067: Migrations moved to startup_event~~ ✅
- ~~Issue #2065: Cloud Run startup probe~~ ✅
- ~~Issue #2093-#2100: Defect Batch 1 — 8 bugs from Defects.docx~~ ✅ (PR #2102)
- ~~Issue #2086: Weekend Batch 1 — 14 fixes merged~~ ✅
- ~~Issue #2233: Project plan & phase-2 analysis docs~~ ✅
- ~~Issue #2231: CEO Platform Review TODOS.md~~ ✅

### Phase 1 - In Progress (Student UX Simplification Sprint — Mar 2026)
- Issue #1022: [Student UX] Merge Classes and Materials pages into unified Study Hub (/study) — IN PROGRESS
- Issue #1023: [Student Nav] Remove Quiz History from primary navigation — embed stats in Study Hub — IN PROGRESS
- Issue #1024: [Student Nav] Move Email Settings from primary navigation to profile dropdown — IN PROGRESS
- Issue #1025: [Student UX] Simplify Student Dashboard quick actions — remove secondary setup actions — IN PROGRESS
- Issue #1026: [UX] Remove inspirational quote from all subpages — show only on Home dashboard — IN PROGRESS
- Issue #1027: [Student UX] Tasks page: group tasks by urgency, show calendar by default on desktop — IN PROGRESS
- Issue #1028: [UX] Standardize action button labels across student pages — replace icon-only buttons — PLANNED
- Issue #1029: [Student Nav] Reduce student navigation from 8 items to 5: Home, Study, Tasks, Messages, Help — IN PROGRESS

### Phase 1 - Open (Parent Dashboard Redesign — Epic #710)
- ~~Issue #710: Epic: Parent Dashboard Visual Redesign~~ ✅
- ~~Issue #711: Parent Dashboard: Visual refresh with distinctive design language~~ ✅
- ~~Issue #712: Parent Dashboard: Add "Coming Up" timeline for selected child~~ ✅
- ~~Issue #713: Parent Dashboard: Multi-child comparison cards in All Children mode~~ ✅
- ~~Issue #714: Parent Dashboard: Clean up dead CSS and scope with `pd-` prefix~~ ✅
- ~~Issue #715: Parent Dashboard: Refactor useParentDashboard into focused sub-hooks~~ ✅
- ~~Issue #716: Parent Dashboard: Enhanced onboarding for first-time parents~~ ✅
- ~~Issue #717: Parent Dashboard: Make urgency overview persistent (non-dismissible)~~ ✅
- ~~Issue #718: Parent Dashboard: Add course activity feed for selected child~~ ✅
- ~~Issue #719: Parent Dashboard: Accessibility improvements (ARIA, keyboard, focus)~~ ✅

### Phase 1 - Open
- Issue #41: Multi-Google account support for teachers
- ~~Issue #42: Manual course creation for teachers~~ ✅
- Issue #57: Auto-send invite email to shadow teachers on creation
- Issue #58: Add is_platform_user flag to Teacher model
- Issue #59: Teacher Dashboard course management view with source badges
- Issue #61: Content privacy controls and version history for uploads
- Issue #62: teacher_google_accounts table for multi-account OAuth
- ~~Issue #89: Auto-create student account when parent links by email~~ ✅
- Issue #109: AI explanation of assignments
- Issue #110: Add assignment/test to task (link tasks to assignments) — courses, content, and study guides now linkable; assignment linking pending
- ~~Issue #111: Student self-learn: create and manage personal courses~~ ✅
- Issue #114: Course materials: file upload and storage (GCS) — upload + text extraction done, GCS pending
- ~~Issue #116: Courses: Add structured course content types + reference/Google Classroom links~~ ✅
- ~~Issue #119: Recurring Tasks: Feasibility + implementation proposal~~ ✅
- ~~Issue #126: Calendar Task Actions: Add quick links beyond Create Study Guide~~ ✅
- ~~Issue #166: Audit logging: persistent audit trail with admin API and UI~~ ✅
- ~~Issue #167: Task Detail Page with full task info and actions~~ ✅
- ~~Issue #168: Calendar task popover: icon buttons + task detail navigation fix~~ ✅
- ~~Issue #172: Fix ungrouped study guide categorization (Move to Course)~~ ✅
- ~~Issue #173: Move to Course: searchable dropdown + create new course~~ ✅
- ~~Issue #174: Global search: backend unified search endpoint~~ ✅
- ~~Issue #175: Global search: frontend search component in DashboardLayout~~ ✅
- ~~Issue #183: Task Detail Page: link/unlink resources (courses, materials, study guides)~~ ✅
- ~~Issue #193: Task list: click task row to navigate to task detail page~~ ✅
- ~~Issue #194: Rename 'Study Guide' to 'Course Material' across UI and navigation~~ ✅
- ~~Issue #420: Frontend: Add show/hide password toggle to all auth pages~~ ✅
- ~~Issue #509: Send welcome email after user registration~~ ✅
- ~~Issue #510: Send acknowledgement email after email verification~~ ✅
- ~~Issue #169: Color theme: Clean up hardcoded CSS colors (prerequisite for themes)~~ ✅
- ~~Issue #170: Color theme: Dark mode (ThemeContext, ThemeToggle, dark palette)~~ ✅
- ~~Issue #171: Color theme: Focus mode (muted warm tones for study sessions)~~ ✅

### Phase 1.5 - Calendar Extension, Content, Search, Mobile & School Integration
- ~~Issue #174: Global search: backend unified search endpoint~~ ✅
- ~~Issue #175: Global search: frontend search component in DashboardLayout~~ ✅
- ~~Issue #152: Mobile responsive web: CSS breakpoints for 5+ pages~~ ✅
- ~~Issue #308: Update ClassBridge logo and favicon assets~~ ✅
- ~~Issue #195: AI auto-task creation: extract critical dates from generated course materials~~ ✅
- Issue #96: Student email identity merging (personal + school email)
- ~~Issue #45: Extend calendar to other roles (student, teacher) with role-aware data (parent calendar done in #97)~~ ✅
- Issue #46: Google Calendar push integration for tasks
- ~~Issue #25: Manual Content Upload with OCR (enhanced) — document upload + text extraction done; image OCR for embedded images in .docx~~ ✅ (#523)
- Issue #28: Central Document Repository
- ~~Issue #53: Background periodic Google Classroom sync for teachers~~ ✅
- Issue #113: School & School Board model
- ~~Issue #201: Parent UX: Single dashboard API endpoint~~ ✅
- ~~Issue #202: Parent UX: Status-first dashboard~~ ✅
- ~~Issue #203: Parent UX: One-click study material generation~~ ✅
- ~~Issue #204: Parent UX: Fix filter cascade on Course Materials page~~ ✅
- ~~Issue #205: Parent UX: Reduce modal nesting~~ ✅
- ~~Issue #206: Parent UX: Consolidated parent navigation via My Kids page~~ ✅
- ~~Issue #207: Parent Dashboard: Collapsible/expandable calendar (now defaults to collapsed — #544)~~ ✅

### Phase 2 — Dashboard & UI Polish Sprint (Mar 8-10, 2026)
- ~~Issue #1615: Chat FAB icon and Study Guide UI polish iterations~~ ✅ (§6.84)
- ~~Issue #1616: Upload wizard loses class selection and resets on prop changes~~ ✅ (§6.85)
- ~~Issue #1617: Collapsible dashboard panels, simplified view, and child card styling~~ ✅ (§6.86)
- ~~Issue #1618: Filter parent Recent Activity to relevant items only~~ ✅ (§6.87)
- ~~Issue #1619: Create Class wizard polish and enrollment system follow-ups~~ ✅ (§6.88)
- ~~Issue #1620: Dashboard quick actions reorganization and additions~~ ✅ (§6.89)
- ~~Issue #1621: Document download 404 for pre-migration content (follow-up)~~ ✅
- ~~Issue #1622: MyKidsPage polish — school name, View navigation, SectionPanel headers~~ ✅ (§6.90)

### Phase 2
- ~~Issue #26: Performance Analytics Dashboard (umbrella — broken into #469-#474)~~ ✅
- ~~Issue #27: Notes & Project Tracking Tools~~ → Replaced by #1090 (Epic: Contextual Notes System)
- Issue #1090: **Epic: Contextual Notes System** (#1084 data model, #1085 side panel UI, #1086 images, #1087 task linking, #1088 search, #1089 parent access)
- Issue #29: TeachAssist Integration
- Issue #50: Data privacy & user rights (FERPA/PIPEDA compliance)

### Phase 2 — Performance Analytics (#26) ✅ COMPLETE
- ~~Issue #469: Analytics: Grade data pipeline (GradeRecord model, sync service, seed service)~~ ✅
- ~~Issue #470: Analytics: Backend aggregation service and API endpoints~~ ✅
- ~~Issue #471: Analytics: Frontend dashboard with Recharts (LineChart, BarChart, summary cards)~~ ✅
- ~~Issue #472: Analytics: AI-powered performance insights (on-demand via OpenAI)~~ ✅
- ~~Issue #473: Analytics: Weekly cached progress reports (ProgressReport model, 24h TTL)~~ ✅
- Issue #474: Analytics: Test expansion (14 backend + 6 frontend tests written; more coverage possible)

### Phase 2 — Admin Email & Broadcast Management
- Issue #513: Admin: View and edit email templates from dashboard
- Issue #514: Admin: Broadcast email history with reuse and resend

### Phase 2 — FAQ / Knowledge Base
- ~~Issue #437: FAQ: Backend models — FAQQuestion + FAQAnswer tables~~ ✅
- ~~Issue #438: FAQ: Pydantic schemas for request/response validation~~ ✅
- ~~Issue #439: FAQ: Backend API routes — CRUD + admin approval workflow~~ ✅
- ~~Issue #440: FAQ: Integrate FAQ into global search~~ ✅
- ~~Issue #441: FAQ: Error-to-FAQ reference system~~ ✅
- ~~Issue #442: FAQ: Frontend pages — FAQ list, detail, and admin management~~ ✅
- ~~Issue #443: FAQ: Backend + frontend tests~~ ✅
- ~~Issue #444: FAQ: Seed initial how-to entries for pilot~~ ✅

### March 6 Pilot — Mobile MVP (Completed)
- ~~Issue #364: Mobile MVP: API client & auth modules (AsyncStorage, refresh tokens)~~ ✅
- ~~Issue #365: Mobile MVP: AuthContext & LoginScreen~~ ✅
- ~~Issue #366: Mobile MVP: Navigation setup (auth-gated stack + bottom tabs)~~ ✅
- ~~Issue #367: Mobile MVP: ParentDashboardScreen~~ ✅
- ~~Issue #368: Mobile MVP: ChildOverviewScreen~~ ✅
- ~~Issue #369: Mobile MVP: CalendarScreen (read-only)~~ ✅
- ~~Issue #370: Mobile MVP: MessagesListScreen~~ ✅
- ~~Issue #371: Mobile MVP: ChatScreen (read & reply)~~ ✅
- ~~Issue #372: Mobile MVP: NotificationsScreen~~ ✅
- ~~Issue #373: Mobile MVP: ProfileScreen (view & logout)~~ ✅
- ~~Issue #374: Mobile MVP: UI polish (loading, empty states, pull-to-refresh, tab badges)~~ ✅
- ~~Issue #357: Web: Update CORS config for mobile app origins~~ ✅ (Not needed — CORS is browser-only, React Native bypasses it)

### March 6 Pilot — Web Production Readiness (In Progress)
- ~~Issue #354: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅
- ~~Issue #353: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅ (duplicate of #354)
- ~~Issue #355: API Versioning Strategy: Options & Decision~~ ✅ (Decision: no versioning needed for pilot; mobile calls same `/api/*` endpoints)
- Issue #358: Web: End-to-end testing on production — smoke test script created (`scripts/smoke-test.py`), needs credentials for full run
- ~~Issue #359: Web: Performance validation with 50+ simulated users~~ ✅
- ~~Issue #360: Web: Create pilot user accounts and demo data~~ ✅
- ~~Issue #361: Web: Monitoring and alerting setup for production~~ ✅
- ~~Issue #362: Web: Pilot onboarding prep (welcome email, quick-start guide)~~ ✅
- ~~Issue #363: Web: Deploy freeze and dress rehearsal~~ ✅
- ~~Issue #385: Create privacy policy and terms of service pages~~ ✅
- Issue #265: Go live: Production deployment with custom domains
- Issue #375: Mobile MVP: Device testing (iOS + Android via Expo Go) — code quality prep done, physical testing pending
- ~~Issue #376: March 6 Pilot Launch: Go-Live Checklist~~ ✅

**Pilot prep subtasks (parallelizable):**
- ~~Issue #396: Register custom domains with Cloud Run (depends on DNS access)~~ ✅
- ~~Issue #397: Update Google OAuth redirect URIs for production domain (depends on #396)~~ ✅
- ~~Issue #398: Create pilot user accounts and verify login~~ ✅
- ~~Issue #399: Run smoke-test.py against production with all 4 roles (depends on #398)~~ ✅
- ~~Issue #400: Verify SendGrid email delivery from production~~ ✅
- ~~Issue #388: Launch day: Monitoring and incident response plan~~ ✅
- ~~Issue #401: Set Cloud Run min-instances=1 to avoid cold starts~~ ✅
- ~~Issue #402: Prepare Expo Go access instructions for pilot parents~~ ✅
- ~~Issue #406: Update documentation with production URL (classbridge.ca)~~ ✅
- ~~Issue #386: Create pilot user accounts and seed demo data~~ ✅
- ~~Issue #387: Pilot onboarding: Welcome email and setup guide~~ ✅
- ~~Issue #389: Marketing: Landing page for limited launch~~ ✅
- ~~Issue #409: Email branding: Add ClassBridge logo to all email templates~~ ✅
- ~~Issue #410: Email branding: Unify color theme across all email templates~~ ✅
- ~~Issue #321: Enhance health endpoint with version info~~ ✅
- ~~Issue #359: Performance validation with load test script~~ ✅
- ~~Issue #363: Deploy freeze and dress rehearsal~~ ✅
- ~~Issue #376: March 6 Pilot Launch: Go-Live Checklist~~ ✅
- ~~Issue #408: Email format validation on all input fields~~ ✅

### Mobile App — Post-Pilot (Phase 3-4, Open)
- Issue #377: Phase 3: Add notification polling to mobile app
- Issue #378: Phase 3: React Query offline caching for mobile
- Issue #379: Phase 4: Student mobile screens (dashboard, assignments, study viewer)
- Issue #380: Phase 4: Teacher mobile screens (messages, notifications, quick view)

### Mobile App — Original Full Plan (Deferred, Open)

**Backend API Preparation (#311-#322) — Deferred to post-pilot as needed:**
- ~~Issue #311: Backend: Implement API Versioning (v1)~~ (CLOSED — not needed for pilot; mobile calls same `/api/*` endpoints)
- Issue #312: Backend: Add Pagination to All List Endpoints
- Issue #313: Backend: Implement Structured Error Responses
- Issue #314: Backend: Set Up Firebase Admin SDK
- Issue #315: Backend: Create DeviceToken Model and Registration Endpoints
- Issue #316: Backend: Implement Push Notification Service
- Issue #317: Backend: Integrate Push Notifications with Key Events
- ~~Issue #318: Backend: Assignment Reminder Background Job~~ ✅
- Issue #319: Backend: Profile Picture Upload Endpoint
- Issue #320: Backend: Assignment File Upload Endpoint
- ~~Issue #321: Backend: Enhance Health Endpoint with Version Info~~ ✅
- ~~Issue #322: Backend: Integration Tests for v1 API~~ ✅

**Mobile App Screens (#323-#340) — Superseded by pilot MVP issues #364-#374:**
- Issue #323-#340: Original full mobile plan screens (many superseded by simpler pilot MVP)

**Testing & Deployment (#341-#346):**
- ~~Issue #340: Testing: Manual Testing - iOS~~ ✅
- ~~Issue #341: Testing: Manual Testing - Android~~ ✅
- Issue #343: Deployment: Beta Testing with TestFlight (iOS) — Phase 3+
- Issue #344: Deployment: Beta Testing with Google Play Internal Testing — Phase 3+
- Issue #345: Deployment: Prepare App Store Submission - iOS — Phase 4
- ~~Issue #346: Deployment: Prepare Google Play Submission - Android — Phase 4~~ ✅

**Documentation (#347-#349) & Risk (#350-#352):**
- Issue #347-#349: Mobile documentation (deferred)
- Issue #350: RISK: Push Notification Delivery Failures
- Issue #351: RISK: File Upload Storage Costs
- Issue #352: Infrastructure: Set Up CI/CD for Mobile Builds — Phase 4

### Phase 2+ (Future)
- Issue #192: ~~Native mobile apps~~ → SUPERSEDED by #364-#380

### Phase 3 — Course Planning & Guidance (#500-#511)
- Issue #511: School Board Integration — board-specific catalogs, student ↔ board linking (depends on #113)
- Issue #500: Course Catalog Model — board-scoped high school course database with prerequisites, credits, grade levels
- Issue #501: Academic Plan Model — multi-year high school course plan per student
- Issue #502: Prerequisite & Graduation Requirements Engine — validate plans against OSSD rules
- Issue #503: AI Course Recommendations — board-specific personalized guidance based on student profile and goals
- Issue #504: Semester Planner UI — select and arrange courses per semester
- Issue #505: Multi-Year High School Planner UI — visual Grade 9-12 course map
- Issue #506: University Pathway Alignment — map course plans to post-secondary program requirements
- Issue #507: Course Planning Navigation & Dashboard Integration
- Issue #508: Course Planning Tests — backend + frontend test coverage

### Phase 4+
- Issue #30: Tutor Marketplace
- Issue #31: AI Email Communication Agent

### Security & Hardening (Codebase Analysis — Feb 2026)
- ~~Issue #139: Security: Fix authorization gaps in list_students, get_user, list_assignments~~ ✅
- ~~Issue #140: Add rate limiting to auth, AI generation, and file upload endpoints~~ ✅
- ~~Issue #141: Add security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options)~~ ✅
- Issue #142: Add input validation and field length limits across all endpoints
- ~~Issue #143: Add password reset flow (Forgot Password)~~ ✅
- ~~Issue #144: Fix N+1 query patterns in task list, child list, and reminder job~~ ✅ (fixed in #241)
- ~~Issue #145: Add CASCADE delete rules to FK relationships~~ ✅ (fixed in #187)
- ~~Issue #146: Add unique constraint on parent_students (parent_id, student_id)~~ ✅ (fixed in #187)
- ~~Issue #147: Add React ErrorBoundary for graceful error handling~~ ✅
- ~~Issue #148: Add global toast notification system for user feedback~~ ✅
- ~~Issue #149: Implement JWT token refresh mechanism~~ ✅
- ~~Issue #150: Add loading skeletons to replace text loading states~~ ✅
- ~~Issue #151: Accessibility audit: aria labels, keyboard nav, skip-to-content~~ ✅
- ~~Issue #152: Mobile responsive web: CSS breakpoints for 5+ pages~~ ✅
- ~~Issue #153: Fix FlashcardsPage stale closure bug in keyboard handler~~ ✅
- ~~Issue #154: Add frontend unit tests (vitest)~~ ✅ (258 frontend tests across 18 files)
- ~~Issue #155: Add backend route tests for google, study, messages, notifications, admin, invites~~ ✅
- Issue #156: Add PostgreSQL test environment to CI for cross-DB coverage

### Risk Audit (Full Application Review — Feb 2026)
- ~~Issue #176: CRITICAL: Fix admin self-registration and password validation~~ ✅
- ~~Issue #177: CRITICAL: Fix CORS wildcard and secure authentication tokens~~ ✅
- ~~Issue #178: CRITICAL: Secure Google OAuth flow~~ ✅
- ~~Issue #179: CRITICAL: Fix hardcoded JWT secret key~~ ✅
- ~~Issue #180: HIGH: Add JWT token revocation and rate limiting~~ ✅
- ~~Issue #181: HIGH: Fix RBAC gaps on students, assignments, courses, users, and content routes~~ ✅
- ~~Issue #182: HIGH: Secure logging endpoint and parent-created student passwords~~ ✅
- ~~Issue #184: MEDIUM: Fix LIKE pattern injection in search and study guide routes~~ ✅
- Issue #185: MEDIUM: Add database migration tooling (Alembic)
- ~~Issue #186: MEDIUM: Fix N+1 queries in messages, tasks, and parent routes~~ ✅ (fixed in #241)
- ~~Issue #187: MEDIUM: Add cascading deletes and unique constraints~~ ✅
- Issue #188: LOW: Replace deprecated dependencies (python-jose, PyPDF2, datetime.utcnow)
- ~~Issue #189: LOW: Add deployment pipeline tests and database backup strategy~~ ✅ (backup strategy in #354, CI test gating verified)
- Issue #190: LOW: Improve health check endpoint to verify database connectivity
- ~~Issue #191: LOW: Fix audit log silent failure and invite token reuse~~ ✅ (audit SAVEPOINT in #392, invite with_for_update in #392)

### Architecture & DDD Migration
- ~~Issue #127: Split api/client.ts into domain-specific API modules~~ ✅
- ~~Issue #128: Extract backend domain services from route handlers~~ ✅
- Issue #129: Introduce repository pattern for data access
- ~~Issue #130: Split ParentDashboard into sub-components~~ ✅ (AlertBanner, StudentDetailPanel, QuickActionsBar extracted in #540; useParentDashboard hook + TodaysFocusHeader extracted in #657; now 544 LOC)
- ~~Issue #131: Activate TanStack Query for server state management~~ ✅
- Issue #132: Reorganize backend into domain modules (DDD bounded contexts)
- Issue #133: Reorganize frontend into domain modules
- Issue #134: Add domain events for cross-context communication

### Infrastructure & DevOps
- ~~Issue #10: Pytest unit tests~~ ✅
- Issue #11: ~~GitHub Actions CI/CD~~ (CLOSED)
- ~~Issue #12: PostgreSQL + Alembic migrations~~ ✅
- Issue #13: ~~Deploy to GCP~~ (CLOSED)
- ~~Issue #14: Google OAuth verification~~ ✅
- ~~Issue #24: Register classbridge.ca domain~~ ✅
- ~~Issue #353: Infrastructure: Database Backup & Disaster Recovery for Production~~ ✅
- ~~Issue #2817: CI: Restrict security scanning to master-only pushes~~ ✅ (PR #2813)
- ~~Issue #2818: CI: Add path filters, concurrency, and daily run limit to GitHub Actions~~ ✅ (PR #2815)
- ~~Issue #2819: Repo: Make emai-dev-03 private~~ ✅

### Security & Hardening
- ~~Issue #63: Require SECRET_KEY and fail fast if missing~~ ✅ (fixed in #179)
- ~~Issue #64: Fix CORS configuration for credentials~~ ✅ (fixed in #177)
- ~~Issue #65: Protect frontend log ingestion endpoints~~ ✅
- ~~Issue #66: Introduce Alembic migrations and remove create_all on startup~~ ✅
- Issue #67: Prevent duplicate APScheduler jobs in multi-worker deployments
- Issue #68: Encrypt Google OAuth tokens at rest
- Issue #69: Revisit JWT storage strategy to reduce XSS risk

### UI & Theming
- ~~Issue #486: Flat (non-gradient) UI theme — replace gradients with solid colors (parent tracking)~~ ✅
- ~~Issue #487: Web: Replace all CSS gradient backgrounds with solid accent colors (13 CSS files)~~ ✅
- ~~Issue #488: Mobile: Remove gradient from login button and use solid theme colors~~ ✅
- Issue #489: Add gradient/flat style toggle to theme system (low priority)

### UX / Navigation
- ~~Issue #811: Replace header back button with unified PageNav component~~ ✅

### UI/UX HCD Assessment — Phase 2 Improvements (Epic #827)

**Tier 1 — Critical (Next 2 sprints):**
- ~~Issue #828: Unify design tokens (replace hard-coded CSS values with CSS variables)~~ ✅
- ~~Issue #829: Fix WCAG 2.1 AA accessibility gaps across all roles~~ ✅
- ~~Issue #830: Add explicit "All Children" tab and mobile scroll indicators in parent child selector~~ ✅
- ~~Issue #831: Standardize responsive breakpoints to 3 tiers (480/768/1024px)~~ ✅
- ~~Issue #832: Simplify parent dashboard with progressive disclosure for new users~~ ✅

**Tier 2 — Important (Next 4 sprints):**
- Issue #833: Teacher dashboard enhancement (SVG icons, dynamic counts, announcement preview)
- Issue #834: Student engagement (streak celebrations, spaced repetition, continue studying)
- ~~Issue #835: Standardize empty states with shared EmptyState component~~ ✅
- Issue #836: Add message search and communication improvements
- Issue #837: Unify quick action paradigm across Parent, Student, and Teacher roles

**Tier 3 — Backlog:**
- Issue #838: Grade integration: display grades from Google Classroom for parents and students
- Issue #839: Assignment submission: allow students to submit work through the platform

### Observability & Quality
- ~~Issue #70: Populate request.state.user_id for request logs~~ ✅
- ~~Issue #71: Add baseline test suite (auth, RBAC, core routes)~~ ✅
- Issue #72: Roll out new design system across remaining pages
- Issue #73: Add migration for new DB indexes
- ~~Issue #74: Add pagination for conversations/messages list~~ ✅
- Issue #75: Introduce lightweight caching for read-heavy endpoints
- Issue #76: Document local seed + load testing workflow
- Issue #77: Design system + perf + local testing tools

### Testing
- Issue #78: Manual test scenarios: backend API
- Issue #79: Manual test scenarios: frontend UX
- Issue #80: Add E2E smoke tests (Playwright or Cypress)

### Phase 1 - Bugs Fixed (Google Sync & OAuth)
- ~~Issue #428: Google OAuth Error 400: redirect_uri_mismatch on production~~ ✅
- ~~Issue #430: Google Classroom course materials not syncing to Course Content~~ ✅
- ~~Issue #431: Sync Google Classroom courseWorkMaterials to CourseContent~~ ✅
- ~~Issue #432: Assignment sync does not populate CourseContent for parent/student view~~ ✅
- ~~Issue #433: Student Google Classroom sync does not pull course materials or assignments~~ ✅
- ~~Issue #434: No automatic/background sync for Google Classroom updates~~ ✅
- ~~Issue #436: Google Sync returns 500 on parent sync-courses endpoint~~ ✅
- ~~Issue #631: Add Child Google Classroom flow repeats for every child~~ ✅
- ~~Issue #705: Google OAuth sign-in fails with 'Authentication failed'~~ ✅

### Phase 1 - Bugs Fixed (Parent Dashboard & Filtering)
- ~~Issue #276: Parent dashboard shows empty state - children disappeared after deploy~~ ✅
- ~~Issue #305: Parent dashboard stat cards not filtering by selected child~~ ✅
- ~~Issue #306: Course materials not filtering by selected child on parent dashboard~~ ✅
- ~~Issue #582: Reorder Parent Dashboard sections: Tasks first (collapsible), then Course Materials, then Courses~~ ✅
- ~~Issue #609: Add 'View Details' button to task detail modal on Parent Dashboard~~ ✅
- ~~Issue #682: TasksPage: add child selector pills like Dashboard, organize button layout~~ ✅
- ~~Issue #815: Parent Dashboard: Recent Activity not filtered by selected child~~ ✅
- ~~Issue #854: bug: Parent Dashboard '+' button shows misleading 'Add Child' label~~ ✅
- ~~Issue #861: bug: Duplicate 'Recent Activity' header on Parent Dashboard~~ ✅
- ~~Issue #865: bug: Duplicate 'Student Details' header on Parent Dashboard~~ ✅

### Phase 1 - Bugs Fixed (Course Materials & Content)
- ~~Issue #421: Second parent cannot see study guides created by first parent for shared child~~ ✅
- ~~Issue #423: Second parent cannot see tasks/study guides for shared child~~ ✅
- ~~Issue #426: Header padding too large + course material fails to load for second parent~~ ✅
- ~~Issue #522: Course material tile missing 'assign to course' option (regression)~~ ✅
- ~~Issue #525: Create Study Material modal has unstyled upload tabs and drop zone~~ ✅
- ~~Issue #533: My Kids page should show unassigned courses and materials in All Children view~~ ✅
- ~~Issue #537: DOCX image/screenshot OCR not extracting math formulas from embedded images~~ ✅
- ~~Issue #566: Course Materials and Courses pages stuck in loading skeleton~~ ✅
- ~~Issue #570: Unassigned material stays in list after being reassigned to a course~~ ✅
- ~~Issue #590: Course Materials student filter not filtering on backend~~ ✅
- ~~Issue #593: Course Materials section shows study guides instead of course materials and incorrect count when filtered~~ ✅
- ~~Issue #598: Quick actions bar: rename Study Material, remove Add Child/Course, restyle buttons~~ ✅
- ~~Issue #615: Add Replace Document button to course material detail page~~ ✅
- ~~Issue #617: Replace Document button not visible on content without existing file~~ ✅
- ~~Issue #618: Upload Document modal missing overlay and not properly centered~~ ✅
- ~~Issue #619: Download serves .txt instead of original document format (.docx)~~ ✅
- ~~Issue #620: Upload document should run in background with status indicator~~ ✅
- ~~Issue #622: Hide OCR-extracted text content for uploaded documents~~ ✅
- ~~Issue #684: MyKidsPage: Classes and Materials still show as tiles instead of list~~ ✅
- ~~Issue #685: CourseDetailPage: materials not clickable, panel width inconsistency~~ ✅
- ~~Issue #702: Course Material Detail: + button should be inside Original Document panel, not tab bar~~ ✅
- ~~Issue #704: Original Document tab shows blank - unable to load existing documents~~ ✅
- ~~Issue #706: Study guide generation buttons disabled for materials with description-only content~~ ✅
- ~~Issue #732: fix: flashcard keyboard navigation not implemented~~ ✅
- ~~Issue #733: fix: shuffle button resets flashcards instead of shuffling~~ ✅
- ~~Issue #750: Visual defects on CourseMaterialDetailPage after refactor~~ ✅
- ~~Issue #809: Course Materials page: alignment, child filters, search box, back button~~ ✅
- ~~Issue #817: Course material detail page: missing PageNav breadcrumb, header cut off~~ ✅
- ~~Issue #825: Material detail page missing icon buttons (edit, archive, delete)~~ ✅
- ~~Issue #842: Task creation from course materials should auto-link the course material~~ ✅
- ~~Issue #845: Archived count always shows (0) on Course Materials page~~ ✅
- ~~Issue #847: Convert Create Task to icon-only button on material detail page~~ ✅
- ~~Issue #856: Material detail page shows content_type instead of course name~~ ✅

### Phase 1 - Bugs Fixed (Navigation, Layout & Mobile)
- ~~Issue #240: UX: Silent API error failures across multiple pages~~ ✅
- ~~Issue #300: Logo shows white background in dark mode theme~~ ✅
- ~~Issue #302: Child card quick actions don't filter destination pages by student~~ ✅
- ~~Issue #303: My Kids page crashes with 'Something went wrong' when student_id param is present~~ ✅
- ~~Issue #304: Production error on /my-kids page with student_id parameter~~ ✅
- ~~Issue #419: Landing page: header logo too small and excessive hero padding~~ ✅
- ~~Issue #422: Landing page: header logo too small, doesn't fill nav bar height~~ ✅
- ~~Issue #447: Landing page mobile view: oversized logo, nav, and hero elements~~ ✅
- ~~Issue #484: Mobile app: Use ClassBridge logo and match web theme on login screen~~ ✅
- ~~Issue #560: Icon inconsistency between sidebar and dashboard quick actions~~ ✅
- ~~Issue #568: My Kids page: duplicated child CTAs (tabs + cards)~~ ✅
- ~~Issue #633: My Kids page missing Add Child and Add Course action buttons~~ ✅
- ~~Issue #640: StudyGuidesPage: + Create button misaligned from filters~~ ✅
- ~~Issue #642: TasksPage: + New Task button misaligned from header~~ ✅
- ~~Issue #674: Messaging page missing sidebar nav and logo~~ ✅
- ~~Issue #679: Course page: missing back nav, delete course, button icons, inconsistent panels~~ ✅
- ~~Issue #680: Tasks page: replace dropdown filters with chip buttons, consistent New Task button~~ ✅
- ~~Issue #681: CoursesPage: convert tile grid to clickable list with edit/delete per item~~ ✅
- ~~Issue #683: Child selector state lost on page refresh across all pages~~ ✅
- ~~Issue #753: Flash of 'Welcome Rohini' when navigating between pages~~ ✅
- ~~Issue #808: Mobile responsive defects: content cutoff, checkbox styling, header overflow~~ ✅

### Phase 1 - Bugs Fixed (Production, CI & Auth)
- ~~Issue #863: fix: ESLint react-refresh rule blocks CI deploy~~ ✅
- ~~Issue #866: bug: password reset takes too long / hangs on 'Resetting...'~~ ✅

### Phase 1 - Bugs Fixed (Other)
- ~~Issue #266: Admin broadcast emails render HTML as plain text~~ ✅
- ~~Issue #267: Edit Child modal missing address and profile detail fields~~ ✅
- ~~Issue #268: Pending invites still shown after student has accepted and linked~~ ✅
- ~~Issue #299: Edit Child modal: missing email field + optional fields not collapsible~~ ✅
- ~~Issue #393: Commit: Frontend bug fix and unit tests (#153, #154)~~ ✅
- ~~Issue #416: Registration shows generic error instead of actual failure reason~~ ✅
- ~~Issue #498: Parent cannot see children details~~ ✅
- ~~Issue #562: All Children Overview panel: chevron doesn't rotate and size inconsistent with calendar~~ ✅
- ~~Issue #563: Today's Focus task notification labels are not clickable~~ ✅
- ~~Issue #584: Student filter not working across the application~~ ✅
- ~~Issue #595: View Task link in reminder emails has missing domain~~ ✅
- ~~Issue #599: Inspirational message not hidden when Today's Focus is closed~~ ✅
- ~~Issue #616: Default theme should be light, not auto-detect dark from OS~~ ✅
- ~~Issue #634: Unicode escape renders as literal text in StudentDetailPanel~~ ✅
- ~~Issue #637: Student cards still show 'courses' instead of 'classes'~~ ✅
- ~~Issue #687: Tasks: show edit icon on hover, consolidate edit/delete into modal~~ ✅
- ~~Issue #689: fix: align Tasks filter panel rows vertically~~ ✅
- ~~Issue #841: AI auto-task creation extracts historical dates from article content as due dates~~ ✅
- ~~Issue #858: bug: Calendar default view should be 3-Day, not Week~~ ✅

### Phase 1 - Open (AI Help Chatbot — §6.59, #1355-#1363)
- Issue #1355: Epic: AI Help Chatbot — RAG-Powered In-App Assistant (§6.59)
- Issue #1356: Help Chatbot: Knowledge base YAML files — FAQ, features, videos, pages (§6.59.1)
- Issue #1357: Help Chatbot: Embedding service + in-memory vector store (§6.59.2)
- Issue #1358: Help Chatbot: RAG chat service + system prompt (§6.59.3)
- Issue #1359: Help Chatbot: API endpoint POST /api/help/chat (§6.59.4)
- Issue #1360: Help Chatbot: Frontend widget — FAB, chat panel, message bubbles (§6.59.5)
- Issue #1361: Help Chatbot: Video embed component — YouTube + Loom inline players (§6.59.6)
- Issue #1362: Help Chatbot: Backend + frontend tests (§6.59.7)
- Issue #1363: Help Chatbot: NotesFAB z-index coordination + mobile bottom sheet (§6.59.8)
- Issue #1630: Help Chatbot: Global Search integration — search across platform data (§6.59.9) *(supersedes #1410)*
- ~~Issue #2106: feat: comprehensive help/FAQ/chatbot update — 15 missing feature topics~~ ✅

### Phase 1 - Features Built (Image Retention & Resource Links — Mar 7, 2026)
- ~~Issue #1308: feat: ContentImage model and database migration for image retention~~ ✅
- ~~Issue #1309: feat: extract and store images during document upload~~ ✅
- ~~Issue #1310: feat: include image metadata in AI study guide prompt~~ ✅
- ~~Issue #1311: feat: image serving endpoint for study guide images~~ ✅
- ~~Issue #1312: feat: render images inline in study guide frontend~~ ✅
- ~~Issue #1313: feat: fallback 'Additional Figures' section for unplaced images~~ ✅
- ~~Issue #1319: feat: resource_links model + migration (§6.57)~~ ✅
- ~~Issue #1320: feat: link_extraction_service — URL extraction + YouTube enrichment (§6.57)~~ ✅
- ~~Issue #1321: feat: integrate link extraction into upload + teacher comm sync (§6.57)~~ ✅
- ~~Issue #1322: feat: CRUD API endpoints for resource links (§6.57)~~ ✅
- ~~Issue #1323: feat: Videos & Links tab on CourseMaterialDetailPage (§6.57)~~ ✅
- ~~Issue #1325: feat: YouTube embed component + topic grouping UI (§6.57)~~ ✅
- ~~Issue #1326: test: link extraction service + resource links API tests (§6.57)~~ ✅

### Phase 1 - Bug Fixes (Mar 7, 2026)
- ~~Issue #1295: My Kids page shows raw 'OverdueTask' enum value instead of formatted label~~ ✅
- ~~Issue #1297: No background progress indicator for upload-only (image) uploads~~ ✅
- ~~Issue #1299: Upload wizard lacks clear paste/screenshot guidance~~ ✅
- ~~Issue #1301: bug: task urgency pills missing from Today's Focus header~~ ✅
- ~~Issue #1304: Task urgency pills and hero text broken due to date parsing bug~~ ✅
- ~~Issue #1306: fix: CoursesPage child selector missing All icon, color dots, and + context menu~~ ✅
- ~~Issue #1314: fix: 'Failed to download document' on course-materials document tab~~ ✅
- ~~Issue #1337: fix: YouTube embeds show broken placeholders — CSP missing frame-src (§6.57)~~ ✅

### Phase 1 - Features Built (UX & UI Polish)
- ~~Issue #239: UX: Add confirmation dialogs to destructive actions missing them~~ ✅
- ~~Issue #245: UX: Inconsistent component patterns across pages (child selector, buttons, empty states)~~ ✅
- ~~Issue #249: Tech debt: Close stale issues and update REQUIREMENTS.md status markers~~ ✅
- ~~Issue #605: Course Material Detail: Header card redesign & button upgrades~~ ✅
- ~~Issue #608: Course Material Detail: Integration & responsive polish~~ ✅
- ~~Issue #635: Rename 'Course' to 'Class' across all UI labels~~ ✅
- ~~Issue #672: UI Polish: Personal hero headline with overdue task counts~~ ✅
- ~~Issue #738: Parent Dashboard: Add skeleton loading states for dashboard sections~~ ✅
- ~~Issue #739: Parent Dashboard: Improve + button affordance with tooltip~~ ✅
- ~~Issue #740: Parent Dashboard: Auto-expand Student Detail panel when child selected~~ ✅
- ~~Issue #766: ux: remove redundant ChildComparisonCards on parent dashboard~~ ✅
- ~~Issue #819: Expand Class Materials search to also search course/material content~~ ✅

### Phase 1 - Features Built (Backend & Notifications)
- ~~Issue #214: Add email + in-app notification dispatch when a message is sent~~ ✅
- ~~Issue #215: Create message notification email template~~ ✅
- ~~Issue #216: Add dedup logic to prevent email spam on rapid-fire messages~~ ✅
- ~~Issue #244: Performance: Add missing database indexes for frequent queries~~ ✅
- ~~Issue #254: Send email notification when teacher enrolls existing student in course~~ ✅
- ~~Issue #417: Email verification for registration (soft gate)~~ ✅

### Phase 1 - Features Built (Testing)
- ~~Issue #217: Add tests for message email notifications~~ ✅
- ~~Issue #269: UI Tests: Test utilities & mock factories~~ ✅
- ~~Issue #270: UI Tests: AuthContext + LoginPage + RegisterPage~~ ✅
- ~~Issue #271: UI Tests: NotificationBell component~~ ✅
- ~~Issue #272: UI Tests: MessagesPage~~ ✅
- ~~Issue #274: UI Tests: TeacherDashboard + AdminDashboard + Dashboard dispatcher~~ ✅
- ~~Issue #275: UI Tests: ParentDashboard + StudentDashboard (full coverage)~~ ✅
- ~~Issue #490: Set up mobile testing framework (Jest + React Native Testing Library)~~ ✅
- ~~Issue #491: Add unit tests for mobile LoginScreen~~ ✅
- ~~Issue #492: Add unit tests for mobile dashboard screens (ParentDashboard, ChildOverview, Calendar)~~ ✅
- ~~Issue #493: Add unit tests for mobile messaging screens (MessagesList, Chat)~~ ✅
- ~~Issue #494: Add unit tests for mobile Notifications, Profile, and Placeholder screens~~ ✅
- ~~Issue #742: Parent Dashboard: Mobile responsiveness testing and fixes~~ ✅

### Phase 1 - Features Built (Mobile)
- ~~Issue #248: UX: Mobile responsiveness gaps in 5+ CSS files~~ ✅
- ~~Issue #338: Mobile: Implement Loading Skeletons~~ ✅
- ~~Issue #356: Mobile Development: Skill Guide & Quick Reference Created~~ ✅

### Phase 1 - Features Built (Other)
- ~~Issue #81: Manual Course Enrollment (Student self-enroll)~~ ✅
- ~~Issue #238: Notify parent when teacher adds their child to a course~~ ✅
- ~~Issue #253: Resend/re-invite: allow teachers and parents to resend pending invites~~ ✅
- ~~Issue #424: Web: Add Lottie animation loader for AI study material generation~~ ✅
- ~~Issue #445: Add static Help/Getting Started page (Phase 1 FAQ)~~ ✅
- ~~Issue #448: Prep: Create feature/phase-2 branch for Phase 2 development~~ ✅
- ~~Issue #450: Sync emai-class-bridge repo with emai-dev-03 master~~ ✅
- ~~Issue #580: Add focus prompt to CourseMaterialDetailPage inline generation~~ ✅
- ~~Issue #606: Course Material Detail: Pill-style tabs & focus prompt relocation~~ ✅
- ~~Issue #607: Course Material Detail: Content formatting, typography & OCR handling~~ ✅
- ~~Issue #675: Enhanced password management: OAuth user reset + parent child password control~~ ✅
- ~~Issue #741: Parent Dashboard: Add context preview to collapsed Activity Feed~~ ✅
- ~~Issue #759: Evaluate cost-efficient hosting alternatives to GCP~~ ✅

### March 6 Pilot - Additional Completed Tasks
- ~~Issue #381: Custom Domain: Complete SSL provisioning for all domains~~ ✅
- ~~Issue #382: Google OAuth: Update consent screen for custom domain~~ ✅
- ~~Issue #383: Google OAuth: Add pilot test users~~ ✅
- ~~Issue #390: Publish Expo Go project for mobile pilot distribution~~ ✅
- ~~Issue #394: Commit: Mobile MVP app (ClassBridgeMobile/)~~ ✅
- ~~Issue #403: GoDaddy: Remove parked A records blocking SSL provisioning~~ ✅
- ~~Issue #404: Add missing A records for clazzbridge.com in GoDaddy~~ ✅
- ~~Issue #405: Configure domain redirect: clazzbridge.com to classbridge.ca~~ ✅
- ~~Issue #455: Pilot prep: Run enhanced smoke test against production~~ ✅
- ~~Issue #456: Create Expo account and Apple Developer Program enrollment~~ ✅
- ~~Issue #515: Security: Disable Swagger/OpenAPI docs in production~~ ✅
- ~~Issue #516: Performance: Add GZip compression middleware~~ ✅
- ~~Issue #585: Create Privacy Policy page at /privacy~~ ✅
- ~~Issue #586: Create Terms of Service page at /terms~~ ✅
- ~~Issue #588: Decide: Keep or drop gmail.readonly scope for OAuth verification~~ ✅
- ~~Issue #726: Rename Google OAuth consent screen from EMAI to ClassBridge~~ ✅
- ~~Issue #727: Implement incremental OAuth scopes (drop gmail.readonly from initial consent)~~ ✅

### UX Audit - Additional Completed Items
- ~~Issue #277: Teacher: Add class-wide announcement/broadcast feature~~ ✅
- ~~Issue #278: Mobile: Fix split-pane layout for Messages and Teacher Comms~~ ✅
- ~~Issue #279: Student: Add mobile breakpoint to Study Guide page~~ ✅
- ~~Issue #280: Accessibility: Add focus traps, ARIA roles, and screen reader support to modals~~ ✅
- ~~Issue #281: Accessibility: Add text/icon labels alongside color-only status indicators~~ ✅
- ~~Issue #282: Parent: Auto-send invite email when creating/linking a child~~ ✅
- ~~Issue #283: Student: Add visual progress bar to quiz experience~~ ✅
- ~~Issue #284: Teacher: Enable email reply in Teacher Communications~~ ✅
- ~~Issue #285: Parent: Add touch support for calendar drag-and-drop task rescheduling~~ ✅
- ~~Issue #286: Parent: Consolidate teacher linking and messaging into unified flow~~ ✅
- ~~Issue #287: All roles: Add first-time onboarding tooltip tour~~ ✅
- ~~Issue #288: All roles: Add loading spinners during AI generation operations~~ ✅
- ~~Issue #289: Student: Add gamification elements (streaks, badges, progress tracking)~~ ✅
- ~~Issue #290: Teacher: Add course search/filter for managing many courses~~ ✅
- ~~Issue #291: Parent: Clarify Dashboard vs My Kids page purpose and navigation~~ ✅
- ~~Issue #292: Student: Add spaced repetition and 'mark for review' to flashcards~~ ✅
- ~~Issue #293: All roles: Replace browser confirm() with styled ConfirmModal everywhere~~ ✅
- ~~Issue #295: All roles: Add keyboard shortcuts legend (? key)~~ ✅
- ~~Issue #298: Student: Remove or replace non-functional Average Grade dashboard card~~ ✅

### Other Completed (Misc)
- ~~Issue #120: Bug: Task status dropdown filters are not working~~ ✅
- ~~Issue #121: Calendar: Enable editing task due date via drag-and-drop~~ ✅
- ~~Issue #122: Recurring Tasks: Feasibility + implementation proposal~~ ✅
- ~~Issue #196: Replace course content list text buttons with icon buttons~~ ✅
- ~~Issue #197: Add Create Task button to all detail views~~ ✅
- ~~Issue #220: Backend: Create student_teachers join table~~ ✅
- ~~Issue #221: Backend: Add endpoint to link teacher to child~~ ✅
- ~~Issue #222: Backend: Update message recipients to include directly-linked teachers~~ ✅
- ~~Issue #223: Frontend: Add 'Link Teacher' UI to parent dashboard~~ ✅
- ~~Issue #228: Role-based inspirational messages on dashboard~~ ✅
- ~~Issue #229: Admin dashboard: manage inspirational messages~~ ✅
- ~~Issue #231: Inspiration messages: file-based seed data (parent, teacher, student)~~ ✅
- ~~Issue #232: Inspiration messages: frontend dashboard integration~~ ✅
- ~~Issue #307: Fix ESLint errors before re-enabling CI lint check~~ ✅
- ~~Issue #310: Implement API Versioning (v1)~~ ✅
- ~~Issue #324: Mobile: Implement Authentication Flow (Login/Register)~~ ✅
- ~~Issue #325: Mobile: Implement Dashboard Screen (Role-Based)~~ ✅
- ~~Issue #326: Mobile: Implement Courses Screen with Pagination~~ ✅
- ~~Issue #330: Mobile: Implement Messages/Chat Screen~~ ✅
- ~~Issue #331: Mobile: Implement Notifications Screen~~ ✅
- ~~Issue #332: Mobile: Implement User Profile & Settings Screen~~ ✅
- ~~Issue #348: Documentation: Create Mobile Development Onboarding Guide~~ ✅
- ~~Issue #384: Google OAuth: Publish app to production (post-pilot)~~ ✅
- ~~Issue #391: Cleanup: Delete junk and duplicate files from working directory~~ ✅
- ~~Issue #395: Commit: Infrastructure, monitoring, docs, and seed data~~ ✅
- ~~Issue #517: Bug: Invalid /api/* paths return SPA HTML instead of JSON 404~~ ✅
- ~~Issue #558: Parent dashboard: remove Student Details, add task detail modal, fix child filter for tasks~~ ✅
- ~~Issue #625: Remove duplicate overdue notification banner from parent dashboard~~ ✅
- ~~Issue #626: Reorder parent sidebar navigation~~ ✅
- ~~Issue #628: Remove Courses section from parent dashboard~~ ✅
- ~~Issue #638: Standardize UI: + icons on add/create buttons & collapsible sections~~ ✅
- ~~Issue #644: Remove 'All Children' button and add toggle-to-deselect on child filter buttons~~ ✅
- ~~Issue #676: Improve dark theme color palette for better contrast and visibility~~ ✅
- ~~Issue #823: feat: soft delete (archive) course materials + button icon improvements~~ ✅

### VASP/DTAP Compliance - Ontario School Board Approval (Open)
- Issue #779: VASP Compliance: Migrate infrastructure to GCP Canada region (northamerica-northeast2)
- Issue #780: VASP Compliance: Address OpenAI API data residency (US data transfer risk)
- Issue #781: VASP Compliance: Update Privacy Policy & ToS for MFIPPA/PIPEDA compliance
- Issue #782: VASP Compliance: Create Privacy Impact Assessment (PIA) document
- Issue #783: VASP Compliance: Implement age-based consent mechanism (MFIPPA)
- Issue #784: VASP Compliance: Implement MFA/2FA support
- Issue #785: VASP Compliance: Implement SSO/SAML support for school board integration
- Issue #786: VASP Compliance: WCAG 2.1 AA accessibility audit and remediation
- Issue #787: VASP Compliance: Implement data export and right to erasure
- Issue #788: VASP Compliance: Move JWT to httpOnly cookies (XSS mitigation)
- Issue #789: VASP Compliance: Add dependency vulnerability scanning to CI/CD
- Issue #790: VASP Compliance: Establish annual penetration testing program
- Issue #791: VASP Compliance: Begin SOC 2 Type II readiness assessment
- Issue #792: VASP Compliance: Obtain cyber liability insurance
- Issue #793: VASP Compliance: Create Data Processing Agreement (DPA) template for school boards
- Issue #794: VASP Compliance: Implement formal breach notification procedures
- Issue #795: VASP Compliance: Complete K-12CVAT vendor questionnaire
- Issue #796: VASP Compliance: Implement account lockout and enhanced brute-force protection
- Issue #797: VASP Compliance: Implement consent management and cookie disclosure
- Issue #798: VASP Compliance: Implement formal data retention and automated purging
- Issue #799: VASP Compliance: Designate privacy officer and establish privacy program
- Issue #800: VASP Compliance: Enhance audit logging for SOC 2 and VASP requirements
- Issue #801: VASP Compliance: Evaluate D2L Brightspace integration (Ontario VLE)
- Issue #802: VASP Compliance: Identify and engage pilot school board partner
- Issue #803: EPIC: DTAP Compliance - Ontario School Board Digital Technology Approval Process
- Issue #804: VASP Compliance: Add WAF/DDoS protection (Cloud Armor)
- Issue #805: VASP Compliance: Add SAST/DAST security scanning to CI/CD
- Issue #806: VASP Compliance: Create formal data classification and inventory
- Issue #807: VASP Compliance: Implement comprehensive API rate limiting

### Railway Migration (CLOSED — Abandoned)
- Issue #769: ~~Add Railway URL to Google OAuth Console~~ (CLOSED)
- Issue #770: ~~Update CI/CD pipeline from GCP Cloud Run to Railway~~ (CLOSED)
- Issue #771: ~~Test core features on Railway deployment~~ (CLOSED)
- Issue #772: ~~Custom domain cutover: point clazzbridge.com to Railway~~ (CLOSED)
- Issue #773: ~~Decommission GCP Cloud Run and Cloud SQL~~ (CLOSED)
- Issue #774: ~~Clean up Railway migration temp files (security)~~ (CLOSED)
- Issue #971: ~~Railway dashboard config~~ (CLOSED — migration abandoned, project remains on GCP Cloud Run)

### LMS Abstraction & D2L Brightspace Integration (Partial)
- Issue #768: ~~Research: Brightspace (D2L) API integration~~ (CLOSED)
- Issue #775: ~~Arch: LMS abstraction layer — Adapter Pattern + OneRoster canonical models~~ (CLOSED)
- Issue #776: ~~Refactor: Extract Google Classroom sync into LMSProvider adapter~~ (CLOSED)
- Issue #777: D2L Integration Partner registration & Brightspace sandbox setup (OPEN)
- Issue #778: Feature: Brightspace integration MVP — courses, assignments, grades sync (OPEN)

### Mobile App Distribution & Testing (Partial)
- Issue #327: Mobile: Implement Course Detail Screen (OPEN)
- Issue #328: Mobile: Implement Assignments Screen (OPEN)
- Issue #329: Mobile: Implement Assignment Detail Screen (OPEN)
- Issue #336: Mobile: Implement Offline Mode with Data Caching (OPEN)
- Issue #339: Mobile: Write Mobile App Tests (OPEN)
- Issue #342: Deployment: Beta Testing with TestFlight (iOS) (OPEN)
- Issue #425: Mobile: Add Lottie animation loader (post-pilot) (OPEN)
- Issue #457: ~~Build and distribute ClassBridge mobile app via EAS Build~~ (CLOSED)
- Issue #460: ~~Link EAS project and update app.json placeholders~~ (CLOSED)
- Issue #461: ~~Register iOS pilot devices for ad hoc distribution~~ (CLOSED)
- Issue #462: ~~Update pilot docs with real download links after EAS Build~~ (CLOSED)
- Issue #477: ~~Android: Build APK and test on devices~~ (CLOSED)
- Issue #478: ~~iOS: Build IPA and distribute via TestFlight~~ (CLOSED)
- Issue #482: ~~Publish Android app to Google Play Store~~ (CLOSED)
- Issue #483: ~~Publish iOS app to Apple App Store~~ (CLOSED)

### UI/UX Polish (Partial)
- Issue #198: UI Layout Redesign: turbo.ai-inspired navigation and content structure (OPEN — partially addressed by §6.65 dashboard redesign)
- Issue #199: UI Layout: Glassmorphism card design and improved dashboard cards (OPEN — backlog)
- Issue #200: UI Layout: Improved information hierarchy and content density (OPEN — partially addressed)
- Issue #264: Create reusable UI testing package from ClassBridge test infrastructure (OPEN)
- Issue #669: ~~UI Polish: Mute teal saturation on active sidebar nav items~~ (CLOSED)
- Issue #670: ~~UI Polish: Hide motivational quote on mobile~~ (CLOSED)
- Issue #671: ~~UI Polish: Add small labels below sidebar icons~~ (CLOSED)
- Issue #678: Add multiple dark theme options for user selection (OPEN — Phase 2)
- Issue #734: ~~ui: redesign Course Material Detail page layout and polish~~ (CLOSED)

### Performance & Scalability (Partial)
- Issue #242: Performance: Add pagination to unbounded list endpoints (OPEN)
- Issue #243: Performance: Move synchronous email sending to background jobs (OPEN)
- Issue #294: Teacher: Batch student invites via CSV upload or email list (OPEN)
- Issue #757: ~~Set up support email for OAuth consent screen~~ (CLOSED)

### Business & Marketing (Open)
- Issue #761: Marketing strategy & monetization plan for 100K users
- Issue #762: Competitive analysis & market positioning

### Other Issues (Updated Mar 14, 2026)
- Issue #296: Teacher: Add course content reordering (drag-to-reorder) (OPEN)
- Issue #297: Teacher: Add draft/publish visibility controls for course content (OPEN)
- Issue #407: ~~Clean up old Cloud Run URL from Google OAuth console~~ (CLOSED)
- Issue #476: ~~Re-enable Analytics nav link in Phase 2~~ (CLOSED)
- Issue #479: ~~Re-enable FAQ nav link in Phase 2~~ (CLOSED)
- Issue #485: ~~Phase 1 (MVP) Delivery Plan - ClassBridge Launch Readiness~~ (CLOSED)
- Issue #579: Optimize multi-material generation: single API call vs parallel (OPEN)
- Issue #587: ~~Record Google OAuth demo video for scope verification~~ (CLOSED)
- Issue #589: ~~Submit Google OAuth app for production verification~~ (CLOSED)
- Issue #623: ~~Tag unlinked course materials and streamline parent-to-child assignment~~ (CLOSED)
- Issue #735: ~~refactor: break CourseMaterialDetailPage into sub-components~~ (CLOSED)
- Issue #736: ~~ux: improve focus prompt behavior across tabs~~ (CLOSED)

### Chatbot & Search (§6.59) — Partially Open
- Issue #1698: feat: deprecate GlobalSearch — remove in favour of chatbot unified search
- Issue #1716: fix: View button navigates to wrong ID after study material generation
- ~~Issue #1719: fix: search_service uses raw message as ILIKE term — strip action words before search~~ ✅
- Issue #1720: feat: handle 'list all entity' queries — return nav card or all entities
- ~~Issue #1722: fix: chatbot 'show tasks for [name]' returns no results~~ ✅
- ~~Issue #1734: fix: chatbot search scope narrower than global search for parents~~ ✅
- Issue #1744: research: LLM-based intent classification — cost/benefit analysis
- ~~Issue #1778: fix: add TOPIC_KEYWORDS to intent classifier and suggestion chips on no-results~~ ✅
- ~~Issue #1779: content: expand help knowledge base FAQ coverage for missing features~~ ✅

### WOW Features & Parent UX (Open)
- Issue #1403: Epic: Smart Daily Briefing — Proactive Parent Intelligence (§6.61)
- Issue #1405: Frontend: daily briefing card on parent dashboard (§6.61.2)
- Issue #1407: Epic: Help My Kid — One-Tap Study Actions (§6.62)
- Issue #1429: Dev Plan: WOW Features — Parallel Development Strategy
- Issue #1430: Product Strategy: Two Layers — Infrastructure vs Intelligence
- Issue #1431: Epic: Smart Data Import — Parent-Powered School Data (§6.67)
- Issue #1432: Photo Capture: Snap assignment/report card → auto-import (§6.67.1)
- Issue #1433: Email Forwarding: Forward school emails → auto-parse assignments (§6.67.2)
- Issue #1435: Decision: No Perplexity Integration — AI Strategy Note
- Issue #1436: Epic: "Learn Your Way" — Interest-Based Personalized Learning (§6.69)
- Issue #1441: feat: Learn Your Way freemium paywall design

### Digital Wallet & Subscription System (§6.60) — Partially Implemented (PR #1854)
- Issue #1384: Epic: Digital Wallet & Subscription System (§6.60)
- ~~Issue #1385: Stripe integration (§6.60.1) — CLOSED, implemented PR #1854~~
- Issue #1386: Subscription plans: Stripe Checkout for recurring billing (§6.60.2) — PackageTier done, recurring NOT done
- ~~Issue #1387: Digital wallet: dual credit pools (§6.60.3) — CLOSED, implemented PR #1854~~
- Issue #1388: One-time credit purchase: ConfirmModal "Buy More" integration (§6.60.4) — checkout done, bridge NOT done
- Issue #1389: Subscription frontend: pricing page, billing settings, tier badge (§6.60.5) — WalletPage done, rest NOT done
- Issue #1390: Invoice module: generate, send, and track invoices (§6.60.6)
- Issue #1391: Admin subscription management: user tier control, revenue dashboard (§6.60.7)
- ~~Issue #1392: Payments backend tests (§6.60.8) — CLOSED, implemented PR #1854~~
- Issue #1851: Interac e-Transfer: manual-assisted payment flow for Canadian users (§6.60.9)
- Issue #1859: fix: UTF-8 arrow character in wallet transaction notes
- Issue #1860: feat: admin wallet management — view wallets, grant credits, override tiers
- Issue #1861: feat: integrate CreditTopUpModal into insufficient credits (402) flow
- Issue #1862: feat: wallet link in sidebar + tier badge in header

### MCP Protocol Integration (Phase 2) — Open
- Issue #903: EPIC: MCP Protocol Integration — AI-Powered Contextual Learning
- Issue #906: Student Academic Context MCP resources and tools
- Issue #907: Google Classroom MCP tools
- Issue #908: Study Material Generation MCP tools
- Issue #909: AI Tutor Agent — contextual study plan generation via MCP
- Issue #910: Teacher Communication MCP tools
- Issue #911: MCP Client — external educational resource discovery
- Issue #912: MCP integration tests and Claude Desktop configuration

### DTAP / VASP Compliance (Phase 2) — Open
- Issue #779: VASP: Migrate infrastructure to GCP Canada region
- Issue #780: VASP: Address OpenAI API data residency (US data transfer risk)
- Issue #781: VASP: Update Privacy Policy & ToS for MFIPPA/PIPEDA compliance
- Issue #782: VASP: Create Privacy Impact Assessment (PIA)
- Issue #784: VASP: Implement MFA/2FA support
- Issue #785: VASP: Implement SSO/SAML for school board integration
- Issue #787: VASP: Implement data export and right to erasure
- Issue #789: VASP: Add dependency vulnerability scanning to CI/CD
- Issue #790: VASP: Establish annual penetration testing program
- Issue #791: VASP: Begin SOC 2 Type II readiness assessment
- Issue #792: VASP: Obtain cyber liability insurance
- Issue #793: VASP: Create DPA template for school boards
- Issue #794: VASP: Implement formal breach notification procedures
- Issue #795: VASP: Complete K-12CVAT vendor questionnaire
- Issue #798: VASP: Implement formal data retention and automated purging
- Issue #799: VASP: Designate privacy officer and establish privacy program
- Issue #800: VASP: Enhance audit logging for SOC 2 and VASP requirements
- Issue #802: VASP: Identify and engage pilot school board partner
- Issue #803: EPIC: DTAP Compliance — Ontario School Board Digital Technology Approval Process
- Issue #804: VASP: Add WAF/DDoS protection (Cloud Armor)
- Issue #806: VASP: Create formal data classification and inventory

### Phase 2 — Other Features (Open)
- Issue #513: Admin: View and edit email templates from dashboard
- Issue #514: Admin: Broadcast email history with reuse and resend
- Issue #572: Course Materials Storage Strategy (partially done — GCS migration complete)
- Issue #573: Study Guide Repository — cross-student reuse and content-matching dedup
- Issue #578: User-Provided AI API Key (BYOK)
- Issue #665: Phase 2: Teacher grade & feedback entry per student per term
- Issue #666: Phase 2: Unified teacher material upload with type classification
- Issue #664: Phase 2: Parent-assigned quizzes with complexity levels
- Issue #882: Bulk child import via CSV
- Issue #884: Study material version history
- Issue #993: Multi-document support per course material
- Issue #1090: Epic: Contextual Notes System — Note-taking on Course Materials (§6.7)
- Issue #1209: feat: Replace tutorial SVG placeholders with real screenshots
- Issue #1594: feat: hierarchical study guides — generate child study guides from parent topics
- Issue #2597: **EPIC** — expand Help page with User Journey Guide & role-based diagrams (§6.125)
  - Issue #2599: add journey diagram SVG/PNG assets to frontend (§6.125.4)
  - Issue #2600: User Journeys tab in Help Center with role-based organization (§6.125.1-2)
  - Issue #2601: Ask the Bot button on journey cards with pre-filled context (§6.125.3)
  - Issue #2602: index journey content in Help KB YAML for search and chatbot RAG (§6.125.5)
  - Issue #2603: cross-link Tutorial page steps to Help journey articles (§6.125.6)
- Issue #2598: **EPIC** — proactive journey hints — smart first-login popups & contextual guidance (§6.126)
  - Issue #2604: journey_hints DB table, model, and migration (§6.126.5)
  - Issue #2605: journey hint detection service — state-based hint logic (§6.126.3-4)
  - Issue #2606: journey hints API endpoints — get, dismiss, snooze, suppress (§6.126.5-7)
  - Issue #2607: first-login welcome modal with role-tailored journey steps (§6.126.1-2)
  - Issue #2608: contextual journey nudge banner component (§6.126.9-10)
  - Issue #2609: behavior signal detection — auto-dismiss, cooldown, nuclear suppress (§6.126.7-8)
  - Issue #2610: optional Getting Started progress widget on dashboard (§6.126.13)
- Issue #1740: feat: master/sub class material hierarchy for multi-document uploads (§6.95)
- ~~Issue #2087: User Bug Report with Screenshot → GitHub Issue + Admin Notification (§6.115)~~ ✅
- ~~Issue #2089: Error Dialog → Report Bug Link (§6.116)~~ ✅
- ~~Issue #2103: Bug Report Bot Protection (§6.117)~~ ✅

### CB-UTDF-001 — Unified Template + Detection Framework (Phase 2) — DEPLOYED (2026-04-11)

**Epic:** Unified Template + Detection Framework for Study Guide & Worksheet Generation
**PRD:** [docs/CB-UTDF-001-PRD-v1.md](../docs/CB-UTDF-001-PRD-v1.md)
**Section:** §6.131 | **Deployed:** April 11, 2026 | **Stories:** 13 (all complete)

- [x] **Epic** — [Epic] CB-UTDF-001: Unified Template + Detection Framework (#2948)
- [x] [CB-UTDF-S1] Extend document classification: add subject + confidence (#2949)
- [x] [CB-UTDF-S2] DB migration: new columns on course_content + study_guides (#2950)
- [x] [CB-UTDF-S3] Template key resolver + High Level Summary variant (#2951)
- [x] [CB-UTDF-S4] ClassificationBar component + teacher auto-assignment (#2952)
- [x] [CB-UTDF-S5] ChildDisambiguationModal — multi-child selector (#2953)
- [x] [CB-UTDF-S6] MaterialTypeSuggestionChips — type-driven chip sets (#2954)
- [x] [CB-UTDF-S7] ClassificationOverridePanel + PATCH endpoint (#2955)
- [x] [CB-UTDF-S8] Worksheet generation: POST endpoint + viewer (#2956)
- [x] [CB-UTDF-S9] Answer key generation endpoint (#2957)
- [x] [CB-UTDF-S10] Weak area analysis: Claude Sonnet endpoint + viewer (#2958)
- [x] [CB-UTDF-S13] CourseDetailPage: add Worksheets tab (#2959)
- [x] [CB-UTDF-S14] Mobile (Expo): ClassificationBar + chips (#2960)
- [x] [CB-UTDF-S15] Tests: classifier unit, integration, E2E (#2961)

**PRs:** #3068 (main implementation), #3085 (post-deployment fixes), #3091 (PR review fixes)
**Deployment incident:** pg_advisory_lock deadlock → fixed with pg_try_advisory_lock
**Post-deploy fixes:** #3070–#3078, #3079–#3083, #3085, #3091
**Defect (2026-04-12):** #3173 — `generate_worksheet_endpoint` truncated during merge (500 on generate), #3174 — `analyze_weak_areas` using wrong variables from same botched merge. Fixed in #3175.

### CB-PCM-001 — Admin Customer Database: CRM, Branded Email & Messaging — DEPLOYED (2026-04-12)

**Epic:** #2974 — Admin Customer Database
**Section:** §6.132 | **Deployed:** April 12, 2026 | **Stories:** 8 (all complete)
**Data model:** 4 new tables: parent_contacts, parent_contact_notes, outreach_templates, outreach_log
**Scope:** 25 API endpoints, 2 frontend pages, 53 tests, 5 branded seed email templates

- [x] [CB-PCM-S1] DB models + migrations (#2975) — PR #3106
- [x] [CB-PCM-S2] Pydantic schemas (#2976) — PR #3106
- [x] [CB-PCM-S3] Customer contacts CRUD API (#2977) — PR #3107
- [x] [CB-PCM-S4] Outreach templates CRUD API + seed (#2978) — PR #3108
- [x] [CB-PCM-S5] Outreach send API — email, WhatsApp, SMS (#2979) — PR #3109
- [x] [CB-PCM-S6] Frontend — Customer Database page (#2980) — PR #3110
- [x] [CB-PCM-S7] Frontend — Unified Outreach Composer (#2981) — PR #3111
- [x] [CB-PCM-S9] Tests — backend + frontend (#2983) — PR #3112

**Integration PR:** #3113 (merged all 8 stories)

**PR review fixes (all closed):**
- #3114 — N+1 query in outreach log list
- #3115 — Tag filter memory (PG JSON contains + SQLite 5000 cap)
- #3116 — SOURCE_OPTIONS mismatch
- #3117 — Duplicate warning header
- #3118 — Render function dedup
- #3119 — CSV export limit (10000 row cap)
- #3120 — get_contact detail response
- #3121 — OutreachLogResponse schema

**Post-deployment fixes:**
- #3126/#3135 — Trailing slash 404
- #3136/#3137 — Transparent modal fix
- Checkbox appearance fix, surrogate emoji fix

### CB-AFM-001 — Admin Feature Management (§6.133) — DEPLOYED (2026-04-12)

- [x] DB model + seed (FeatureFlag table, 8 default flags) — #3145, PR #3157
- [x] Admin Feature Management page — #3146, PR #3157
- [x] Sidebar nav gating by feature flags — #3147, PR #3157
- [x] Collapsible admin nav sections — #3141, PR #3148
- [x] PR review fixes: cache invalidation, flash-redirect, seed error handling, updated_at — #3151-#3156, PR #3157

### CB-PEDI-001 — Parent Email Digest Defect Fixes — DEPLOYED (2026-04-13)

**Defect:** Email Digest "Connect Your Gmail" always fails with 500/502 for all users.
**Root cause 1:** Missing null guard on `gmail_address` → `NotNullViolation` crash. Fixed in #3031 (PR #3169).
**Root cause 2:** OAuth scopes missing `userinfo.email` + `userinfo.profile` → Google userinfo API always rejects. Fixed in #3176 (PR #3177).
**Additional fixes:** Non-200 userinfo logging (#3159), specific exception types (#3160). All via PR #3169.
**Requirements updated:** §6.127 OAuth scopes corrected, F-16 multi-sender whitelist added to Phase 2 (#3178).
**Open suggestions:** Migrate to OpenID Connect scopes (#3179).

### Phase 3+ — Open
- Issue #506: University Pathway Alignment
- Issue #507: Course Planning Navigation & Dashboard Integration
- Issue #508: Course Planning Tests
- Issue #511: School Board Integration for Course Planning
- Issue #571: Ontario Curriculum Management
- Issue #942: Phase 1.5: School board email integration
- Issue #943: Phase 1.5: Google Calendar push integration
- Issue #945: Phase 1.5: Multi-Google account support for teachers
- Issue #959: Epic: AI Exam & Assessment Engine
- Issue #960: Epic: Student Progress & Report Card Analysis
- Issue #963: Epic: Mobile App Build & Distribution
- Issue #967: Epic: Phase 4 — LMS Integration Hub
- Issue #968: Epic: Phase 5 — Marketplace & Community Features

---

## 13. Development Setup

See individual skill files for development commands:
- `/start` - Start development servers
- `/build` - Build for production
- `/test` - Run test suite
- `/status` - Check project status
- `/db-reset` - Reset development database
- `/feature` - Create feature branch
- `/new-endpoint` - Scaffold new API endpoint

---

## 14. Phase-2 Repository Consolidation Tracking

**Source:** `class-bridge-phase-2` (247 commits, 34 models, 40+ routes, 66+ pages)
**Assessment Date:** 2026-03-22

### Features Already on Master (No Port Needed)
XP/gamification, achievement badges, study streaks, AI usage tracking, waitlist, account deletion, data export, resource links, content images, daily/weekly digests, assessment countdown, multilingual summaries, report cards, Pomodoro sessions, study timeline, wallet/credits.

### Unique Features to Port (Phase 2F Milestone — May 1, 2026)

| Feature | Issue | Models | Routes | Pages | Status |
|---------|-------|--------|--------|-------|--------|
| 2FA/TOTP Authentication | #2130 | 1 | 3 | 1 | Planned |
| Feature Flags Infrastructure | #2131 | 1 | 2 | 1 | Planned |
| Learning Journals | #2132 | 2 | 5 | 2 | Planned |
| Meeting Scheduler | #2133 | 2 | 4 | 2 | Planned |
| Discussion Forums | #2134 | 3 | 6 | 3 | Planned |
| Peer Review | #2135 | 2 | 4 | 2 | Planned |
| AI Writing Assistance | #2136 | 1 | 3 | 1 | Planned |
| AI Homework Help | #2137 | 1 | 3 | 1 | Planned |
| Wellness Check-ins | #2138 | 2 | 4 | 2 | Planned |
| Student Goals | #2139 | 2 | 4 | 2 | Planned |

### Migrated Issues from emai-class-bridge
47 open issues (#2143-#2189) covering: DTAP compliance, implemented features needing porting, classroom data import, test coverage expansion.

### MCP Protocol Porting
9 issues (#2191-#2199) to port Model Context Protocol server. ~50% complete in phase-2 repo. Includes: server foundation, JWT auth, study tools (7), tutor tools (3), student resources (6), import tools (5).
