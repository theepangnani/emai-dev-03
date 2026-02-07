# /requirement - Requirement Management

Analyse, document, and track new requirements or changes to existing ones.

## Usage

`/requirement <description of the requirement or feature>`

Example: `/requirement Add student self-enrollment for courses`

## Instructions

Follow these steps in order:

### Step 1: Analyse the Requirement

1. Read the current `REQUIREMENTS.md` to understand existing features, phases, and patterns
2. Read relevant source code (models, routes, frontend pages) to understand the current implementation state
3. Identify:
   - Which section of REQUIREMENTS.md this belongs to (existing section update or new section)
   - Which phase it fits into (Phase 1, 1.5, 2, 3, 4)
   - What already exists vs what needs to be built
   - Dependencies on other features or data model changes
   - Impact on existing functionality (breaking changes, migrations needed)

### Step 2: Provide Feedback

Present the analysis to the user before making any changes:

```
=== Requirement Analysis ===

Summary: <1-2 sentence description>

Phase: <which phase this belongs to>
Section: <which REQUIREMENTS.md section (new or existing)>

Current State:
- <what already exists that relates to this>

What Needs to Change:
- Backend: <models, routes, services affected>
- Frontend: <pages, components affected>
- Database: <schema changes, migrations>

Dependencies:
- <other features or issues this depends on>

Risks / Considerations:
- <breaking changes, edge cases, security concerns>

Estimated Scope: <small / medium / large>
```

**Wait for user confirmation before proceeding to Steps 3 and 4.**

### Step 3: Update REQUIREMENTS.md

1. Add or update the relevant section in `REQUIREMENTS.md`
2. Follow existing conventions:
   - Use the same heading hierarchy and table formats
   - Mark implementation status: `- IMPLEMENTED`, `- PARTIAL`, or no suffix for planned
   - Include data model changes with field names and types
   - Include endpoint definitions with HTTP method, path, and description
   - Include role-based access rules
3. If updating an existing section, preserve what's already there and add/modify only what's needed
4. Keep language concise and specification-oriented (not conversational)

### Step 4: Create/Update GitHub Issues

1. Check existing open issues with `gh issue list --state open` to avoid duplicates
2. Break the requirement into actionable implementation issues:
   - One issue per logical unit of work (e.g., backend model change, API endpoint, frontend page)
   - Use clear titles: `<Action> <what> (<where>)` — e.g., "Add student self-enroll endpoint (backend)"
3. Create issues using:
```bash
gh issue create --title "<title>" --body "<body>" --label "<labels>"
```
4. Issue body format:
```markdown
## Context
<Brief description and link to requirement>

## Acceptance Criteria
- [ ] <specific, testable criterion>
- [ ] <specific, testable criterion>

## Technical Notes
- <relevant implementation details>
- <affected files or components>

## Dependencies
- <other issues this depends on, if any>
```
5. Use appropriate labels: `backend`, `frontend`, `database`, `priority:high`, `priority:medium`, `enhancement`, `bug`
6. If an existing issue covers part of the requirement, update it with `gh issue edit <number>` instead of creating a duplicate

### After Completion

Report a summary:
```
=== Requirement Tracked ===

REQUIREMENTS.md: <updated section name>
Issues created/updated:
- #<number>: <title>
- #<number>: <title>

Next steps: <what to implement first>
```
