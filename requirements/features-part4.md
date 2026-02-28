### 6.52 MCP Protocol Integration (Phase 2 — Track F) — #903

Integrate the **Model Context Protocol (MCP)** into ClassBridge to transform it from a tool-based AI platform into a **contextual AI learning platform**. MCP enables AI assistants (Claude Desktop, Cursor, custom agents) to interact with ClassBridge data and tools through a standardized protocol, and enables ClassBridge to consume external MCP servers for enriched educational content.

**Epic Issue:** #903
**GitHub Issues:** #903 (epic), #904-#912 (sub-tasks)

**Business Value:**
- **Differentiation:** First education platform with native MCP support
- **User Engagement:** Natural language interaction with ClassBridge via Claude Desktop
- **Platform Effect:** ClassBridge becomes an AI tool ecosystem, not just a standalone app
- **Developer Ecosystem:** Third-party MCP clients can build on ClassBridge data
- **Cost Efficiency:** MCP client integration reduces need to build every AI feature in-house

**Technical Stack:**
- `fastapi-mcp` — Zero-config FastAPI-to-MCP bridge for auto-exposing endpoints
- `fastmcp` / official MCP Python SDK — Custom tools, resources, and prompts
- SSE (Server-Sent Events) transport for remote clients
- JWT + API key authentication

---

#### 6.52.1 FastAPI-MCP Server Foundation (#904)

Mount an MCP server on the existing FastAPI application with selective endpoint exposure.

**Implementation:**
1. Install `fastapi-mcp` and add to `requirements.txt`
2. Mount MCP server at `/mcp` endpoint in `main.py`
3. Configure `MCP_BASE_URL` in `app/core/config.py` (default `http://localhost:8000`, production `https://www.classbridge.ca`)
4. Filter endpoints: expose only safe read + AI generation routes, exclude auth/admin/delete/OAuth

**Included Endpoints (auto-exposed as MCP tools):**
- `GET /api/courses/*` — list/get courses
- `GET /api/assignments/*` — list/get assignments
- `GET /api/study/*` — list/get study guides, quizzes, flashcards
- `POST /api/study/generate` — generate study guide
- `POST /api/study/quiz/generate` — generate quiz
- `POST /api/study/flashcards/generate` — generate flashcards
- `GET /api/tasks/*` — list/get tasks
- `GET /api/notifications/*` — list notifications
- `GET /api/analytics/*` — grades, trends, insights
- `GET /api/parent/children/*` — list children (parent role)
- `GET /api/messages/*` — list conversations, messages

**Excluded Endpoints:**
- `POST /api/auth/*` — login, register, token refresh
- `DELETE *` — all delete operations
- `GET /api/admin/*` — admin-only endpoints
- `POST /api/google/*` — OAuth flows
- `GET /api/users/*` — user management

**Key Files:**
- `main.py` — MCP server mount
- `app/core/config.py` — `MCP_BASE_URL` setting
- `requirements.txt` — `fastapi-mcp` dependency

**Sub-tasks:**
- [ ] Install `fastapi-mcp` dependency
- [ ] Mount MCP server at `/mcp` with endpoint filtering
- [ ] Add `MCP_BASE_URL` config setting
- [ ] Add MCP status to `/health` endpoint
- [ ] Verify MCP endpoint responds to client connections

---

#### 6.52.2 MCP Authentication & Authorization (#905)

Secure the MCP server with JWT and API key authentication, plus role-based tool filtering.

**JWT Authentication:**
- Reuse existing `get_current_user()` from `app/api/deps.py`
- Token passed via HTTP Authorization header or `?token=<jwt>` query parameter

**API Key Authentication (new):**
- New model: `api_keys` table (`id`, `user_id`, `key_hash`, `name`, `created_at`, `last_used_at`, `expires_at`, `is_active`)
- API keys hashed with bcrypt, shown only once on creation
- Rate limited: 100 requests/minute per API key
- Endpoints: `POST /api/auth/api-keys` (create), `GET /api/auth/api-keys` (list), `DELETE /api/auth/api-keys/{id}` (revoke)

**Role-Based Tool Filtering:**

| Tool Category | Parent | Student | Teacher | Admin |
|---|---|---|---|---|
| List children + child data | Yes | No | No | Yes |
| View own courses/assignments | Yes | Yes | Yes | Yes |
| Generate study materials | Yes | Yes | Yes | No |
| View grades/analytics | Yes | Yes | Yes | Yes |
| View/send messages | Yes | No | Yes | Yes |
| List students (roster) | No | No | Yes | Yes |
| Admin tools | No | No | No | Yes |

**Audit Logging:**
- All MCP tool invocations logged to `audit_logs` table
- Fields: user_id, tool_name, parameters (sanitized), timestamp, client_info

**Key Files:**
- `app/models/api_key.py` — APIKey model
- `app/schemas/api_key.py` — Pydantic schemas
- `app/api/routes/auth.py` — API key CRUD endpoints
- `app/api/deps.py` — MCP auth dependency

**Sub-tasks:**
- [ ] Create `api_keys` DB model and migration
- [ ] Create API key CRUD endpoints
- [ ] Add JWT auth middleware to MCP server
- [ ] Add API key auth as alternative
- [ ] Implement role-based tool filtering
- [ ] Add MCP tool invocation audit logging
- [ ] Frontend: API key management UI on Profile page

---

#### 6.52.3 Student Academic Context MCP Resources (#906)

Custom MCP resources and tools exposing a student's full academic context for contextual AI tutoring.

**MCP Resources (read-only, cached 5-min TTL):**

1. `student://profile/{student_id}` — Academic profile (courses, GPA, completion stats, quiz averages)
2. `student://assignments/{student_id}` — Assignment feed grouped by status (overdue, upcoming, recently completed)
3. `student://study-history/{student_id}` — Study material usage (guides by course, quiz score history, flashcard sets, session count)
4. `student://weak-areas/{student_id}` — AI-analyzed weak topics based on quiz scores and grades with recommended focus

**MCP Tools:**

5. `get_student_summary` — Natural language summary of current academic standing
   - Input: `student_id` (optional — defaults to self for students)
   - Auth: Student (self), Parent (own children), Teacher (enrolled students)

6. `identify_knowledge_gaps` — Topic-level gap analysis with severity and recommendations
   - Input: `student_id`, `course_id` (optional)
   - Auth: Student (self), Parent (own children), Teacher (enrolled students)

**Key Files:**
- `app/mcp/resources/student.py` — Student context resources
- `app/mcp/tools/student.py` — Student analysis tools

**Sub-tasks:**
- [ ] Create student profile resource
- [ ] Create assignment feed resource
- [ ] Create study history resource
- [ ] Create weak areas resource (reuse analytics logic)
- [ ] Create `get_student_summary` tool
- [ ] Create `identify_knowledge_gaps` tool
- [ ] Add 5-minute caching layer
- [ ] Enforce role-based access (parent→children, student→self, teacher→enrolled)

---

#### 6.52.4 Google Classroom MCP Tools (#907)

Wrap existing Google Classroom integration as MCP tools for AI assistants.

**MCP Tools:**

1. `list_google_courses` — List synced courses (filters: student_id, include_archived)
2. `list_course_assignments` — List assignments for a course (filters: status, limit)
3. `get_course_materials` — Get course materials (filters: material_type)
4. `get_classroom_grades` — Grade/score breakdown per student per course
5. `sync_classroom_data` — Trigger on-demand Google Classroom sync (rate limited: 1/5min)
6. `get_sync_status` — Check last sync timestamp and connection status

**Technical Notes:**
- Tools query local DB (synced data), not Google API directly
- `sync_classroom_data` is the only tool that triggers a Google API call
- Clear error when Google is not connected: "Connect Google Classroom first at classbridge.ca/settings"

**Key Files:**
- `app/mcp/tools/google_classroom.py` — Google Classroom MCP tools
- `app/services/google_classroom_service.py` — Existing service (reused)

**Sub-tasks:**
- [ ] Create 6 Google Classroom MCP tools
- [ ] Wire to existing service layer
- [ ] Add rate limiting to sync tool
- [ ] Handle "not connected" state gracefully

---

#### 6.52.5 Study Material Generation MCP Tools (#908)

Expose study material generation and retrieval as MCP tools.

**MCP Tools:**

1. `generate_study_guide` — Generate AI study guide from content (rate limit: 10/min)
2. `generate_quiz` — Generate practice quiz (rate limit: 10/min)
3. `generate_flashcards` — Generate flashcards (rate limit: 10/min)
4. `list_study_materials` — List materials with filtering (type, course, student)
5. `get_study_material` — Get full content of a study material by ID
6. `search_study_materials` — Search materials by keyword
7. `convert_study_material` — Convert guide to quiz or flashcards

**Technical Notes:**
- Generation tools are synchronous (wait for AI response, unlike web UI background generation)
- Duplicate detection (content_hash) prevents redundant AI calls
- Critical dates extraction still creates Task records
- Parent notifications fire when student generates via MCP

**Key Files:**
- `app/mcp/tools/study.py` — Study material MCP tools
- `app/services/ai_service.py` — Existing AI service (reused)

**Sub-tasks:**
- [ ] Create 7 study material MCP tools
- [ ] Wire to existing AI service and study route logic
- [ ] Add duplicate detection
- [ ] Verify critical dates extraction and task creation
- [ ] Verify parent notifications on student generation

---

#### 6.52.6 AI Tutor Agent — Contextual Study Planning (#909)

Capstone feature: an AI Tutor Agent that combines all MCP resources to generate personalized, context-aware study plans.

**MCP Tools:**

1. `create_study_plan` — Generate multi-day personalized study plan
   - Input: `student_id`, `goal` (optional), `days` (default 7), `hours_per_day` (default 2), `focus_courses` (optional)
   - Output: Markdown study plan with daily activities referencing existing materials
   - Side effect: Auto-creates Task records for each study day with linked resources
   - Auth: Student (self), Parent (children)

2. `get_study_recommendations` — Quick "what to study next" recommendations
   - Input: `student_id`, `time_available` (minutes, default 30)
   - Output: Top 3 prioritized activities with rationale and estimated time
   - Auth: Student (self), Parent (children)

3. `analyze_study_effectiveness` — Evaluate whether recent studying has been effective
   - Input: `student_id`, `period` (7d|30d|90d)
   - Output: Effectiveness report (improved topics, stagnated topics, unstudied declining topics, method recommendations)
   - Auth: Student (self), Parent (children), Teacher (enrolled students)

**Data Sources Consumed:**
- `student://profile/{id}` — Academic overview
- `student://assignments/{id}` — Upcoming deadlines
- `student://study-history/{id}` — What's been studied
- `student://weak-areas/{id}` — Gap analysis
- `list_study_materials` — Existing resources to reference
- `get_classroom_grades` — Grade trends

**AI Generation Strategy:**
- Multi-step prompt: (1) Analyze context + identify priorities → (2) Generate day-by-day plan
- Plans reference existing study materials by ID when available
- Context aggregation cached (5-min TTL) to avoid redundant DB queries

**Key Files:**
- `app/mcp/tools/tutor_agent.py` — AI Tutor Agent tools
- `app/services/ai_service.py` — AI generation (extended)

**Sub-tasks:**
- [ ] Create `create_study_plan` tool with multi-step AI generation
- [ ] Auto-create Task records from study plan days
- [ ] Create `get_study_recommendations` tool
- [ ] Create `analyze_study_effectiveness` tool
- [ ] Context aggregation with caching
- [ ] Reference existing study materials in plans

---

#### 6.52.7 Teacher Communication MCP Tools (#910)

Expose parent-teacher messaging and teacher communication summaries as MCP tools.

**MCP Tools:**

1. `list_conversations` — List message conversations (filters: unread_only, limit)
2. `get_conversation_messages` — Get messages in a conversation (auth: participants only)
3. `send_message` — Send a message (requires MCP client confirmation before sending)
4. `get_teacher_communication_summary` — AI-summarized teacher emails/announcements with action items
5. `get_unread_count` — Quick unread messages + notifications count

**Safety:** `send_message` is a write operation — MCP clients should prompt for user confirmation before executing.

**Key Files:**
- `app/mcp/tools/communication.py` — Communication MCP tools
- `app/services/ai_service.py` — `summarize_teacher_communication()` (reused)

**Sub-tasks:**
- [ ] Create 5 communication MCP tools
- [ ] Wire to existing message and teacher communication logic
- [ ] Ensure email notifications fire on MCP-sent messages
- [ ] Mark `send_message` as requiring confirmation

---

#### 6.52.8 MCP Client — External Resource Discovery (#911)

Enable ClassBridge to act as an MCP **client**, connecting to external MCP servers to enrich AI-generated study materials with supplementary content.

**External MCP Servers to Consume:**

1. **Web Search** — Find supplementary articles and explanations for study topics
   - Integration: Append "Recommended Resources" section to study guides
   - Server: Community `web-search` or Brave Search MCP server

2. **Educational Video Discovery** — Find relevant YouTube/educational videos
   - Integration: Add "Watch:" video links to study guides
   - Server: YouTube Data API wrapped as MCP server

3. **Curriculum-Aligned Content** (Phase 3 prep) — Match topics to Ontario curriculum expectations
   - Deferred until #571 (Ontario Curriculum Management) is built

**Configuration:**
```python
# app/core/config.py
mcp_web_search_url: str = ""          # empty = disabled
mcp_video_search_url: str = ""        # empty = disabled
mcp_enrich_study_materials: bool = False  # opt-in feature flag
```

**Safety & Privacy:**
- Feature is opt-in via feature flag (disabled by default)
- Graceful degradation when external servers unavailable
- Only topic name + grade level sent to external servers, never student PII
- External calls have 5-second timeout, run in parallel with AI generation
- Resource cache: 1-hour TTL by topic hash

**Key Files:**
- `app/mcp/client.py` — MCP client manager
- `app/services/ai_service.py` — Extended with resource enrichment
- `app/core/config.py` — MCP client configuration

**Sub-tasks:**
- [ ] Create MCP client manager with connection pooling
- [ ] Integrate web search enrichment into study guide generation
- [ ] Add feature flag and configuration
- [ ] Implement topic-based caching (1-hour TTL)
- [ ] Ensure no PII leakage to external servers
- [ ] Graceful degradation on timeout/unavailability

---

#### 6.52.9 MCP Integration Tests & Claude Desktop Configuration (#912)

Comprehensive test suite and end-user setup documentation.

**Test Suite:**
- `tests/test_mcp.py` — Unit tests for all MCP tools, resources, auth, and filtering (~40 tests)
- `tests/test_mcp_integration.py` — End-to-end flows (parent, student, teacher journeys)
- Performance benchmarks: <500ms reads, <30s AI generation, 10 concurrent clients

**Documentation:**
- `docs/mcp-setup-guide.md` — Step-by-step Claude Desktop configuration
  - Generate API key from Profile page
  - Add to `claude_desktop_config.json`
  - Verify connection and example prompts
- Cursor IDE configuration
- Custom MCP client setup (Python SDK example)

**Sub-tasks:**
- [ ] Write unit tests for all MCP tools and resources (~40 tests)
- [ ] Write 3+ integration test flows
- [ ] Performance benchmark tests
- [ ] Write Claude Desktop setup guide
- [ ] Write Cursor IDE setup guide
- [ ] Document example prompts per role

---

### MCP Implementation Order

| Phase | Issues | Description | Dependencies |
|---|---|---|---|
| **A (Foundation)** | #904, #905 | MCP server + auth | None |
| **B (Core Tools)** | #906, #907, #908 | Student context, Google Classroom, Study tools | Phase A |
| **C (Advanced)** | #909, #910, #911 | AI tutor agent, teacher comms, external resources | Phase B |
| **D (Quality)** | #912 | Tests, docs, Claude Desktop config | Phase A-C |

### MCP Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                  MCP Clients                         │
│  Claude Desktop │ Cursor │ Custom Agents │ Mobile    │
└────────┬────────┴────┬───┴──────┬────────┴──────────┘
         │             │          │
         ▼             ▼          ▼
┌─────────────────────────────────────────────────────┐
│              ClassBridge MCP Server (/mcp)            │
│  Transport: SSE │ Auth: JWT + API Key │ RBAC         │
│                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │  Resources   │ │    Tools     │ │   Prompts    │ │
│  │  (4 types)   │ │  (26 tools)  │ │  (3 types)   │ │
│  │              │ │              │ │              │ │
│  │ Profile      │ │ Study Gen    │ │ Study Plan   │ │
│  │ Assignments  │ │ Classroom    │ │ Exam Prep    │ │
│  │ History      │ │ Messages     │ │ Briefing     │ │
│  │ Weak Areas   │ │ Tutor Agent  │ │              │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│     ClassBridge as MCP Client (opt-in)               │
│     Web Search │ Video Discovery │ Curriculum        │
└─────────────────────────────────────────────────────┘
```

### Tool Summary (26 total)

| Category | Tools | Issue |
|---|---|---|
| Student Context | `get_student_summary`, `identify_knowledge_gaps` | #906 |
| Google Classroom | `list_google_courses`, `list_course_assignments`, `get_course_materials`, `get_classroom_grades`, `sync_classroom_data`, `get_sync_status` | #907 |
| Study Materials | `generate_study_guide`, `generate_quiz`, `generate_flashcards`, `list_study_materials`, `get_study_material`, `search_study_materials`, `convert_study_material` | #908 |
| AI Tutor Agent | `create_study_plan`, `get_study_recommendations`, `analyze_study_effectiveness` | #909 |
| Communication | `list_conversations`, `get_conversation_messages`, `send_message`, `get_teacher_communication_summary`, `get_unread_count` | #910 |
| Auto-exposed | ~15 read endpoints via fastapi-mcp | #904 |
