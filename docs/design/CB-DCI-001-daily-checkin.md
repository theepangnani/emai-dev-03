# CB-DCI-001 · Daily Check-In Ritual · Design Lock

| Field | Value |
|---|---|
| PRD ID | CB-DCI-001 |
| Source PRD | `CB_DCI_001_PRD_v2.docx` (Apr 2026) |
| Status | M0 build in progress (flag OFF) |
| Target ship | Sept 2026 (V1) |
| Epic | #4135 |
| Owner | Theepan |
| Tracking issues | M0-1 #4136 · M0-2 #4140 · M0-3 #4141 · M0-4 #4139 · M0-5 #4142 · M0-6 #4143 · M0-7 #4144 · M0-8 #4145 · M0-9 #4146 · M0-10 #4147 · M0-11 #4148 · Fast-follow #4149 |

> Tagline: **Not data entry. A 60-second 'show me your day.'**

---

## 1 · Strategic framing

DCI is V1 Pain #4 — the **retention engine** of the $19/mo AI tier. It is **NOT** the primary content-ingestion mechanism (Gmail forwarding + Google Classroom OAuth cover ~85 % of content). DCI's job is to fill the last 10 % gap (paper handouts, kid-narrated context) AND, more importantly, to create the daily ritual that turns a $19-paying Contextual-stage parent into an 8-year Continuous-stage family.

| | Pain #3 — Study Guides | Pain #4 — DCI |
|---|---|---|
| Test passed | Kumon Test ("Could I cancel Kumon?") | 8-Year Test ("Will this family stay 96 months?") |
| Function | **Conversion** lever | **Retention** lever |
| Cadence | On-demand | Daily |
| Without it | AI tier not worth $19 | Churn at 60 days |

The two features form the core economic loop. Ship both or ship neither.

---

## 2 · Personas

**Priya (primary buyer).** Dual-earner Markham parent, ~38, two kids in K-12 (Grades 3 + 6), $500/mo current education spend (Kumon $180 + extracurriculars $240 + tutoring $80). Tech-comfort 4/5. Already proved willingness-to-pay. Time budget: **4 min review + 5 min talk**.

**Haashini-like kid (Grade 5-8).** Daily user. Time budget: **60 sec/day**. Goal: finish fast, feel seen, keep streak.

**Older sibling (Grade 9+).** Optional user. 30-60 sec/day. Streak optional.

**Second parent.** Async catch-up viewer, ~3 min × 2/wk.

**Future personas (NOT in V1):** teacher (read-only), admin.

Priya's success criterion: *"At end of school year, I look back and realize my kid and I had a real 5-min conversation about school almost every night for 9 months. That didn't happen last year. That's why I'm still paying."*

---

## 3 · Goals & non-goals

### Goals
- **G1 Retention.** 20-30 % of AI-tier families move Contextual → Continuous within 90 days.
- **G2 Engagement.** 70 %+ kid check-in completion rate on school days (Continuous-stage families).
- **G3 Connection.** 30 %+ "I used the conversation starter" feedback rate.
- **G4 Effort floor.** Median kid time-on-task ≤ 75 s (target 60 s).
- **G5 Data asset (secondary).** De-identified longitudinal data that de-risks V3 board dashboards — never at the cost of family privacy.

### Non-goals (V1)
- **NG1** Not the primary ingestion path.
- **NG2** No teacher / admin role.
- **NG3** No multi-week pattern view (V2 stub only in V1).
- **NG4** No grading / assessment / teacher feedback.
- **NG5** No kid-to-kid social features.
- **NG6** **No homework-answering chatbot for kids** — principle-level constraint, not just scope. We do not disintermediate parents.

---

## 4 · Relationship to other V1 features

### Three ingestion paths
| Path | Source | Routes to |
|---|---|---|
| 1 | Parent-side Gmail forwarding | Deadline dashboard + lesson summaries |
| 2 | User-authorized Google Classroom OAuth | Deadline dashboard + study guide raw material |
| 3 | **DCI — kid daily check-in** (this PRD) | Evening parent summary + conversation starter generation; cross-referenced for "paper-only" gap detection |

### Routing rules
- **Email content** → does NOT surface in DCI evening summary unless the kid references it.
- **Classroom content** → surfaces in DCI as background context for conversation-starter generation.
- **DCI content** → cross-referenced against email / OAuth data to detect gaps ("teacher gave a handout we didn't see on Classroom").

### One rule that resolves most scoping arguments
> If the content could have come through email or Google Classroom — it should, and DCI should not duplicate the capture. DCI's job is to catch what the other two paths miss AND to create the daily ritual moment. Not to be a generic inbox.

### Interaction with other shipped features
- **Smart Briefing (§6.61):** yesterday's DCI surfaces in tomorrow morning's briefing.
- **CB-PEDI-002 unified digest:** weekly digest references DCI patterns starting Day 30+.
- **CB-TASKSYNC-001:** auto-creates tasks from `classification_events.deadline_iso`.
- **CB-ILE-001 Flash Tutor:** detected handout → "Want a 5-question warm-up?" upsell.
- **CB-TUTOR-001 unified Tutor + Arc:** Arc mascot is the kid's companion across both check-in and tutor flows — shared visual identity.

---

## 5 · Principles alignment

| Principle | How DCI respects it |
|---|---|
| P1 — Parent is data controller | All photo/voice/text stored under parent account, visible in Settings, deletable anytime. AI processing toggle. |
| **P2 — Kid is narrator, not worker** | **THE CORE BET.** Three-input UX, streak as affirmation, "close the app" messaging. No data-entry forms, no required fields. |
| P3 — AI assists, never decides | Every summary parent-editable. Classification correctable by kid. Conversation starter has regenerate. |
| P4 — Compliance is a feature | MFIPPA consent flow during onboarding. Bill 194 disclosure inline at every check-in. Auditable model provenance. |
| P5 — B2C funds B2B | DCI is pure B2C retention. Data asset separately governed. |
| P6 — Boards win when parents win | De-identified aggregate (digital-paper gap) useful to boards; individual families never exposed without explicit board partnership authorization. |
| P7 — Minimum data, maximum signal | 90-day default retention, parent-configurable to 3 yr. Raw content processed and discarded; derived signals retained longer. |
| P8 — Ontario-first, Canada-always | All storage GCP `northamerica-northeast1`. No cross-border processing. Ontario curriculum calibration. |

---

## 6 · End-to-end information flow

```
KID · 3:30 PM           AI · INSTANT             PARENT · 7:00 PM
─────────────────       ─────────────────        ─────────────────
[Snap photo]            Vision OCR (Sonnet 4.6)  Evening summary
[Record voice]    →     Whisper transcribe   →   30-sec digest
[Type 2 lines]          GPT-4o-mini classify     Conversation starter
                        Sonnet 4.6 summary       Tap to deep-dive
60 s effort             < 2 s chip / < 30 s sum  4 min review

           ↓ family conversation (5 min, off-app)
```

Critical design principle (P2): the kid is the **narrator** of their own day, not a data-entry worker. Every UX decision — three giant input buttons, streak affirmation, "tonight your parents will see" reassurance, explicit close — reinforces storytelling, not chores. **Single most important UX bet in V1.** If it fails, DCI's retention impact collapses.

---

## 7 · Kid experience (M0 = web; fast-follow = Expo mobile)

### M0 — Web at `/checkin` (3 screens)

**Screen 1 — Greeting & input selection**
- Header: `Hi {kidName}` (no `!` if last voice sentiment ≤ −0.3 — adaptive tone)
- Body: "Quick 60-second check-in. How was school today?"
- Three equal-priority CTAs (camera-first because highest-info / lowest-effort):
  1. **Snap a photo** — Handout · Board · Notebook
  2. **Record voice** — "Today we learned…"
  3. **Type a line** — Quick & easy
- ArcMascot at top, mood=`waving`
- Bottom tab: Home · Today · Tasks · Me (kid mode chrome only)

**Screen 2 — Capture & AI preview**
- **Photo:** `getUserMedia` webcam stream + A4-shaped guide rectangle overlay. Capture → preview → on-device JPEG resize to ≤ 500 KB → upload.
- **Voice:** `MediaRecorder` API, 16 kHz mono opus encoding, ≤ 60 s, level meter visualization, stop button. Local VAD trim before upload.
- **Text:** `<textarea maxlength=280>` with character counter.
- After upload: `<AIDetectedChip>` shows subject + topic + deadline ≤ 2 s p50 (sync GPT-4o-mini call).
- Kid can tap chip to correct ("Actually this is Science, not Math") → `PATCH /api/dci/checkin/{id}/correct`.
- `+ Add more` chip enables multi-artifact day (one photo + one voice + one text).
- CTA: **"Send to ClassBridge"** (Bill 194 disclosure inline above CTA: *"AI will read this to help your parents."*)

**Screen 3 — Affirmation & streak**
- Success ring + check mark (hard closure — kids need to know they're "done")
- ArcMascot mood=`celebrating`
- `XpStreakBadge`: current + longest streak (never guilts on missed days)
- "Tonight your parents will see:" preview list (subject bullets, deadlines)
- Explicit close: **"Close the app. Have a snack. You're good."**
- Auto-dismiss 8 s if not tapped (no engagement farming — VPC constraint)

### Fast-follow — Expo mobile (kid app)
Same 3-screen flow on `expo-camera` + `expo-av` + `expo-notifications` (3:15 PM push, no-school suppression). PIN optional for shared devices. Tracked in #4149.

---

## 8 · Parent experience (M0 = web; fast-follow = Expo mobile)

### M0 — Web at `/parent/today` (does NOT modify ParentDashboard)

**Layout (mobile-first single column, also responsive web):**
1. Header: kid name + date + `ChildSelectorTabs` (multi-kid)
2. **`<EveningSummaryHero>` (NEW):** AI summary · 30-sec read · 3 subject bullets in plain text on navy ink card
3. **Upcoming chips:**
   - Amber: ≤ 7 days
   - Red: overdue OR paper-only
   - Badge: "Not yet on Google Classroom" for paper handouts
4. **Conversation Starter card:** navy bg + amber accent rule + italic AI question + "Tap to see voice note →" + footer (👍 used / regenerate)
5. **Today's artifacts strip:** thumbnail row of photos / voice waveform pills / text snippets — tap-to-deep-dive

**Deep-dive route `/parent/today/artifact/{id}` (M0 stub):**
- Voice player with waveform + AI transcript side-by-side
- "What this means" curriculum strand annotation (B1.1 etc.) via `curriculum_mapping`
- Engagement HIGH/MED/LOW (sentiment + semantic richness)
- "If she wants more" external links (Khan Academy, Crash Course Kids — never hosted)
- Parent edit + regenerate buttons (P3)

**Pattern view `/parent/today/patterns` (M0 = stub):**
- Single line: *"We're learning about Haashini. Check back in 30 days for your first insight."*
- Real pattern view ships V2.

### Fast-follow — Expo mobile (parent app)
Same screens on Expo, parent push at 7:00 PM (suppressed when no kids checked in). Tracked in #4149.

---

## 9 · System architecture

```
CLIENT
  Web kid (/checkin)         Web parent (/parent/today)        [Expo mobile = fast-follow]
       │                              │
API · FastAPI
  POST /api/dci/checkin     GET /api/dci/summary/{kid}/{date}
  PATCH .../{id}/correct    PATCH /api/dci/summary/{id}
  GET .../{id}/status       PATCH /api/dci/conversation-starters/{id}/feedback
  POST /api/dci/consent     GET /api/dci/streak/{kid}
       │
AI PIPELINE
  Vision OCR (Sonnet 4.6)   Whisper (OpenAI API) + sentiment
  Classifier (GPT-4o-mini)  Summary + conv starter (Sonnet 4.6 + prompt cache)
  Curriculum mapping (existing service)
  Content-policy v0 (regex + keyword)
       │
STORAGE (all GCP northamerica-northeast1)
  GCS object store          PostgreSQL (6 new tables)
  90 d default retention    audit_event (provenance)
  Family-scoped signed URLs
```

### Reuse map
| Existing | Used as | Path |
|---|---|---|
| `briefing_service` / `parent_digest_ai_service` | Substrate for summary generator (new prompt) | `app/services/` |
| Conversation-starters endpoint + cache | Repurposed with `source='dci'` | `app/api/routes/conversation_starters.py` |
| `StreakService` + `streak_check.py` | New `action_type='daily_checkin'` aggregate | `app/services/streak_service.py` |
| `asgf_ocr_service` | Vision OCR for photo handouts | `app/services/asgf_ocr_service.py` |
| `curriculum_mapping` | Strand-code annotation in deep-dive | `app/services/curriculum_mapping.py` |
| `notification_service` | Multi-channel fan-out (in-app, email; Expo channel = fast-follow) | `app/services/notification_service.py` |
| `feature_flag_service` | `dci_v1_enabled` toggle | `app/services/feature_flag_service.py` |
| APScheduler in `main.py` | 6:50 PM regen + 3:15/7:00 PM push (fast-follow) | `main.py` |
| `DashboardLayout`, `ChildSelectorTabs`, `ConversationStartersCard`, `XpStreakBadge`, `ArcMascot` | Reused as-is on parent + kid screens | `frontend/src/` |
| `audit_service` | Model provenance + consent change audit | `app/services/audit_service.py` |

### Greenfield
- `dci_voice_service.py` (Whisper + sentiment)
- `dci_summary_service.py` (Sonnet 4.6 + prompt cache)
- `dci_content_policy.py` (v0 regex + keyword)
- `app/api/routes/dci.py`
- `app/api/routes/dci_consent.py`
- `<EveningSummaryHero>`, `<AIDetectedChip>`, `<CapturePicker>`, `<ArtifactCorrector>`, `<DeadlineChip>`, `<ArtifactStrip>` (all new in `frontend/src/components/dci/`)
- Kid web pages: `frontend/src/pages/dci/CheckInIntroPage.tsx`, `CheckInCapturePage.tsx`, `CheckInDonePage.tsx`
- Parent web pages: `frontend/src/pages/dci/EveningSummaryPage.tsx`, `ArtifactDeepDivePage.tsx`, `PatternsStubPage.tsx`

---

## 10 · Data model (M0)

```sql
-- daily_checkins: each kid check-in event
CREATE TABLE daily_checkins (
  id              SERIAL PRIMARY KEY,
  kid_id          INT NOT NULL REFERENCES students(id),
  parent_id       INT NOT NULL REFERENCES users(id),
  submitted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  photo_uris      JSON DEFAULT '[]',
  voice_uri       VARCHAR(500),
  text_content    VARCHAR(280),
  source          VARCHAR(20) DEFAULT 'kid_web'  -- 'kid_web' | 'kid_mobile'
);
CREATE INDEX idx_daily_checkins_kid_date ON daily_checkins(kid_id, submitted_at);

-- classification_events: one row per AI artifact classification
CREATE TABLE classification_events (
  id              SERIAL PRIMARY KEY,
  checkin_id      INT NOT NULL REFERENCES daily_checkins(id),
  artifact_type   VARCHAR(20) NOT NULL,   -- 'photo' | 'voice' | 'text'
  subject         VARCHAR(50),
  topic           VARCHAR(200),
  strand_code     VARCHAR(20),
  deadline_iso    DATE,
  confidence      FLOAT,
  corrected_by_kid BOOLEAN DEFAULT FALSE,
  model_version   VARCHAR(50),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ai_summaries: parent-facing daily summary
CREATE TABLE ai_summaries (
  id              SERIAL PRIMARY KEY,
  kid_id          INT NOT NULL REFERENCES students(id),
  summary_date    DATE NOT NULL,
  summary_json    JSON NOT NULL,
  generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  model_version   VARCHAR(50) NOT NULL,
  prompt_hash     VARCHAR(64) NOT NULL,
  policy_blocked  BOOLEAN DEFAULT FALSE,
  parent_edited   BOOLEAN DEFAULT FALSE,
  UNIQUE (kid_id, summary_date)
);

-- conversation_starters: starter history + feedback
CREATE TABLE conversation_starters (
  id                 SERIAL PRIMARY KEY,
  summary_id         INT NOT NULL REFERENCES ai_summaries(id),
  text               TEXT NOT NULL,
  was_used           BOOLEAN,
  parent_feedback    VARCHAR(20),  -- 'thumbs_up' | 'regenerate'
  regenerated_from   INT REFERENCES conversation_starters(id),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- checkin_streak_summary: per-kid streak aggregate (separate from study streak)
CREATE TABLE checkin_streak_summary (
  kid_id             INT PRIMARY KEY REFERENCES students(id),
  current_streak     INT DEFAULT 0,
  longest_streak     INT DEFAULT 0,
  last_checkin_date  DATE,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- checkin_consent: parent-controlled consent toggles
CREATE TABLE checkin_consent (
  parent_id        INT NOT NULL REFERENCES users(id),
  kid_id           INT NOT NULL REFERENCES students(id),
  photo_ok         BOOLEAN DEFAULT FALSE,
  voice_ok         BOOLEAN DEFAULT FALSE,
  ai_ok            BOOLEAN DEFAULT FALSE,
  retention_days   INT DEFAULT 90,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (parent_id, kid_id)
);
```

### Migration safety (per CLAUDE.md)
- Each ALTER TABLE in `main.py` startup, top-level inside `with engine.connect()`, own `conn.commit()`, try/except + rollback
- `pg_try_advisory_lock` (NOT `pg_advisory_lock`) with 3 retries, 5 s wait
- DB compatibility: `DEFAULT FALSE` for booleans, `TIMESTAMPTZ` (PG) / `DATETIME` (SQLite) gated by `if "sqlite" not in settings.database_url`
- `String(20)` instead of `Enum(PythonEnum)` where applicable
- Pydantic `from_attributes=True` schemas — verify no deferred columns trigger lazy load on serialization

---

## 11 · Privacy & compliance

### MFIPPA (Ontario)
- All DCI data hosted in GCP `northamerica-northeast1`
- Kid-generated content classified as parent-controlled personal information
- Explicit consent flow during onboarding: photo / voice / AI processing / retention duration — all individually togglable

### Bill 194 (Ontario AI disclosure)
- AI processing disclosed at each check-in inline: *"AI will read this to help your parents."*
- Incident reporting framework — 24h SLA for any data access anomaly
- Model provenance logged per summary (which model generated what content, auditable in `audit_event`)

### Child-safety safeguards
- Voice notes transcribed but NEVER shared outside the family account
- Photo storage opaque to non-family readers — object URIs require family-scoped signed tokens (TTL ≤ 5 min)
- Content-policy layer (M0-7) blocks: PII leakage, other-kid identification (regex v0; ML classifier in fast-follow), medical/legal interpretation
- Parent override: any AI summary can be regenerated, edited, or discarded

---

## 12 · Success metrics

| Metric | V1 target | M0 measurement |
|---|---|---|
| Kid check-in completion rate | 70 %+ school days | `dci.kid.completed_seconds` per active kid, 30-d window |
| Median kid time-on-task | ≤ 75 s (target 60 s) | `dci.kid.completed_seconds` p50 |
| Parent review rate | 60 %+ of daily summaries | `dci.parent.summary_viewed` within 24 h of generation |
| Conversation starter usage | 30 %+ marked used | `dci.parent.starter_used` toggle |
| Contextual → Continuous conversion | 20-30 % | Families moving from event-triggered to daily within 90 d |
| 30-d retention (AI tier) | 70 %+ | Weekly active families day 30 vs day 1 |
| 90-d retention (AI tier) | 50 %+ | Weekly active families day 90 vs day 1 |
| NPS (parents) | 50+ | In-app survey at 14 d and 90 d |
| Cost per family per day | ≤ $0.04 | `dci.cost_per_family_per_day` from `ai_usage_log` |

---

## 13 · Resolved decisions (this design lock)

| Topic | Decision | Reasoning |
|---|---|---|
| Weekend scope | M0 working web demo (flag OFF) | User direction; mobile + nudge fast-follow |
| Web vs mobile for M0 | All-web for kid + parent | Webcam + MediaRecorder are "good enough" for spike; Expo lift is multi-week |
| Pre-Priya validation | Build now, interview after | User direction; M0 is the artifact we put in front of Priyas |
| Summary model | **Sonnet 4.6 with prompt caching** | ~5× cheaper than Opus 4.7 (~$0.005 vs ~$0.09 per family per day with caching). Existing `parent_digest_ai_service` runs Haiku 4.5 successfully — Sonnet is one tier up. Opus 4.7 reserved as one-flag-flip fallback if blind eval misses bar |
| Vision OCR model | Sonnet 4.6 | PRD-approved default; Opus only for accuracy-critical handouts (deferred) |
| Classifier (chip) | GPT-4o-mini sync | Cheap, fast, ≤ 2 s p50 — kid can't wait for async |
| Voice transcription | OpenAI Whisper API | PRD-approved; sentiment via Haiku 4.5 |
| Streak overlap | **Separate `checkin_streak_summary` table; reuse `StreakLog` writes** | Existing `action_type` column lets writes be reused; aggregate must be per-stream because a kid who studies via Tutor but never checks in shouldn't have a "DCI streak" |
| Missed-7-days UX | **Day-7 single in-app + email parent nudge, invitation-framed, mute toggle, re-arms after resume** | Honors P1 (parent is controller) without violating P2 (kid is narrator). Skip during honeymoon (first 14 d), suppress on holidays/weekends. Tracked under fast-follow #4149 |
| Streak monetization | **None.** Streaks celebrate; never guilt | Resolves PRD §14 Q8 — VPC constraint against manipulative engagement |
| Content-policy v0 | Regex + keyword (PII / named-other-kid / medical-legal); fail-closed if redaction retry fails | Real ML classifier + face detection are fast-follow; v0 must still get external counsel review before flag enable |
| Cost ceiling | ≤ $0.04 per family per day | Includes Whisper + classifier + summary; circuit-breaker at $0.05 |
| Numbering convention | §6.143 in `requirements/features-part7.md` | After §6.142 CB-PEDI-002. Note: §6.142 is duplicated (CB-TUTOR-002 also at §6.142) — flagged as fast-follow renumbering issue |

---

## 14 · Open questions (to resolve before V1 ramp)

| # | Question | Owner | Resolution timing |
|---|---|---|---|
| Q1 | Days kid doesn't check in — silent vs gentle? | Design | Resolved partially: 7+ days = parent nudge. Days 1-6 = silent. |
| Q2 | When do we offer kid a view of parent's summary? | Design + Legal | Post-M0 |
| Q3 | Multi-kid: per-kid or all-kids digest default? | Design | Working: per-kid with all-kids tab |
| Q4 | Does Priya actually do day-1 setup with her kid? | Research | Priya interviews (fast-follow #4149) |
| Q5 | What % of Grade 5-8 kids do 5+ check-ins/wk without nudge? | Research | Priya interviews |
| Q6 | Does the conversation starter actually work in real homes? | Research | Priya interviews |
| Q7 | Do we support email-forward-only parents as "no DCI" tier? | Product | Working proposal: yes, fallback for non-engaged kids |

---

## 15 · M0 acceptance criteria (definition of "weekend done")

- [ ] All 6 tables created on dev SQLite + verified migration plan for prod PG (M0-2)
- [ ] `dci_v1_enabled` flag exists, defaults OFF, blocks all DCI routes (M0-3)
- [ ] `POST /api/dci/checkin` round-trips photo + voice + text → returns 202 + classification chip ≤ 2 s (M0-4)
- [ ] Whisper transcription + Haiku sentiment scoring writes to `classification_events` (M0-5)
- [ ] Sonnet 4.6 summary generator produces JSON summary + conversation starter, written to `ai_summaries` (M0-6)
- [ ] Content-policy v0 blocks PII / named-other-kid / medical-legal in test harness (M0-7)
- [ ] Check-in streak table updates correctly on consecutive days; school-day-aware (M0-8)
- [ ] Kid web flow `/checkin` works in Chrome + Safari with webcam + MediaRecorder (M0-9)
- [ ] Parent web flow `/parent/today` renders summary + conversation starter from a fixture day (M0-10)
- [ ] Consent flow gates writes; Bill 194 disclosure visible; settings section toggles work (M0-11)
- [ ] All M0 work integrated on `integrate/cb-dci-001-m0`; no merge to master without explicit approval; flag stays OFF on prod
- [ ] Local lint + build + pytest green before any push

---

## 16 · Fast-follow scope (post-M0, tracked in #4149)

Mobile (Expo kid + parent · push · camera · voice) · Cross-reference DCI ↔ Gmail/Classroom · Day-7 parent nudge job · Lifecycle/purge cron · DCI → CB-TASKSYNC auto-task · DCI → CB-ILE upsell · Content-policy red team + counsel review · Pattern view (V2 prep) · Telemetry dashboard · DCI → Smart Briefing · Priya interviews + Q4-Q6 validation · Q9 missed-days UX formalization.

---

## 17 · Risks (rank-ordered)

1. **Kid daily engagement rate (Q5).** The unknown that breaks the whole feature. Mitigation: Priya interviews + 14-day closed beta gate before ramp.
2. **Content-policy false negatives → child-safety incident → MFIPPA breach.** Mitigation: external counsel review of M0-7 taxonomy + red-team test suite + manual audit of first 1,000 summaries.
3. **Voice transcription cost & accuracy in noisy kid environments.** Mitigation: VAD trim + cost cap + fallback "transcript unavailable" UX.
4. **Sonnet 4.6 quality vs Opus 4.7.** Mitigation: blind eval first 100 summaries; one-flag-flip fallback to Opus if quality misses bar.
5. **Streak gamification → manipulation accusation.** Mitigation: never-guilt copy, no monetization, log break events but never surface to kid.
6. **§6.142 numbering collision in requirements.** Mitigation: fast-follow renumbering issue (cosmetic, not blocking).

---

## 18 · References

- Source PRD: `CB_DCI_001_PRD_v2.docx` (Apr 2026)
- V1 Scope Document, Vision/Principles/Constraints framework, Data Consent Architecture
- Adjacent epics: CB-PEDI-002 (#4045), CB-TUTOR-001 (#3974), CB-TUTOR-002 (epic #4062), CB-ILE-001, CB-TASKSYNC-001, CB-BRIDGE-001
- Requirements: `requirements/features-part7.md` §6.143 (this PR)
- Issue tracker: epic #4135
