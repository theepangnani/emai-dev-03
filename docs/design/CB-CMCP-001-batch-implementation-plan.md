# CB-CMCP-001 — Batch Implementation Plan

**Source PRDs:** [`CB-CMCP-001-PRD-v1.0.docx`](../../) + [`CB-CMCP-001-PRD-v1.1.docx`](../../) (authenticity amendments, supersedes v1.0) + [`CB-CMCP-001-DD-v1.0.docx`](../../) (design)
**Requirements:** [§6.150](../../requirements/features-part7.md)
**Epic:** [#4351](https://github.com/theepangnani/emai-dev-03/issues/4351)
**Authenticity sub-issues:** [#4352 A1](https://github.com/theepangnani/emai-dev-03/issues/4352) · [#4353 A2](https://github.com/theepangnani/emai-dev-03/issues/4353) · [#4354 A3](https://github.com/theepangnani/emai-dev-03/issues/4354) · [#4355 A4](https://github.com/theepangnani/emai-dev-03/issues/4355)
**Decision sub-issues:** [#4361–#4371](https://github.com/theepangnani/emai-dev-03/issues/4361) (D1–D11)
**Status:** PLAN — NOT YET STARTED
**Author:** Theepan Gnanasabapathy (mentor pass: Claude)
**Date:** 2026-04-27

---

## 1. Why this plan exists

Mentor review of CB-CMCP-001 PRD v1.0 surfaced four authenticity gaps (now A1–A4 binding amendments in PRD v1.1) and eleven strategic-decision items. The user asked for *"a detailed batch implementation plan"* using design-thinking principles, with explicit emphasis on **reusability, extensibility, scalability, simplicity**, and **domain-driven design**.

This plan is a single source of truth for *how* CB-CMCP-001 ships — the bounded contexts, the batches, the integration sequence, and the gates between milestones. It does **not** override the open decisions: it codifies the **default working assumptions** (mentor recommendations from D1–D11) so engineering can proceed without re-litigating each batch, and explicitly calls out the boundary edits required if any decision lands differently.

This document does **not** start development — it is a planning artifact, reviewable as a PR before any code stripe is opened.

---

## 2. Working assumptions (mentor-recommendation defaults)

All eleven decisions remain user-owned. For planning purposes the recommendations from D1–D11 are taken as defaults. Each is annotated with its **boundary-edit cost** if reversed.

| # | Decision | Default | If reversed |
|---|---|---|---|
| D1 | One MCP vs two | **C — defer board MCP** | Cheap. M2 batch 2a still ports the scaffold; the board-side `BOARD_ADMIN` tool surface is just deferred. Reversing later = open a new MCP deployment. |
| D2 | `study_guides` vs new `content_artifacts` | **B — extend `study_guides`** | Medium. Schema choice cascades. If reversed mid-flight, new code dual-writes during a migration window. Decide before M0 batch 0a. |
| D3 | Self-study path | **C — hybrid (self-study + class-distribute)** | Cheap. State-machine just gains/loses a `SELF_STUDY` state. UI swaps badges. |
| D4 | Validator second-pass | **C in M1, B in M3** | Cheap. Validator is a pluggable post-step. Adding embedding similarity is additive. |
| D5 | CEG extraction quality | **B — two-pass + paid OCT reviewer** | Cheap engineering, expensive headcount. If reversed (single-pass + admin), accuracy SLA drops; CEG release criteria loosen. |
| D6 | Latency NFRs + streaming | **B — per-type SLA + streaming** | Medium. Streaming UX touches ~5 frontend components. Reversing to sync-only forces shorter-form artifacts only. |
| D7 | Board surface | **B — REST/LTI primary, MCP secondary** | Cheap. Board REST endpoints are an additive layer on top of the same data model. |
| D8 | Cost model | **B — estimate now** | Cheap. ~1 day of analysis. Saves a budget surprise mid-M1. |
| D9 | CEG version cascade | **B — severity classifier** | Cheap. One column on `ceg_versions` + one job. |
| D10 | IEP scope | **B — defer to Phase 2** | Cheap. 3 difficulty tiers ship; IEP customization is teacher-edit-time. |
| D11 | Board interviews | **B — interviews in parallel with M0** | Strategic, not engineering. CEG (M0) has B2C value regardless. |

**The plan below assumes all eleven defaults.** Each batch flags decision dependencies in its preconditions. Decisions D1, D2, D3, D5, D7, D11 are the **M0 hard gates** — must be confirmed before M0 batch 0a opens.

---

## 3. Domain-driven design model

### 3.1 Bounded contexts

CB-CMCP-001 spans six bounded contexts. Each owns its data, its language, and its integration contracts. Cross-context communication is by **domain events** (not direct DB joins).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CB-CMCP-001 system                              │
│                                                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐ │
│  │   CURRICULUM       │  │   GENERATION       │  │   AUTHORING        │ │
│  │                    │  │                    │  │                    │ │
│  │  CEG (graph)       │  │  CGP (pipeline)    │  │  Review queue      │ │
│  │  Subjects/Strands/ │  │  Guardrail Engine  │  │  State machine     │ │
│  │  Expectations/     │  │  Validator         │  │  Edit history      │ │
│  │  Versions          │  │  Voice overlay     │  │  Approval / reject │ │
│  │                    │  │                    │  │                    │ │
│  │  Owner: Curriculum │  │  Owner: AI         │  │  Owner: Teacher    │ │
│  │  Admin             │  │  Service           │  │  Portal            │ │
│  └────────┬───────────┘  └────────┬───────────┘  └────────┬───────────┘ │
│           │                       │                        │            │
│           │   CurriculumUpdated   │   ArtifactGenerated   │  Approved   │
│           │   ExpectationVersioned│   AlignmentScored     │  Rejected   │
│           ▼                       ▼                        ▼            │
│  ════════════════════════ DOMAIN EVENT BUS ════════════════════════     │
│           │                       │                        │            │
│           ▼                       ▼                        ▼            │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐ │
│  │   SURFACE          │  │   AUTHORIZATION    │  │   DISTRIBUTION     │ │
│  │                    │  │                    │  │                    │ │
│  │  DCI coach card    │  │  Roles             │  │  MCP server        │ │
│  │  Digest block      │  │  RBAC matrix       │  │  REST/CSV/LTI      │ │
│  │  Bridge entry      │  │  Board OAuth       │  │  Board catalog     │ │
│  │  ParentCompanion   │  │                    │  │  Coverage map      │ │
│  │                    │  │                    │  │                    │ │
│  │  Owner: Surface    │  │  Owner: Auth       │  │  Owner: Public     │ │
│  │  Dispatcher        │  │  Service (existing)│  │  API gateway       │ │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Aggregates per context

Each aggregate has a **root entity** (transactional consistency boundary) and **value objects**.

| Context | Aggregate root | Value objects | Key invariants |
|---|---|---|---|
| Curriculum | `Expectation` (one OE or SE) | `MinistryCode`, `Strand`, `CurriculumVersion`, `Embedding` | An SE always has a `parent_oe_id`. Active SEs are always within the latest `CurriculumVersion` per subject/grade. |
| Generation | `GenerationRun` (one CGP request) | `GuardrailEnvelope` (CEG SE list + class-context), `VoiceModuleHash`, `AlignmentScore`, `EngineRoute` | Every run has a guardrail envelope. Voice module hash is recorded at generation time. Alignment score ∈ [0,1]. |
| Authoring | `ContentArtifact` (extends `study_guides` per D2) | `ArtifactState`, `EditDelta`, `ApprovalDecision`, `ReviewerId` | State machine is acyclic except DRAFT↔PENDING_REVIEW. Approved artifacts are immutable; new approval = new version row. |
| Surface | `SurfaceDispatch` (one fan-out event) | `DCICoachCard`, `DigestBlock`, `BridgeCard`, `DispatchOutcome` | All three derivative payloads are emitted best-effort; failure of one does NOT block others or the artifact's APPROVED state. |
| Authorization | `RolePolicy` (existing dev-03; extended) | `BoardScope`, `CurriculumAdminScope` | New roles added: `BOARD_ADMIN`, `CURRICULUM_ADMIN`. Existing PARENT/STUDENT/TEACHER/ADMIN unchanged. |
| Distribution | `BoardCatalog` (one board's view) | `CatalogQuery`, `CoverageMap`, `ExportFormat` | Board sees only `state=APPROVED` + `board_id` matches. Cross-board content visibility is OFF by default. |

### 3.3 Domain events

Cross-context communication is via these events. Each is a published record with `event_id`, `occurred_at`, `payload`. We do **not** introduce a message broker; events are emitted in-process as DB-backed work items, polled by a background worker (matches existing dev-03 task-sync pattern).

> **Telemetry note:** all domain events listed below are also tee'd to a cross-cutting telemetry sink (Cloud Logging / Cloud Monitoring). Telemetry is not a bounded context; it observes every event uniformly and is therefore not enumerated in the per-event consumer column.

| Event | Producer context | Consumer contexts | Trigger |
|---|---|---|---|
| `ExpectationVersioned` | Curriculum | Generation, Authoring | New `CurriculumVersion` row + diff against prior version |
| `ClassContextAvailable` | (External: ASGF + course_contents) | Generation | Teacher uploads new course material; new course content tagged to a class |
| `ArtifactGenerated` | Generation | Authoring | CGP run completes (DRAFT or PENDING_REVIEW state) |
| `AlignmentScored` | Generation | Authoring | Post-gen validator finishes — score is rendered inline in the Teacher Review Queue (M3-A); no separate validator dashboard. |
| `ArtifactApproved` | Authoring | Surface (Distribution queries by state at request time; no event subscription needed. If a catalog cache is later introduced, add a cache-invalidation event then.) | Teacher approves → state APPROVED |
| `ArtifactReClassified` | Curriculum | Authoring | CEG version cascade: a tagged SE changed; flag affected artifacts (only `change_severity = scope_substantive`) |
| `BoardCatalogQueried` | Distribution | — | Audit + rate-limit signal |

### 3.4 Anti-corruption layers

External systems are bounded behind ACLs to preserve our domain language:

- **Claude / OpenAI** → `AIEngineRouter` (existing in `app/services/ai_service.py`). Translates `GenerationRequest` → provider-specific API; never leaks provider model strings into domain code.
- **Google Classroom** → existing `app/services/google_classroom_*.py`. ACL already in place.
- **Ontario Ministry PDFs** → `CEGExtractor` (M0 batch 0b). Strictly inbound. Never used at runtime — only during periodic CEG rebuild jobs.

---

## 4. Architecture overview

### 4.1 Layered architecture (per context)

Every context follows the same internal layering — keeps the codebase predictable and reusable patterns transferable across contexts.

```
┌──────────────────────────────────────────────────────────────┐
│  API / Adapters                                              │
│  • FastAPI routers (REST)                                    │
│  • MCP tool handlers                                         │
│  • SSE streaming endpoints                                   │
│  • Background worker handlers                                │
├──────────────────────────────────────────────────────────────┤
│  Application Services (use cases)                            │
│  • RequestGeneration, ApproveArtifact, EmitSurfaces, etc.    │
│  • Orchestrate aggregates; emit domain events                │
├──────────────────────────────────────────────────────────────┤
│  Domain Layer                                                │
│  • Entities + aggregates + value objects                     │
│  • Domain services (pure logic — no I/O)                     │
│  • Domain events (records, no broker)                        │
├──────────────────────────────────────────────────────────────┤
│  Infrastructure                                              │
│  • SQLAlchemy repositories                                   │
│  • External API clients (Claude/OpenAI/GCS)                  │
│  • Cache (in-memory TTL — same pattern as phase-2 student/*) │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Generation pipeline data flow (the critical path)

```
1. User request                   2. Class context envelope     3. CEG retrieval
   • User identity + role            • Pull from:                  • Structured: by grade/subject/strand
   • Grade / subject / strand        ▸ course_contents             • Semantic: embedding match (pgvector)
   • Content type + difficulty       ▸ GC announcements (14d)      → list of OE + SE expectations
   • Optional: target SE codes       ▸ teacher email digest (30d)
                                     ▸ teacher artifact library
                                     → cited sources

4. Prompt construction            5. AI engine routing          6. Generation
   • Curriculum guardrail layer      • Claude Sonnet for          • Streaming SSE for long-form
   • Class-context layer (A1)          long-form (study guide,    • Sync for short artifacts
   • Voice overlay (A3)                sample test, assignment)   • Token usage logged
   • Persona overlay (A2)            • GPT-4o-mini for high-      • Voice module hash stamped
                                       volume (quiz, worksheet)

7. Post-gen validation            8. Persist                    9. Surface integration (A4)
   • Self-report check               • content_artifacts row     • If state = APPROVED:
   • Second-pass validator           • content_json + alignment    ▸ DCICoachCard emit
     (port phase-2                     metadata                     ▸ DigestBlock emit
      CurriculumMappingService)       • PDF render (deferred to     ▸ BridgeEntry emit
   • If alignment ≥ threshold:         on-demand)                   (best-effort; failure ≠ block)
     → state DRAFT                     • Domain event:
   • Else:                             ArtifactGenerated
     → state DRAFT + flagged
```

### 4.3 Integration with existing dev-03 systems

| Existing system | Role in CB-CMCP-001 | Touch point |
|---|---|---|
| `app/services/ai_service.py` | Reused as engine router; gain `class_context_envelope` + `voice_module_id` parameters | Extend, don't replace |
| `app/models/study_guide.py` | Becomes the `ContentArtifact` table (extended per D2) | Add columns: `se_codes` JSONB, `alignment_score`, `ceg_version`, `state`, `board_id`, `voice_module_hash`, `class_context_envelope_summary` |
| CB-ASGF-001 ingestion | Source for class-context envelope (A1) | Reuse pipeline; new `ClassContextResolver` calls into it |
| CB-PEDI-002 digest | Surface for Email Digest summary block (A4) | Add new block-renderer for `cb_cmcp_artifact_summary` |
| CB-DCI-001 | Surface for Daily Check-In coach card (A4) | Extend DCI ingest contract to accept artifact-derived cards |
| CB-BRIDGE-001 | Surface for "What child is learning" Bridge card (A4) | New card type + API + frontend component |
| CB-TASKSYNC-001 | Class assignments emit Tasks | When approved artifact assigned to class roster, emit `TaskCreated` |
| CB-TUTOR-001/002 Arc | Voice reference for A3 | Inherit voice rules; share `arc_voice_v*.txt` registry |
| Existing JWT + OAuth2 | Auth for MCP (port from phase-2) | Add `BOARD_ADMIN` / `CURRICULUM_ADMIN` roles |
| Existing SSE pattern (`/tutor`, `/asgf`) | Streaming UX for long-form generation | Reuse SSE plumbing |

---

## 5. Reuse inventory (port from phase-2 + extend in dev-03)

This is the load-bearing claim that lets CB-CMCP-001 ship in 9 months instead of 18. Each row is concrete code that exists today.

### 5.1 Port from `class-bridge-phase-2` `feature/phase-2`

| Asset | LOC | Maps to | Port batch |
|---|---|---|---|
| `app/models/curriculum.py` (`CurriculumExpectation`) | 28 | CEG aggregate root (extend) | M0 batch 0a |
| `app/data/curriculum_seed.py` | 334 | Seeding pattern (replace data with Gr 1–8) | M0 batch 0b |
| `app/api/routes/curriculum.py` | 218 | Curriculum read REST API | M0 batch 0a |
| `app/services/curriculum_mapping.py` (`CurriculumMappingService.annotate()`) | 141 | M1 second-pass alignment validator (D4) | M1 batch 1d |
| `app/services/parent_summary.py` (`ParentSummaryService.generate()`) | 116 | A2 Parent Companion ~70% (extend) | M1 batch 1f |
| `app/mcp/__init__.py` | 125 | MCP server scaffold | M2 batch 2a |
| `app/mcp/auth.py` | 155 | MCP JWT + RBAC | M2 batch 2a (extend with BOARD_ADMIN/CURRICULUM_ADMIN) |
| `app/mcp/resources/student.py` | 779 | A1 student-context envelope | M1 batch 1b |
| `app/mcp/tools/study.py` | 459 | Dedup (SHA-256 content-hash) + per-user rate-limit (10/min in-memory) pattern is reusable BUT is currently in-line per-endpoint, not extracted as a utility. **Port step:** extract to `app/services/cmcp/dedup_and_ratelimit.py` first, then call from M1-A request handler. Replace the endpoints with curriculum-guardrailed equivalents in M2 batch 2C. | M2 batch 2c |
| `app/mcp/tools/tutor.py` | 611 | Defer (relevant to end-user MCP, not board) | Out of M0–M4 scope |
| `app/mcp/tools/import_tools.py` | 403 | Out of CB-CMCP-001 scope | (covered by #2196) |

### 5.2 Already in dev-03 (extend, don't duplicate)

| Asset | Role |
|---|---|
| `app/services/ai_service.py` | Engine router; extend with envelope + voice |
| `app/models/study_guide.py` | Becomes `ContentArtifact` per D2 |
| `app/models/course_content.py` | Class-context source (A1) |
| ASGF ingestion services — `app/services/asgf_ingestion_service.py`, `app/services/asgf_service.py`, `app/services/asgf_assignment_service.py` | Class-context ingestion source (A1) — **primary integration point** (the entry path that turns uploads into class-context envelope material) |
| ASGF slide service — `app/services/asgf_slide_service.py` | Class-context ingestion source (A1) — **primary integration point** (slide-deck parsing feeds the envelope alongside ingestion) |
| ASGF pedi + learning-history services — `app/services/asgf_pedi_service.py`, `app/services/asgf_learning_history_service.py` | Class-context ingestion source (A1) — **primary integration point** (pedagogical signals + learning history shape envelope content) |
| ASGF cost / OCR / quiz / save services — `app/services/asgf_cost_service.py`, `app/services/asgf_ocr_service.py`, `app/services/asgf_quiz_service.py`, `app/services/asgf_save_service.py` | Class-context ingestion source (A1) — tangential (OCR + cost accounting + quiz/save flows are read-only references, not primary integration points) |
| `app/services/pedi_*` services | Email Digest summary block target (A4) |
| `app/services/dci_*` services | Daily Check-In coach card target (A4) |
| Bridge components (`frontend/src/components/bridge/*`) | Bridge entry render target (A4) |
| Tutor's `arc_voice_*` patterns (CB-TUTOR-001/002) | A3 voice reference |
| `app/services/tasks/task_sync_*` (CB-TASKSYNC-001) | Class assignment task emission |
| `app/db/database.py` + advisory-lock migration pattern | M0 schema migrations |
| Existing SSE patterns in `tutor.py` / `asgf` | Streaming UX (D6) |

---

## 6. UI/UX strategy

### 6.1 Inherit, don't invent

CB-CMCP-001 has **five new user-facing surfaces**. None gets a new design system — all inherit the existing Bridge / Fraunces serif heading / rust-accent / dark-pill primary CTA / warm-ivory-surface tokens from CB-THEME-001 + CB-BRIDGE-001 + CB-TUTOR-001. Reuse, not reinvent. The only new visual primitive is a **curriculum-code chip** (see §6.4).

### 6.2 The five surfaces

| Surface | Role | Inherits | Owner persona |
|---|---|---|---|
| **Generation request flow** | User picks grade/subject/strand → requests artifact (or accepts class-context-detected suggestion) | CB-ASGF-001 entry-point shape; Bridge tokens | Student / Parent / Teacher |
| **Teacher Review Queue** | Queue of `state=PENDING_REVIEW` artifacts; approve / edit / regenerate | Existing teacher portal layout; Bridge tokens; tutor inline-edit pattern | Teacher |
| **Parent Companion view** | Render the 5-section Parent Companion artifact; deep-link into Bridge | Bridge `/my-hub` card style; warm coaching tone (NOT Arc-led) | Parent |
| **Curriculum / SE picker** | Browse Ontario expectations by grade/subject/strand; pick SEs to anchor a request | New (table + tree) — uses Bridge spacing/typography | Teacher / Curriculum Admin |
| **Board Admin Dashboard** | Coverage map (strand × content-count heatmap); catalog browse; export | New (dashboard) — uses Bridge tokens + recharts (per CB-PEDI-002 pattern) | Board Admin |

### 6.3 User journey examples (Double Diamond informed)

**Maya (Grade 8 student, YRDSB) — "I want a quiz on linear equations":**

```
DISCOVER:  "I have a math test Thursday on linear equations"
DEFINE:    Request → grade/subject/strand prefilled from her enrolled course
DEVELOP:   System generates with class-context envelope (Mr. Chen's recent slides
           + GC announcement) → Arc-voiced quiz with worked examples
DELIVER:   Artifact appears in /tutor; auto-emits coach card to her parent's DCI
           tomorrow morning
```

**Priya (Grade 5 parent, YRDSB) — "How do I help with biodiversity?":**

```
DISCOVER:  Bridge "What Aarav is learning" card surfaces curriculum SEs A1.2-A1.3
DEFINE:    Tap → "Get a Parent Companion" CTA
DEVELOP:   Self-service generation, no teacher review (D3=C, self-study path)
           → 5-section Parent Companion (NOT a worksheet)
DELIVER:   Lands in next morning's Email Digest + persists in her Bridge view.
           Three coaching prompts she can use over dinner.
```

**Mr. Chen (Grade 7 teacher) — "I need a homework assignment":**

```
DISCOVER:  Class-context envelope auto-built from his uploads + GC announcements
DEFINE:    Curriculum picker shows SEs covered in last 14 days
DEVELOP:   Generate → review queue → he edits 2 lines → approve
DELIVER:   Auto-shared with class roster (CB-TASKSYNC-001 emits Tasks);
           coach card to each enrolled student's parent's DCI
```

**TDSB Curriculum Coordinator — "Show me Grade 9 Math coverage":**

```
DISCOVER:  REST: GET /api/board/{board_id}/coverage?grade=9&subject=MATH
DEFINE:    Coverage map: strand × approved-artifact-count heatmap
DEVELOP:   Click a strand → list of approved artifacts in that strand
DELIVER:   Signed CSV export (D7=B) for LMS import; LTI link-out stub for
           direct integration testing
```

### 6.4 Design tokens additions (one new primitive only)

Existing Bridge token system covers everything except the **curriculum-code chip**, which appears on every artifact. Single new primitive, semantic-color-keyed.

```css
/* curriculum-code chip — inherits from existing Bridge chip styles */
.cb-curriculum-chip {
  /* size: matches existing Bridge tag chip (token --chip-md) */
  /* color (light): --color-curriculum-bg (warm-ivory-tinted variant of --bridge-rust) */
  /* color (dark): --color-curriculum-bg-dark (matched to dark-mode rust palette) */
  /* type: --font-family-mono (tabular feel for codes like "B2.3") */
  /* contrast verified: ≥ 4.5:1 in both themes */
}
.cb-curriculum-chip--ministry { /* official Ministry code */ }
.cb-curriculum-chip--cb        { /* internal CB code (e.g., CB-G7-MATH-B2-SE3) */ }
.cb-curriculum-chip--inferred  { /* inferred via second-pass validator, not author-tagged */ }
```

### 6.5 Non-negotiable UX rules (from `ui-ux-pro-max` priority 1–2)

These apply to every new surface; reviewed at each stripe's `/pr-review` pass.

- **Accessibility (CRITICAL):** WCAG 4.5:1 contrast on every new surface; aria-labels on every icon-only button; screen-reader announcements on async state transitions (PENDING_REVIEW → APPROVED).
- **Touch & interaction (CRITICAL):** 44×44pt targets on all action buttons in the review queue and parent companion; loading feedback within 100ms of any tap; SSE streaming UI uses progressive content reveal (skeleton → token-by-token).
- **Reduced motion:** Voice-overlay typography scales with system text-size; SSE streaming respects `prefers-reduced-motion` (instant render instead of typewriter).
- **Color not the only indicator:** Curriculum chip variants (Ministry / CB / inferred) differ by **icon + label**, not color alone. Alignment-score badges differ by **shape + label**, not just red/yellow/green.

### 6.6 When to invoke `/bencium-innovative-ux-designer` and `/frontend-design`

Both skills are about distinctive production-grade UI and have **identical stated descriptions**, so the choice between them is operator preference — not a principled assignment. Either is appropriate at any of the high-stakes UI stripes; pairing with `/ui-ux-pro-max` (which covers patterns, tokens, accessibility, layout) is the load-bearing call.

Recommended pairing pattern:

- Always invoke `/ui-ux-pro-max` first on every UI stripe.
- Invoke EITHER `/bencium-innovative-ux-designer` OR `/frontend-design` (operator pick) at brand-defining stripes — primarily **M1-F Parent Companion render** (the brand-defining moment for parents) and **M3-H Board Admin Dashboard** (most freedom for distinctive layouts).
- If the surface is high-stakes and time allows, invoke both and pick the stronger output.

---

## 7. Batch plan — M0 through M5

Each batch is a coherent integration branch (`integrate/cb-cmcp-001-Mn-batch-Nx`) with **3–6 parallel stripes** that can ship in isolated worktrees. Per existing convention: 2× `/pr-review` per integration branch + lint+build+tests local before push.

### M0 — Foundation (target: June 2026)

Goal: CEG built and validated; cost model published; reviewer onboarded; M0 hard-gate decisions confirmed.

**Hard preconditions:** D1, D2, D3, D5, D7, D11 confirmed by user.

#### Batch M0-A — Schema + role extensions

| Stripe | Scope | Reuses |
|---|---|---|
| 0A-1 | DDL: `ceg_subjects`, `ceg_strands`, `ceg_expectations`, `curriculum_versions` (with `change_severity`). Embedding column: `vector(1536)` on PG via pgvector ext; on SQLite, store as `JSON` column with the embedding as a list of floats. Semantic-search query path uses `pgvector <=> ` operator on PG and a Python-side cosine-similarity computation on SQLite (acceptable for dev/test where corpus is small — Phase 1 ≤ ~2,000 expectations). Migration gates pgvector creation with `if "sqlite" not in settings.database_url`. Acceptance criteria for 0A-1 include round-trip test on BOTH PG + SQLite. | phase-2 `CurriculumExpectation` model (extend) |
| 0A-2 | Extend `study_guides` per D2: add `se_codes` JSONB, `alignment_score`, `ceg_version`, `state`, `board_id`, `voice_module_hash`, `class_context_envelope_summary`, `requested_persona` | dev-03 `study_guide.py` |
| 0A-3 | Auth: add `BOARD_ADMIN` + `CURRICULUM_ADMIN` to `UserRole` enum; RBAC matrix updates | dev-03 `app/api/deps.py` |
| 0A-4 | Idempotent migrations in `main.py` startup using existing `pg_try_advisory_lock` pattern; advisory lock IDs reserved (e.g., 4351) | dev-03 main.py migration block pattern |

**Stripe count:** 4. Parallelizable. **Tests:** schema migration round-trip on PG + SQLite.

#### Batch M0-B — CEG extraction pipeline

| Stripe | Scope | Reuses |
|---|---|---|
| 0B-1 | Port phase-2 `app/api/routes/curriculum.py` REST API (read-only) under feature flag | phase-2 |
| 0B-2 | Two-pass extractor (D5=B, **AI-side check only**): `cli/extract_ceg.py` — runs Claude twice with different prompts, diffs results, writes pending-review JSON. Note: this is the AI-side quality check; the OCT-certified curriculum-reviewer human-side check happens separately in stripe 0C-1. **Both are required** per D5=B; neither alone is sufficient for the ≥99% Ministry-code accuracy gate. | phase-2 `curriculum_seed.py` (pattern) |
| 0B-3a | Backend: `/api/ceg/admin/review/*` endpoints — list pending, accept, reject, edit (with audit log entries); RBAC requires `CURRICULUM_ADMIN` role | dev-03 admin route patterns |
| 0B-3b | Frontend: `/admin/ceg/review` page — table view of pending SEs, accept / reject / inline-edit; uses Bridge token styling | New (dev-03 admin patterns) |
| 0B-4 | Embedding generation backfill job: `cli/embed_ceg.py` — `text-embedding-3-small` per expectation; pgvector index | phase-2 mapping service (pattern) |
| 0B-5 | Phase-1 seed run: Gr 1–8 Math, Lang, Sci, Soc Studies — store source PDFs in private GCS bucket; commit extracted JSON to repo for audit | New |

**Stripe count:** 6. **Tests:** extractor round-trip on a small sample; review-interface RBAC; embedding lookup match accuracy (≥95% on sample queries).

#### Batch M0-C — Quality SLA + reviewer onboarding (process, not code)

| Stripe | Scope |
|---|---|
| 0C-1 | Hire / contract paid OCT-certified curriculum reviewer (~80h Phase 1) — owner: founder, not engineering |
| 0C-2 | Accuracy audit framework: `cli/audit_ceg.py` — sample 100 SEs, compare to Ministry source, compute Ministry-code accuracy; ≥99% gate |
| 0C-3 | Publish CEG accuracy report on launch alongside the `ceg_versions.released_at` row |

**Stripe count:** 3. Mostly process; one CLI tool.

#### Batch M0-D — Cost model document

| Stripe | Scope |
|---|---|
| 0D-1 | Published doc: `docs/design/CB-CMCP-001-cost-model.md` — token cost per content type × pilot/single-board/multi-board volume tiers; $/artifact projection; CB-ASGF-001 baseline anchor |

**Stripe count:** 1. No code.

**M0 acceptance gate (unlocks M1):** CEG live (Gr 1–8, ≥99% Ministry-code accuracy audited); cost model published; reviewer onboarded; D1/D2/D3/D5/D7/D11 confirmed.

---

### M1 — Generation Pipeline Alpha (target: July 2026)

Goal: First curriculum-aligned artifacts generated end-to-end with all four authenticity amendments wired up. Internal-only flag; not yet user-visible.

#### Batch M1-A — Guardrail Engine + prompt builders

| Stripe | Scope | Reuses |
|---|---|---|
| 1A-1 | `app/services/cmcp/guardrail_engine.py` — composes prompt: CEG SE list + class-context envelope + voice overlay + persona overlay | dev-03 `ai_service.py` (extend) |
| 1A-2 | New Pydantic schemas: `GenerationRequest`, `GenerationResult`, `AlignmentReport`; route at `/api/cmcp/generate` (gated behind feature flag `cmcp.enabled`, default OFF) | dev-03 schema patterns |
| 1A-3 | State machine on `content_artifacts.state` — implement transitions per DD §6.1 + new `SELF_STUDY` state from D3=C | dev-03 state-machine patterns |

**Stripe count:** 3.

#### Batch M1-B — A1 Class-Context Blending

| Stripe | Scope | Reuses |
|---|---|---|
| 1B-1 | Port phase-2 `app/mcp/resources/student.py` to `app/services/cmcp/student_context.py` (rename, drop the MCP routes — they belong in M2) | phase-2 |
| 1B-2 | `app/services/cmcp/class_context_resolver.py` — pulls (a) course_contents, (b) GC announcements 14d, (c) teacher email digest 30d, (d) teacher artifact library matching SEs; emits structured envelope with citations | dev-03 ASGF + GC + PEDI services |
| 1B-3 | Inject envelope into guardrail prompt per A1 binding requirement; record `envelope_size`, `cited_source_count`, `fallback_used` per generation | M1-A integration |
| 1B-4 | Frontend "generic — no class-vocab anchoring" badge component (Bridge token-only styling) | New |

**Stripe count:** 4. **Tests:** envelope size > 0 in ≥70% of test generations (M3 acceptance threshold).

#### Batch M1-C — A3 Arc Voice Overlay

| Stripe | Scope | Reuses |
|---|---|---|
| 1C-1 | `prompt_modules/voice/` registry — `arc_voice_v1.txt` (student-facing), `professional_v1.txt` (teacher-facing), `parent_coach_v1.txt` (Parent Companion); admin endpoint to swap active version without code deploy | CB-TUTOR-001/002 voice patterns |
| 1C-2 | Voice module hash stamped on every artifact's metadata; `voice_module_hash` column written | New |
| 1C-3 | Audit job: weekly random-sample of 50 artifacts checked for voice consistency vs CB-TUTOR-001 reference | New |

**Stripe count:** 3.

#### Batch M1-D — Validator (D4=C in M1)

| Stripe | Scope | Reuses |
|---|---|---|
| 1D-1 | Port phase-2 `app/services/curriculum_mapping.py` → `app/services/cmcp/alignment_validator.py` | phase-2 (direct port) |
| 1D-2 | First-pass: model self-report (`se_codes_covered`); Second-pass: validator runs `CurriculumMappingService.annotate()` on output and computes overlap | New (compose) |
| 1D-3 | `alignment_score` written to artifact; if < 0.80 → `flag_for_review = True` | New |

**Stripe count:** 3. (Embedding-similarity validator deferred to M3 batch 3I per D4.)

#### Batch M1-E — Streaming UX (D6=B)

| Stripe | Scope | Reuses |
|---|---|---|
| 1E-1 | SSE endpoint per content type: long-form (study guide, sample test, assignment) streams; short-form (quiz, worksheet) sync | dev-03 SSE pattern from tutor.py |
| 1E-2 | Per-content-type latency SLA telemetry (Quiz < 8s, Worksheet < 12s, Study Guide < 25s, Sample Test < 40s, Assignment < 30s); Cloud Monitoring dashboard + SLO alert (10% over target sustained 5 min) paging on-call. Acceptance: dashboard live + alert firing in staging before stripe closes. | dev-03 telemetry patterns |
| 1E-3 | Frontend streaming consumer hook + skeleton fallback that respects `prefers-reduced-motion` | dev-03 streaming hooks |

**Stripe count:** 3.

#### Batch M1-F — A2 Parent Companion (highest-leverage reuse)

| Stripe | Scope | Reuses |
|---|---|---|
| 1F-1 | Port phase-2 `parent_summary.py` → `app/services/cmcp/parent_companion_service.py` | **phase-2 (~70% reuse)** |
| 1F-2 | Extend prompt for 5-section structure: SE explanation, talking points (3–5, configurable), coaching prompts, "how to help without giving the answer", Bridge deep-link | New (extend) |
| 1F-3 | New Pydantic response with 5 fields; auto-emit on `state=APPROVED` for student-facing artifacts within 60s | New |
| 1F-4 | Frontend Parent Companion render: invoke `/frontend-design` skill for distinctive visual treatment of the 5 sections; uses Bridge tokens; warm coaching tone (NOT Arc-led) | New |
| 1F-5 | RBAC matrix update per A2 (FR-05 amendment) — STUDENT cannot access Parent Companion | dev-03 deps |

**Stripe count:** 5. **Acceptance:** every student-facing approved artifact has a Parent Companion derivative ≤60s; never includes answer key (auditable lint).

**M1 acceptance gate (unlocks M2):** Internal end-to-end generation works for all 5 content types + Parent Companion derivative; alignment validator hits ≥80% accuracy threshold; voice-overlay audit passes; ≥70% of test generations carry a populated class-context envelope.

---

### M2 — CB-MCP Server v1.0 (target: August 2026)

Goal: MCP server live, internal testing complete. **Per D1=C: end-user MCP only; board MCP deferred.**

**Sequencing flexibility:** Batch M2-A (port phase-2 MCP scaffold) has no dependency on the M1 generation pipeline — it can be developed in parallel with M1 to reduce critical path. Only batch M2-B (CB-CMCP-specific MCP tools) depends on M1-A. If parallelism is available, start M2-A as soon as M0 lands.

#### Batch M2-A — Port phase-2 MCP scaffold (#2191)

| Stripe | Scope | Reuses |
|---|---|---|
| 2A-1 | Port `app/mcp/__init__.py` + `app/mcp/auth.py` to dev-03 (rename roles to add CB-CMCP additions) | phase-2 |
| 2A-2 | Port `app/mcp/routes.py` + `app/mcp/tools/*` (defer tutor/import per scope) | phase-2 |
| 2A-3 | New `BOARD_ADMIN` + `CURRICULUM_ADMIN` role wiring; RBAC matrix per DD §5.3 | New |

**Stripe count:** 3. **Note:** this also closes #2191 (or significantly de-scopes it).

#### Batch M2-B — CB-CMCP-001-specific MCP tools

| Stripe | Scope | Reuses |
|---|---|---|
| 2B-1 | `get_expectations` MCP tool — wraps the M0-B REST API | M1-A |
| 2B-2 | `get_artifact` MCP tool — role-scoped retrieval | M1-A |
| 2B-3 | `list_catalog` MCP tool — paginated, role-scoped, filtered | M1-A |
| 2B-4 | `generate_content` MCP tool — wraps M1 CGP via async submission; supersedes phase-2 `mcp_generate_*` per the #908 / #2193 cross-link | phase-2 dedup/rate-limit pattern |

**Stripe count:** 4. **Acceptance:** Claude Desktop config doc, end-to-end test from Claude Desktop to artifact retrieval.

**M2 acceptance gate (unlocks M3):** MCP server running on Cloud Run; all M2-B tools available; internal QA pass; #2191 closed.

---

### M3 — Workflow + Surface Integration (target: September 2026)

Goal: Teacher review workflow live; Bridge / DCI / Digest integration shipped; first user-visible flag ramp.

**Sequencing flexibility:** Batch M3-B (Self-study path implementation, D3=C) only depends on the M1 state machine — not on the M3-A teacher-review queue. It can ship as early as late M2 to derisk the D3 decision and validate the SELF_STUDY state-machine path before M3-A is built.

#### Batch M3-A — Teacher Review Queue UI

| Stripe | Scope | Reuses |
|---|---|---|
| 3A-1 | Backend: `/api/cmcp/review/*` — list pending, get artifact for edit, edit-delta, approve, reject, regenerate | M1 state machine |
| 3A-2 | Frontend: `/teacher/review` page — queue list, artifact detail, inline edit; invoke `/ui-ux-pro-max` for review-queue table patterns | dev-03 teacher portal layout |
| 3A-3 | SE-tag editor (add/remove/correct curriculum chips) — uses curriculum chip primitive from §6.4 | New |
| 3A-4 | One-click regeneration with adjusted parameters | M1-A |

**Stripe count:** 4.

#### Batch M3-B — Self-study path implementation (D3=C)

| Stripe | Scope | Reuses |
|---|---|---|
| 3B-1 | New `state=SELF_STUDY` skips PENDING_REVIEW for student/parent self-initiated requests | M1 state machine |
| 3B-2 | "AI-generated, not teacher-approved" badge component — color-not-the-only-indicator (icon + label) | New |
| 3B-3 | RBAC: SELF_STUDY artifacts visible only to requestor + their parent/child | M2-A |

**Stripe count:** 3.

#### Batch M3-C — Surface Integration A4 (Bridge / DCI / Digest)

| Stripe | Scope | Reuses |
|---|---|---|
| 3C-1 | `app/services/cmcp/surface_dispatcher.py` — fan-out on `ArtifactApproved` event; emits 3 derivatives best-effort with retry | dev-03 worker patterns |
| 3C-2 | DCI coach card payload — extend CB-DCI-001 ingest contract; new `cb_cmcp_coach_card` block type | CB-DCI-001 (extend) |
| 3C-3 | Digest summary block — new `cb_cmcp_artifact_summary` renderer in `app/services/digest_block_renderers.py` | CB-PEDI-002 (extend) |
| 3C-4 | Bridge "What [child] is learning" card type — new card component + API endpoint + frontend slot in BridgePage | CB-BRIDGE-001 (extend) |
| 3C-5 | Telemetry: 24h-surface rate, render rate, CTR per surface | dev-03 telemetry |

**Stripe count:** 5.

#### Batch M3-D — Class assignment + CB-TASKSYNC integration

| Stripe | Scope | Reuses |
|---|---|---|
| 3D-1 | Approved artifact → assign to class roster → emit `TaskCreated` events for each enrolled student | CB-TASKSYNC-001 |
| 3D-2 | XP eligibility for completed assigned artifacts | dev-03 XP service |

**Stripe count:** 2.

#### Batch M3-E — Board catalog REST + signed CSV (D7=B)

| Stripe | Scope | Reuses |
|---|---|---|
| 3E-1 | `/api/board/{id}/catalog` REST endpoint — `BOARD_ADMIN`-scoped | M2-A auth |
| 3E-2 | Coverage map service: strand × content-count aggregation | New |
| 3E-3 | Signed CSV export — TTL-limited GCS signed URLs | dev-03 GCS pattern |
| 3E-4 | LTI 1.3 link-out stub (deep-link only; full LTI launch deferred) | New |

**Stripe count:** 4.

#### Batch M3-F — Curriculum / SE picker (Teacher / Curriculum Admin)

| Stripe | Scope | Reuses |
|---|---|---|
| 3F-1 | Frontend curriculum browser: tree (subject → strand → topic) + table; SE selection multi-pick | M0-B routes + new UI |
| 3F-2 | Hooks into the generation request flow as an alternative to grade/subject/strand-only triple | M1-A |

**Stripe count:** 2.

#### Batch M3-G — CEG version cascade (D9=B)

| Stripe | Scope | Reuses |
|---|---|---|
| 3G-1 | `change_severity` enum on `curriculum_versions` diff; classifier sets `wording_only` vs `scope_substantive` | New |
| 3G-2 | When a `scope_substantive` SE change lands, flag affected approved artifacts → state=PENDING_REVIEW | M1 state machine |
| 3G-3 | Notification to artifact owner via existing CB-MCNI | dev-03 |

**Stripe count:** 3.

#### Batch M3-H — Board Admin Dashboard

| Stripe | Scope | Reuses |
|---|---|---|
| 3H-1 | Frontend `/board/dashboard` — coverage heatmap (strand × grade); invoke `/bencium-innovative-ux-designer` for distinctive layout | M3-E REST + recharts |
| 3H-2 | Catalog browse + filter + signed-CSV download | M3-E |

**Stripe count:** 2.

#### Batch M3-I — Validator second-pass (D4=B in M3)

| Stripe | Scope | Reuses |
|---|---|---|
| 3I-1 | Embedding-similarity validator: embed each generated section + each SE expectation; cosine ≥ threshold | M0 pgvector |
| 3I-2 | Composes with M1-D validator; both must pass | M1-D |

**Stripe count:** 2.

**M3 acceptance gate (unlocks M4):** Teacher review queue functional; Bridge / DCI / Digest integration shipped; flag `cmcp.enabled` ramped to internal-staff; ≥80% of approved artifacts surface in DCI within 24h; CTR ≥15% Bridge entry.

---

### M4 — School Board Pilot (target: October 2026)

Goal: Two YRDSB pilot schools live; 200+ artifacts generated; pilot feedback collected.

#### Batch M4-A — Pilot board onboarding playbook

| Stripe | Scope |
|---|---|
| 4A-1 | DSA template + signing workflow (legal artifact) — owner: founder |
| 4A-2 | Service-account provisioning for board IT (`BOARD_ADMIN` token) |
| 4A-3 | Sandbox env spin-up + integration testing playbook |

**Stripe count:** 3.

#### Batch M4-B — Pilot operations

| Stripe | Scope | Reuses |
|---|---|---|
| 4B-1 | Bi-weekly check-in cadence + feedback intake form | New |
| 4B-2 | Pilot telemetry dashboard: artifact volume, review-to-approval time, alignment-score distribution, edit rate | M1 telemetry |
| 4B-3 | Success-criteria audit at +60d / +90d (≥70% first-review approval, ≥80% teacher satisfaction, ≥200 artifacts) | New |

**Stripe count:** 3.

#### Batch M4-C — Production hardening

| Stripe | Scope | Reuses |
|---|---|---|
| 4C-1 | Board catalog rate-limit enforcement (300 req/min per board service account, per NFR-08) | M2-A rate-limit pattern |
| 4C-2 | MFIPPA / Bill 194 audit-log review pass; Cloud Logging retention validated (12 months for MCP audit, 90d for generation logs) | dev-03 audit pattern |
| 4C-3 | DR runbook: Cloud SQL HA failover test; CEG re-extraction from PDF source playbook | dev-03 patterns |

**Stripe count:** 3.

**M4 acceptance gate (unlocks M5):** Pilot success criteria met; flag `cmcp.enabled = on_for_all`; revenue conversation with pilot boards opened.

---

### M5 — Phase 2 Curriculum (target: Q1 2027)

Goal: Coverage expanded to Gr 9–12, FSL, Arts, HPE, French interface.

#### Batch M5-A — Gr 9–12 CEG extraction

| Stripe | Scope | Reuses |
|---|---|---|
| 5A-1 | Re-run M0-B extractor on Gr 9–12 Ministry PDFs | M0-B |
| 5A-2 | OCT reviewer second pass on secondary curriculum | M0-C |
| 5A-3 | Embedding refresh | M0-B |

**Stripe count:** 3.

#### Batches M5-B / M5-C / M5-D — FSL, Arts, HPE, French interface

(Stripe-level breakdown deferred to M4 close — same shape as M5-A per subject area.)

---

## 8. Rollout strategy

### 8.1 Feature flag ladder

Single root flag `cmcp.enabled` (default OFF) with variant gating:

```
off → internal_only → staff → on_5 → on_25 → on_100 → on_for_all
```

- **internal_only**: flagged users (engineering + curriculum admin)
- **staff**: ClassBridge employees
- **on_5 / 25 / 100**: percentage rollout to all users
- **on_for_all**: drop the flag; remove dead-code paths in next cleanup PR

### 8.2 Sub-flags

- `cmcp.board_mcp.enabled` — defaults OFF; flips ON only when a board signs DSA (per D1=C)
- `cmcp.parent_companion.enabled` — defaults OFF until M1-F lands + UX QA pass
- `cmcp.streaming.enabled` — defaults OFF until M1-E lands; allows fallback to sync if SSE issues arise

### 8.3 Telemetry per amendment

| Amendment | Metric | Target | Source |
|---|---|---|---|
| A1 | % of generations with envelope_size > 0 | ≥70% by M3 | — |
| A1 | Cited_source_count per artifact | ≥1 average | — |
| A2 | Parent Companion adoption (DCI/Digest open + click) | ≥30% in 7d | — |
| A2 | Parent Companion render correctness (no answer key leak) | 100% | — |
| A3 | Voice module hash present on student-facing | 100% | — |
| A3 | Voice consistency audit (sample 50) | ≥90% inter-rater | — |
| A4 | Approved artifacts surfaced in DCI within 24h | ≥80% | — |
| A4 | Bridge entry CTR | ≥15% | — |
| A4 | Digest summary block render rate | ≥95% | — |
| (Cross-cutting) | Generation latency P95 by content_type | per-type SLA: Quiz < 8s · Worksheet < 12s · Study Guide < 25s · Sample Test < 40s · Assignment < 30s | Cloud Run request latency + custom metric stamped with `content_type` at request time |

### 8.4 Kill-switch

If `cmcp.enabled` is flipped OFF mid-ramp, all generation requests fall back to existing CB-ASGF-001 / Tutor flows (no curriculum-aligned generation). Approved artifacts already in `study_guides` continue to render with their captured `voice_module_hash` + `ceg_version` — no regression.

---

## 9. Acceptance gates (cumulative)

| Gate | Unlocks | Required |
|---|---|---|
| **M0 → M1** | Generation pipeline build | CEG live (Gr 1–8, ≥99% accuracy); cost model published; reviewer onboarded; D1/D2/D3/D5/D7/D11 confirmed |
| **M1 → M2** | MCP server build | E2E generation works; alignment validator ≥80%; voice audit passes; envelope ≥70% on test corpus; **per-content-type latency P95 SLAs holding (Cloud Monitoring dashboard live + alerts firing on 10%-over-target sustained 5 min)** |
| **M2 → M3** | Workflow + surfaces | **End-user MCP** live on Cloud Run (per D1=C, board MCP deferred); #2191 closed; internal QA pass |
| **M3 → M4** | Pilot opens | Teacher review functional; Bridge/DCI/Digest integration live; flag ramped to staff; A4 surface KPIs hit |
| **M4 → M5** | Phase 2 expansion | Pilot success criteria met; on_for_all ramp |

---

## 10. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CEG extraction misreads Ministry codes | Medium | High | D5=B two-pass + OCT reviewer + ≥99% accuracy gate |
| Class-context envelope leaks PII into prompts | Medium | High | A1 envelope structure scrubs at the resolver layer; PII linter on every envelope before injection |
| Parent Companion accidentally ships answer keys | Medium | High | Lint check on Parent Companion JSON; audit log; flag ON only after lint passes 100% on test corpus |
| Voice overlay drifts from CB-TUTOR-001 reference | Low | Medium | Weekly audit (M1-C-3) + voice version pinning per artifact |
| MCP server overwhelmed by board service accounts | Low | High | Per-client rate limit (300 req/min); Cloud Run autoscale max 20; alert on auth-failure spike |
| Board never signs DSA — CB-MCP value unrealized | Medium | High | D11 — interviews in parallel with M0; B2C value via Authenticity Layer is independent |
| Curriculum revision floods teacher re-review queue | Medium | Medium | D9=B severity classifier; only `scope_substantive` flags |
| Streaming SSE breaks for slow networks | Low | Medium | `cmcp.streaming.enabled` sub-flag; sync fallback for short artifacts |
| Latency SLA breach goes unnoticed | Medium | Medium | M1-E 1E-2 ships an SLO alert (10% over target sustained 5 min) → page on-call. Streaming sub-flag `cmcp.streaming.enabled` allows fallback to sync UX if SSE infra issues arise. |
| Cost overrun mid-M1 | Medium | Medium | D8=B cost model; per-artifact spend cap as backstop |
| User changes D2 (study_guides extension vs new content_artifacts) after M0 starts | Low (gated) | High | D2 is a hard precondition for M0 batch 0a; once locked, this risk is moot. If reversed mid-flight, dual-write window required during table migration; cost is multi-week. |

---

## 11. Out of scope (deferred / explicitly not in CB-CMCP-001)

- IEP-specific differentiation (D10=B → separate Phase 2 epic with SEA/SERT/MFIPPA review)
- French-language curriculum (M5)
- Textbook / third-party content integration (future PRD)
- Student performance analytics beyond access logs (future PRD)
- Adaptive difficulty engine (future PRD; depends on student performance feedback loop)
- LTI 1.3 full launch (M3-E ships link-out stub only; full LTI = Phase 3)
- D2L Brightspace / Edsby native integration (Phase 3)
- Premium content packs / monetization (Phase 2)
- EQAO alignment (Phase 2)
- Multi-agent curriculum gap-filling orchestration (Phase 3)

---

## 12. References

- PRD v1.0 + v1.1 + DD v1.0 (`Requirement/Claude-ai-generated/CB-CMCP-001-*.docx`)
- Mentor review plan (`C:\Users\tgnan\.claude\plans\nifty-crunching-squid.md`)
- Requirements §6.150 (`requirements/features-part7.md`)
- Epic #4351; sub-issues #4352–#4355 + #4361–#4371
- Phase-2 source (`c:\dev\emai\class-bridge-phase-2` `feature/phase-2`)
- Reuse map: epic body §"Phase-2 port candidates"
- CB-ASGF-001 epic #3390 (class-context ingestion source)
- CB-TUTOR-001 / CB-TUTOR-002 (Arc voice reference)
- CB-BRIDGE-001 / CB-DCI-001 / CB-PEDI-002 (Surface targets for A4)
- CB-TASKSYNC-001 (assignment task emission)
- VASP / DTAP epics #802 / #803 (board pilot non-technical predecessor)
