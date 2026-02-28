# /emai-req - ClassBridge Requirement Review & Planning

Review, analyze, and plan requirements for the ClassBridge (EMAI) platform with feedback, feasibility assessment, priority/phase recommendations, GitHub issue(s) creation, REQUIREMENTS.md updates, and detailed implementation planning, structure the plan so tasks can run in parallel Claude sessions with minimal merge conflicts. . **Does not include coding** — ends at planning stage.

## Usage

`/emai-req <description of the requirement>`

Examples:

- `/emai-req Add dark mode toggle to the app`
- `/emai-req Parents should receive weekly progress summaries`
- `/emai-req Implement student self-enrollment for courses`

## Instructions

Follow all 8 steps in order. Present findings to the user at each major checkpoint.

**IMPORTANT:** This skill is for requirement analysis and planning ONLY. It ends after creating a detailed implementation plan and updating GitHub issues. DO NOT proceed to coding — implementation should be done separately after plan review.

---

### Step 1: Review the Requirement

1. Read the requirements files to understand the current feature set, phases, and conventions. The requirements are split across multiple files:
   - `REQUIREMENTS.md` — Index + overview (sections 1-5)
   - `requirements/features-part1.md` — §6.1-6.14 (core features: AI, users, courses, content, analytics, comms, teachers, tasks, audit)
   - `requirements/features-part2.md` — §6.15-6.26 (UI/auth: themes, layout, search, mobile, security, multi-role, lifecycle, password reset)
   - `requirements/features-part3.md` — §6.27-6.50 (extended: messaging, teacher linking, roster, admin, onboarding, verification, course planning, emails)
   - `requirements/dashboards.md` — §7 (role-based dashboards)
   - `requirements/roadmap.md` — §8 (phased roadmap with progress checklists)
   - `requirements/mobile.md` — §9 (mobile app)
   - `requirements/technical.md` — §10-11 (architecture, API endpoints, NFRs, KPIs)
   - `requirements/tracking.md` — §12-13 (GitHub issues, dev setup)
     Read the index file first, then the specific files relevant to the requirement being analyzed. You do NOT need to read all files — only those relevant to the requirement.
2. Read relevant source code to understand what exists today:
   - Backend: models (`app/models/`), routes (`app/api/routes/`), schemas (`app/schemas/`), services (`app/services/`)
   - Frontend: pages (`frontend/src/pages/`), components (`frontend/src/components/`), API client (`frontend/src/api/client.ts`)
3. Search for related GitHub issues:
   ```bash
   gh issue list --repo theepangnani/emai-dev-03 --state open --search "<keywords>" --json number,title,state --jq '.[] | "#\(.number) \(.title) (\(.state))"'
   gh issue list --repo theepangnani/emai-dev-03 --state closed --search "<keywords>" --limit 10 --json number,title,state --jq '.[] | "#\(.number) \(.title) (\(.state))"'
   ```
4. Rewrite the requirement in structured format:

   ```
   As a <role>, I want to <action> so that <benefit>.

   Acceptance Criteria:
   - <specific, testable criterion>
   - <specific, testable criterion>

   Scope:
   In scope: <what's included>
   Out of scope: <what's excluded>
   ```

---

### Step 2: Analyze

Perform a thorough technical analysis:

1. **Current State**: What exists today? Is this fully new, partially implemented, or a gap in existing functionality?
2. **Technical Impact**: Which layers are affected?
   - Database: new tables, new columns, migrations
   - Backend: models, schemas, routes, services
   - Frontend: pages, components, CSS, API client
3. **Dependencies**: What other features, issues, or infrastructure does this depend on?
4. **Effort Estimate**:
   - **Small** (1-3 files): Simple addition, single endpoint + UI tweak
   - **Medium** (4-8 files): New feature touching backend + frontend
   - **Large** (9+ files): Cross-cutting feature, new domain, major refactor
5. **Affected File Count**: List the specific files that would need changes

---

### Step 3: Provide Feedback

Give honest, constructive feedback on the requirement:

1. **Clarity**: Is the requirement well-defined? Are there ambiguities?
2. **Completeness**: Are there missing acceptance criteria or edge cases?
3. **User Value**: How much does this benefit end users? Which roles benefit most?
4. **Alignment**: Does this align with the project's current phase and goals?
5. **Suggestions**: Propose improvements, simplifications, or alternative approaches
6. **Potential Issues**: Flag any concerns:
   - Security implications (FERPA/PIPEDA, auth, data access)
   - Performance concerns (N+1 queries, large payloads, expensive operations)
   - Cross-DB compatibility (SQLite vs PostgreSQL differences)
   - Breaking changes to existing functionality

---

### Step 4: Provide Recommendation and Feasibility

Assess whether and how to proceed:

1. **Feasibility Rating**:
   - **Straightforward**: Can be implemented with existing patterns and infrastructure
   - **Moderate**: Requires some new patterns or infrastructure but well-understood
   - **Complex**: Requires significant new infrastructure, external integrations, or architectural changes
   - **Not Feasible (currently)**: Blocked by missing infrastructure, external dependencies, or architectural limitations

2. **Recommendation**: One of:
   - **Implement as described**: Requirement is clear, feasible, and valuable
   - **Implement with modifications**: Good idea but needs scope/approach adjustments (explain what)
   - **Split into phases**: Too large for a single implementation pass (propose breakdown)
   - **Defer**: Not the right time — explain why and what should come first
   - **Decline**: Not aligned with project goals or not feasible

3. **Risk Assessment**:
   - What could go wrong?
   - What are the unknowns?
   - What's the rollback plan if something breaks?

---

### Step 5: Recommend Priority and Phase

Assign priority and phase based on complexity and value:

**Priority** (compare against current open issues):
| Level | Criteria |
|-------|----------|
| **P0 — Critical** | Blocks users, data loss risk, security vulnerability |
| **P1 — High** | Core feature gap, multiple users affected, enables other work |
| **P2 — Medium** | Nice-to-have improvement, single-role benefit, moderate effort |
| **P3 — Low** | Polish, edge case, future-phase prep |

**Phase** (based on REQUIREMENTS.md roadmap):
| Phase | Criteria |
|-------|----------|
| **Phase 1 (MVP)** | Core functionality needed for initial launch |
| **Phase 1.5** | Essential improvements discovered during Phase 1 |
| **Phase 2** | Enhanced features, analytics, integrations |
| **Phase 3** | Advanced AI, automation, scale features |
| **Phase 4** | Enterprise, multi-tenant, premium features |

**Present the full analysis to the user:**

```
============================================
  REQUIREMENT ANALYSIS: <short title>
============================================

REFINED REQUIREMENT
  As a <role>, I want to <action> so that <benefit>.

  Acceptance Criteria:
  - <criterion>

CURRENT STATE
  - <what exists>
  - <what's missing>

FEEDBACK
  - <clarity, completeness, suggestions>

FEASIBILITY: <Straightforward / Moderate / Complex / Not Feasible>
  <explanation>

RECOMMENDATION: <Implement / Modify / Split / Defer / Decline>
  <explanation>

PRIORITY: <P0 / P1 / P2 / P3> — <rationale>
PHASE: <Phase 1 / 1.5 / 2 / 3 / 4> — <rationale>

EFFORT: <Small / Medium / Large> (~<N> files)

RISKS
  - <risk 1>
  - <risk 2>

IMPLEMENTATION PLAN
  1. <step — file(s)>
  2. <step — file(s)>
  3. <step — file(s)>

RELATED ISSUES
  - #<number>: <title> (<open/closed>)
============================================
```

**Wait for user approval before proceeding to Steps 6 and 7.**

---

### Step 6: Create GitHub Issues

Only after user approval. Do not create duplicates — check existing issues first.

1. If a **duplicate** exists: update the existing issue with `gh issue edit`
2. If **partially covered**: add missing criteria to existing issue
3. If **new**: create actionable issues

Break large requirements into multiple issues (one per logical unit: backend, frontend, etc.).

```bash
gh issue create --repo theepangnani/emai-dev-03 --title "<title>" --body "$(cat <<'EOF'
## Context
<Brief description and link to requirement>

## Priority
<P0/P1/P2/P3> — <rationale>

## Phase
<Phase N> — <rationale>

## Acceptance Criteria
- [ ] <specific, testable criterion>
- [ ] <specific, testable criterion>

## Implementation Plan
- <step 1>
- <step 2>

## Technical Notes
- <relevant implementation details>
- <affected files or components>

## Dependencies
- <other issues this depends on, if any>

## Feasibility
<Straightforward / Moderate / Complex>
EOF
)"
```

Use labels: `enhancement`, `bug`, `backend`, `frontend`, `database`, `priority:high`, `priority:medium`, `priority:low`

---

### Step 7: Update REQUIREMENTS.md

Only after user approval:

1. Add or update the relevant section in `REQUIREMENTS.md`
2. Follow existing conventions:
   - Same heading hierarchy and table formats as other sections
   - Mark status: `- IMPLEMENTED`, `- PARTIAL`, or no suffix for planned
   - Include data model changes with field names and types
   - Include endpoint definitions (method, path, description)
   - Include role-based access rules
3. Preserve existing content — only add/modify what's needed
4. Update the **Progress Checklist** section:
   - `- [ ]` for planned features
   - `- [x]` for implemented features (with `(IMPLEMENTED)` suffix)
5. Add new GitHub issue numbers to the issue tracking section
6. Commit the changes

**After completion, report:**

```
============================================
  REQUIREMENT TRACKED
============================================

REQUIREMENTS.md: <updated section>
Priority: <P0/P1/P2/P3>
Phase: <Phase N>

Issues created/updated:
  - #<number>: <title> (NEW / UPDATED)

Next steps:
  1. <what to implement first>
  2. <follow-up items>
============================================
```

---

### Step 8: Create Design and Implementation Plan

After REQUIREMENTS.md and GitHub issues are created/updated, create a detailed design and implementation plan:

1. **Architecture & Design Decisions**:
   - Database schema changes (new tables, columns, indexes, migrations)
   - API contract design (endpoints, request/response schemas, status codes)
   - Frontend component hierarchy and data flow
   - State management approach (local state, context, query cache)
   - Security considerations (auth, authorization, data validation)
   - Performance optimization strategies (caching, pagination, eager loading)

2. **Implementation Sequence**:
   - **Backend** (in order):
     - [ ] Database migration in `main.py` startup block
     - [ ] SQLAlchemy models in `app/models/`
     - [ ] Pydantic schemas in `app/schemas/`
     - [ ] Service layer logic in `app/services/`
     - [ ] API routes in `app/api/routes/`
     - [ ] Unit tests in `tests/`
   - **Frontend** (in order):
     - [ ] API client methods in `frontend/src/api/client.ts`
     - [ ] Shared components in `frontend/src/components/`
     - [ ] Page components in `frontend/src/pages/`
     - [ ] CSS styling updates
     - [ ] Integration points with existing features

3. **File-by-File Plan**:
   List each file to be created/modified with specific changes:

   ```
   File: app/models/example.py
   Action: CREATE
   Changes:
     - Add ExampleModel with fields: id, name, user_id, created_at
     - Add relationship to User model
     - Include __repr__ for debugging

   File: app/api/routes/example.py
   Action: MODIFY
   Changes:
     - Add POST /api/examples endpoint
     - Add GET /api/examples/{id} endpoint
     - Implement role-based access control
   ```

4. **Testing Strategy**:
   - Unit test coverage plan (models, schemas, services, routes)
   - Integration test scenarios (API endpoint flows)
   - Frontend component test plan (if applicable)
   - Manual testing checklist (user flows, edge cases)

5. **Risks & Mitigation**:
   - Identify potential breaking changes
   - Database migration rollback plan
   - Cross-DB compatibility verification steps
   - Performance testing requirements

**Update GitHub issues** with the detailed implementation plan:

```bash
gh issue edit <number> --body "$(cat <<'EOF'
[existing content]

## Detailed Implementation Plan

### Architecture Decisions
- <decision 1>
- <decision 2>

### Implementation Sequence
**Backend:**
- [ ] Migration: <description>
- [ ] Model: <description>
- [ ] Schema: <description>
- [ ] Service: <description>
- [ ] Route: <description>
- [ ] Tests: <description>

**Frontend:**
- [ ] API client: <description>
- [ ] Component: <description>
- [ ] Page: <description>
- [ ] CSS: <description>

### File Changes
- `app/models/example.py` (CREATE): <changes>
- `app/api/routes/example.py` (MODIFY): <changes>

### Testing Plan
- <test scenario 1>
- <test scenario 2>

### Risks
- <risk + mitigation>
EOF
)"
```

**After planning, report:**

```
============================================
  DESIGN & IMPLEMENTATION PLAN CREATED
============================================

ARCHITECTURE DECISIONS
  - <key decision 1>
  - <key decision 2>

FILES TO BE CHANGED
  - CREATE: <file> — <purpose>
  - MODIFY: <file> — <purpose>

IMPLEMENTATION SEQUENCE
  Backend: <N> steps
  Frontend: <N> steps
  Tests: <N> scenarios

GITHUB ISSUES UPDATED
  - #<number>: Added detailed implementation plan

READY FOR IMPLEMENTATION
  The requirement is fully analyzed, tracked, and planned.
  Implementation can proceed following the detailed plan.
============================================
```

**DO NOT START CODING.** The skill ends here. Implementation should be done separately after plan review.

---

## Quick Reference

### Requirements File Map

Requirements are split into multiple files under `requirements/`:

| Need to find...                    | Read this file                                |
| ---------------------------------- | --------------------------------------------- |
| AI Study Tools, Integrations       | `requirements/features-part1.md` (§6.1-6.2)   |
| Registration, Courses, Content     | `requirements/features-part1.md` (§6.3-6.4)   |
| Analytics, Communication, Teachers | `requirements/features-part1.md` (§6.5-6.12)  |
| Tasks, Calendar, Audit             | `requirements/features-part1.md` (§6.13-6.14) |
| Themes, UI, Layout, Search         | `requirements/features-part2.md` (§6.15-6.17) |
| Parent UX, Security, Multi-Role    | `requirements/features-part2.md` (§6.20-6.26) |
| Messaging, Teacher Linking, Admin  | `requirements/features-part3.md` (§6.27-6.42) |
| Onboarding, Verification, Emails   | `requirements/features-part3.md` (§6.43-6.50) |
| Dashboards (Parent, Student, etc.) | `requirements/dashboards.md` (§7)             |
| Roadmap, Phase checklists          | `requirements/roadmap.md` (§8)                |
| Mobile app                         | `requirements/mobile.md` (§9)                 |
| Architecture, API endpoints        | `requirements/technical.md` (§10-11)          |
| GitHub issue tracking              | `requirements/tracking.md` (§12-13)           |

### Cross-DB Rules (SQLite + PostgreSQL)

- Use `String(N)` not `Enum` for column types
- Use `DEFAULT FALSE` not `DEFAULT 0` for booleans
- Use `TIMESTAMPTZ` (PostgreSQL) / `DATETIME` (SQLite)
- Test with SQLite locally, deploy to PostgreSQL

### UI Convention

- Use icon buttons with `title` tooltips (not text buttons)
- Use HTML entities/unicode for icons (e.g., &#128203; clipboard, &#128214; book)
- Follow existing CSS variable patterns from `index.css`
