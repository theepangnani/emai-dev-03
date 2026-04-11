# §6.131 — Unified Template + Detection Framework (UTDF)
## Study Guide & Worksheet Generation Enhancement

**Feature ID:** CB-UTDF-001  
**Section:** §6.131  
**Version:** 1.0  
**Date:** 2026-04-08  
**Author:** Sarah (Product Owner) / Theepan Gnanasabapathy  
**Status:** READY FOR IMPLEMENTATION  
**Phase:** 2  
**Target:** May–June 2026  
**Repository:** class-bridge-phase-2  

---

## 1. Context & Pre-Assessment (Critical — Read First)

### What Already Exists (DO NOT re-implement)

The following §3.9 Study Guide Strategy Pattern infrastructure is **already implemented and in production** (issues #1972, #1985, #1987, #1989):

| Component | Status | Detail |
|-----------|--------|--------|
| Document type classification | ✅ IMPLEMENTED | Claude Haiku classifies into 8 types via `DocumentTypeSelector` |
| Study goal selection | ✅ IMPLEMENTED | 7 goals in `UploadWizardStep2` via `StudyGoalSelector` |
| Strategy-driven prompt variation | ✅ IMPLEMENTED | Prompts vary by `document_type + study_goal` |
| Sub-guide strategy inheritance | ✅ IMPLEMENTED | `generation_context` column on `study_guides` |
| Overview suggestion chips | ✅ IMPLEMENTED | Post-generation chips trigger streaming sub-guides |
| Single-child auto-select | ✅ IMPLEMENTED | Parent with one child → auto-assigned on upload |
| Study Guide generation | ✅ IMPLEMENTED | `POST /api/study/guides/` |
| Quiz generation | ✅ IMPLEMENTED | `POST /api/quiz/generate/` |
| Flashcard generation | ✅ IMPLEMENTED | `POST /api/flashcards/generate/` |

**Existing document_type enum values:**
```
teacher_notes | course_syllabus | past_exam | mock_exam |
project_brief | lab_experiment | textbook_excerpt | custom | parent_question
```

**Existing study_goal enum values:**
```
upcoming_test | final_exam | assignment | lab_prep |
general_review | discussion | parent_review
```

### What This Feature Adds (Net-New)

| Component | Net-New? | Notes |
|-----------|----------|-------|
| Named template library (8 templates) | ✅ NEW | Formalizes existing prompt variants + adds worksheet templates |
| Subject/class auto-detection | ✅ NEW | Extend Claude Haiku classification call |
| Multi-child disambiguation modal | ✅ NEW | Single-child already works; multi-child disambiguation is new |
| Teacher auto-assignment | ✅ NEW | No teacher detection exists today |
| Material-type-driven chip sets | ⚠️ EXTENDS | Current chips are generic; make them material-type-aware |
| Worksheet output type | ✅ NEW | Platform generates study guides/quiz/flashcards — NOT worksheets yet |
| Word problem worksheet (Math) | ✅ NEW | Math-specific worksheet variant |
| French worksheet | ✅ NEW | French-specific worksheet variant |
| High-level summary chip | ✅ NEW | Fast, abbreviated summary output |
| Weak area analysis chip | ✅ NEW | Post-exam upload analysis (references §6.66 Weak Spot Report) |
| Manual detection override UI | ✅ NEW | Parent can correct all 4 detected dimensions |

---

## 2. Feature Overview

UTDF enhances the existing §3.9 strategy pattern upload flow to:
1. **Auto-detect 4 dimensions** of any uploaded file: Material Type, Subject, Student, Teacher
2. **Show context-aware suggestion chips** based on the detected material type
3. **Route generation to the correct named template** based on subject × material type
4. **Surface worksheet generation** as a new first-class output type alongside Study Guide, Quiz, Flashcard

### User Story (Parent Perspective)

> As a parent, when I upload my child's Grade 10 Math past exam, I want the system to automatically recognize what it is, suggest the most useful next actions (like creating a practice test or identifying weak areas), and assign it to the right child — so I don't have to manually configure everything before getting help.

---

## 3. Master Template Library

### 3.1 Template Registry

Eight named templates, stored in the existing strategy pattern system (extend `StudyGuideStrategyService`):

| Template Key | Category | Subject | Maps From (document_type + subject) |
|-------------|----------|---------|-------------------------------------|
| `study_guide_overview` | study_guide | Any | Any type + general_review goal |
| `study_guide_math` | study_guide | Math | Any type + math-detected subject |
| `study_guide_science` | study_guide | Science | Any type + science-detected subject |
| `study_guide_english` | study_guide | English/French | Any type + english/french subject |
| `worksheet_general` | worksheet | Any | teacher_notes/course_syllabus + worksheet request |
| `worksheet_math_word_problems` | worksheet | Math | math-detected + worksheet request |
| `worksheet_english` | worksheet | English | english-detected + worksheet request |
| `worksheet_french` | worksheet | French | french-detected + worksheet request |

**Implementation note:** Templates are prompt variants in `StudyGuideStrategyService` — NOT new database tables. Extend the existing `get_strategy()` method with a `template_key` output. Add `template_key` VARCHAR(50) column to `study_guides` table for tracking.

### 3.2 Template Selection Logic

```python
def resolve_template_key(document_type: str, detected_subject: str, requested_output: str) -> str:
    if requested_output == "worksheet":
        if detected_subject == "math":       return "worksheet_math_word_problems"
        if detected_subject == "english":    return "worksheet_english"
        if detected_subject == "french":     return "worksheet_french"
        return "worksheet_general"
    else:  # study_guide
        if detected_subject == "math":       return "study_guide_math"
        if detected_subject == "science":    return "study_guide_science"
        if detected_subject in ("english", "french"): return "study_guide_english"
        return "study_guide_overview"
```

---

## 4. Auto-Detection System

### 4.1 Detection Dimensions

The existing Claude Haiku classification call (used in §3.9) must be extended to detect **all 4 dimensions in a single call**, returning structured JSON:

```python
# Extend existing classify_document() in StudyGuideStrategyService
# Current output: {"document_type": "past_exam"}
# New output:
{
  "document_type": "past_exam",          # existing — no change to enum values
  "detected_subject": "math",            # NEW
  "confidence": 0.91,                    # NEW — overall classification confidence
  "subject_keywords_found": ["algebra", "quadratic", "polynomial"],  # NEW — for UI display
  "material_type_display": "Past Exam"   # NEW — human-readable label
}
```

**Subject detection values:** `math | science | english | french | history | geography | computer_studies | other`

**Confidence threshold:** ≥ 0.80 = auto-assign and show confirmed chip; < 0.80 = show detected value with "Does this look right?" inline confirmation.

### 4.2 Material Type → Display Label Mapping

| `document_type` (existing enum) | Display Label | UTDF Category |
|--------------------------------|---------------|---------------|
| `teacher_notes` | Teacher Notes | Handout/Notes |
| `course_syllabus` | Syllabus | Handout/Notes |
| `past_exam` | Past Exam | Exam |
| `mock_exam` | Mock Exam | Exam |
| `project_brief` | Assignment | Assignment |
| `lab_experiment` | Lab Material | Handout/Notes |
| `textbook_excerpt` | Class Material | Notes |
| `custom` | Other | Other |
| *(new)* `worksheet` | Worksheet | Worksheet |
| *(new)* `student_test` | Student Test | Student Test |
| *(new)* `quiz_paper` | Quiz | Quiz |

**DB migration required:** Add `worksheet`, `student_test`, `quiz_paper` to `document_type` enum on `course_content` table (already a string column per §5.1 Enum→String migration, so append-only).

### 4.3 Student Auto-Detection

| Scenario | Behavior |
|----------|----------|
| Parent has 1 child | Auto-assign. No UI prompt. Show confirmed badge: "Assigned to [Child Name]" |
| Parent has 2+ children, document has grade level | Match to child at that grade. If ambiguous, show disambiguation modal |
| Parent has 2+ children, no grade detected | Show disambiguation modal |
| Grade detected but no child matches | Show disambiguation modal with "None of these — create new" |

**Disambiguation modal:** Single-select pill row showing child name + grade for each linked child. "Not sure" option defaults to parent's primary child.

### 4.4 Teacher Auto-Assignment

| Scenario | Behavior |
|----------|----------|
| Teacher name found in document text | Auto-assign. Show "Teacher: [Name]" badge |
| Selected course has known teacher | Auto-assign from course record |
| No teacher identified | Show optional prompt: "Add a teacher for [Subject]?" with inline add form |
| Teacher prompt dismissed | Proceed without teacher. Non-blocking. |

**Teacher lookup:** Query `courses` table by selected child + subject match. Reuse existing `teacher_id` FK on `course_content`.

---

## 5. Smart Suggestion Chips

### 5.1 Chip Sets by Material Type

Chips appear after upload classification completes. Maximum 6 chips. Chip order = priority order.

**Handout / Teacher Notes / Syllabus** (`teacher_notes`, `course_syllabus`):
```
[Generate Worksheets] [Create Sample Test] [Create Quiz] [Create Flashcards]
[High Level Summary] [Full Study Guide ▾]
```

**Worksheet** (`worksheet`):
```
[Generate More Worksheets] [Generate Answer Key] [Create Quiz] [Create Flashcards]
```

**Past Exam / Mock Exam** (`past_exam`, `mock_exam`):
```
[Create Practice Test] [Create Study Guide] [Create Flashcards] [Weak Area Analysis]
```

**Student Test / Quiz Paper** (`student_test`, `quiz_paper`):
```
[Create Practice Test] [Weak Area Analysis] [Create Study Guide] [Create Flashcards]
```

**Class Notes / Textbook / Lab** (`teacher_notes`-notes, `lab_experiment`, `textbook_excerpt`):
```
[Create Study Guide] [Generate Worksheets] [Create Quiz] [Create Flashcards]
[High Level Summary]
```

**Assignment / Project Brief** (`project_brief`):
```
[Create Study Guide] [Create Flashcards] [Ask Bot]
```

### 5.2 Chip Behavior

| Chip | Action | AI Engine | Template Used |
|------|--------|-----------|---------------|
| Create Study Guide | `POST /api/study/guides/` with `template_key=study_guide_{subject}` | OpenAI gpt-4o-mini | Subject-matched study guide template |
| Generate Worksheets | `POST /api/worksheets/generate/` *(new endpoint)* | OpenAI gpt-4o-mini | `worksheet_{subject}` template |
| Generate Answer Key | `POST /api/worksheets/answer-key/` *(new endpoint)* | OpenAI gpt-4o-mini | Answer key prompt variant |
| Create Sample Test / Practice Test | Existing quiz flow with `quiz_type=practice_test` | OpenAI gpt-4o-mini | Exam-format quiz template |
| Create Quiz | Existing `POST /api/quiz/generate/` | OpenAI gpt-4o-mini | Existing quiz template |
| Create Flashcards | Existing `POST /api/flashcards/generate/` | OpenAI gpt-4o-mini | Existing flashcard template |
| High Level Summary | `POST /api/study/guides/` with `template_key=high_level_summary` | OpenAI gpt-4o-mini | Concise 5-bullet summary template |
| Weak Area Analysis | `POST /api/analytics/weak-area/` *(new endpoint)* | Claude API (sonnet) | Analytical reasoning template |
| Full Study Guide | Existing streaming guide flow | OpenAI gpt-4o-mini | `study_guide_overview` with 4000 tokens |
| Ask Bot | Open chatbot drawer | Claude Haiku | Existing chatbot flow |

### 5.3 "Full Study Guide" Overflow

"Full Study Guide" chip only appears for Handout/Notes material types (NOT for Worksheets or Exams) and is styled as a secondary chip (lighter, smaller) with a down-caret `▾` to signal it's an advanced/optional action. It maps to existing streaming guide generation at 4000 tokens.

---

## 6. Refined Workflow

### Step 1 — Upload (Unchanged)
Parent uploads via existing UploadWizard (PDF, Word, PPTX, image, text). Existing file validation, magic bytes check, GCS storage unchanged.

### Step 2 — Classification (Extended)
After file is stored, the existing `classify_document()` call in `StudyGuideStrategyService` is extended to return the full 4-dimension JSON (see §4.1). Classification runs synchronously in the existing non-blocking modal pattern (pulsing placeholder already implemented).

**Classification prompt extension** (modify existing Claude Haiku prompt):
```
In addition to document_type, also return:
- detected_subject: one of [math, science, english, french, history, geography, computer_studies, other]
- confidence: float 0.0-1.0 representing overall classification confidence
- subject_keywords_found: list of up to 5 keywords that led to subject detection
Return as JSON only.
```

### Step 3 — Confirmation UI (New)
After classification, show a compact confirmation bar above the suggestion chips:

```
📄 [Past Exam]  📚 [Math]  👤 [Thanushan – Grade 10]  👨‍🏫 [Mr. Smith]  [Edit ✎]
```

- High-confidence (≥ 0.80): All badges shown as confirmed (solid fill)
- Low-confidence: Relevant badge shown with dashed border + "?" indicator
- "Edit ✎" opens inline override panel (see §6.4)

### Step 4 — Smart Chip Display (New)
Chips rendered based on `document_type` using the chip sets defined in §5.1. Existing chip styling from design system applies. Chips replace the existing generic "Generate Study Guide" / "Generate Quiz" / "Generate Flashcards" buttons on the post-upload state.

### Step 5 — Generation
User taps chip → existing generation flow for Study Guide / Quiz / Flashcard. New flow for Worksheet / Answer Key / Weak Area Analysis. `template_key` passed to strategy service. Output stored with `template_key` column populated.

### Step 6 — Override (New, Non-Blocking)
If parent taps "Edit ✎":
- Material Type: Dropdown (all 11 material types)
- Subject: Dropdown (8 subjects)
- Student: Child selector (existing child pill UI)
- Teacher: Teacher selector (existing teacher list)
Saving override re-runs chip display with corrected values. **Override does not re-run AI classification** — it uses the manually selected values.

---

## 7. New API Endpoints

### 7.1 Worksheet Generation
```
POST /api/worksheets/generate/
Request:
{
  "content_id": "uuid",           # existing course_content record
  "template_key": "worksheet_math_word_problems",
  "num_questions": 10,            # 5-20, default 10
  "difficulty": "grade_level",    # below_grade | grade_level | above_grade
  "student_id": "uuid"
}
Response: { "worksheet_id": "uuid", "status": "queued" }
```

### 7.2 Answer Key Generation
```
POST /api/worksheets/{worksheet_id}/answer-key/
Response: { "answer_key_id": "uuid", "status": "queued" }
```

### 7.3 Weak Area Analysis
```
POST /api/analytics/weak-area/
Request:
{
  "content_id": "uuid",           # student test or past exam upload
  "student_id": "uuid"
}
Response: { "analysis_id": "uuid", "status": "queued" }
```

### 7.4 Classification Override
```
PATCH /api/course-content/{content_id}/classification/
Request:
{
  "document_type": "past_exam",
  "detected_subject": "math",
  "student_id": "uuid",
  "teacher_id": "uuid"
}
Response: { "content_id": "uuid", "chips": [...] }  # returns updated chip set
```

---

## 8. Data Model Changes

### 8.1 New Columns (Migrations)

```sql
-- On course_content table (existing)
ALTER TABLE course_content
  ADD COLUMN detected_subject VARCHAR(50),          -- math|science|english|french|etc.
  ADD COLUMN detection_confidence NUMERIC(4,3),     -- 0.000–1.000
  ADD COLUMN template_key VARCHAR(50),              -- resolved template key
  ADD COLUMN classification_override BOOLEAN DEFAULT FALSE;  -- true if parent manually corrected

-- On study_guides table (existing)
ALTER TABLE study_guides
  ADD COLUMN template_key VARCHAR(50);              -- which template was used

-- On course_content document_type column (already string per §5.1 migration)
-- Append new values to application-level enum: worksheet, student_test, quiz_paper
```

### 8.2 New Table: worksheets

```sql
CREATE TABLE worksheets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES course_content(id) ON DELETE CASCADE NOT NULL,
  student_id UUID REFERENCES students(id),
  created_by UUID REFERENCES users(id) NOT NULL,
  template_key VARCHAR(50) NOT NULL,
  num_questions INT NOT NULL DEFAULT 10,
  difficulty VARCHAR(20) NOT NULL DEFAULT 'grade_level',
  status VARCHAR(20) NOT NULL DEFAULT 'queued',    -- queued|generating|complete|failed
  output_markdown TEXT,
  answer_key_markdown TEXT,
  ai_engine VARCHAR(20) NOT NULL DEFAULT 'openai',
  prompt_tokens_used INT,
  output_tokens_used INT,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  CONSTRAINT worksheets_difficulty_check CHECK (difficulty IN ('below_grade','grade_level','above_grade')),
  CONSTRAINT worksheets_status_check CHECK (status IN ('queued','generating','complete','failed'))
);

CREATE INDEX idx_worksheets_content_id ON worksheets(content_id);
CREATE INDEX idx_worksheets_student_id ON worksheets(student_id);
CREATE INDEX idx_worksheets_created_by ON worksheets(created_by);
```

### 8.3 New Table: weak_area_analyses

```sql
CREATE TABLE weak_area_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID REFERENCES course_content(id) ON DELETE CASCADE NOT NULL,
  student_id UUID REFERENCES students(id),
  requested_by UUID REFERENCES users(id) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'queued',
  analysis_markdown TEXT,
  weak_topics JSONB,                                -- ["Quadratic equations", "Factoring"]
  ai_engine VARCHAR(20) NOT NULL DEFAULT 'claude',
  prompt_tokens_used INT,
  output_tokens_used INT,
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX idx_weak_area_analyses_student_id ON weak_area_analyses(student_id);
```

---

## 9. Acceptance Criteria

### AC-1: Classification Accuracy (Material Type)
```
GIVEN a parent uploads a PDF with blank answer fields labeled "Name: ___"
WHEN classification completes
THEN document_type = "worksheet" AND detection_confidence ≥ 0.80
AND chips shown = [Generate More Worksheets, Generate Answer Key, Create Quiz, Create Flashcards]
AND "Full Study Guide" chip is NOT shown
```

### AC-2: Classification Accuracy (Past Exam)
```
GIVEN a parent uploads a PDF with "Past Exam", "Total: 40 marks", MCQ sections
WHEN classification completes
THEN document_type = "past_exam"
AND chips shown = [Create Practice Test, Create Study Guide, Create Flashcards, Weak Area Analysis]
```

### AC-3: Subject Detection — Math
```
GIVEN a parent uploads a document containing "algebra", "quadratic", "polynomial"
WHEN classification completes
THEN detected_subject = "math"
AND study guide generated uses template_key = "study_guide_math"
AND worksheet generated uses template_key = "worksheet_math_word_problems"
```

### AC-4: Single Child Auto-Select
```
GIVEN a parent has exactly one linked child
WHEN any file is uploaded
THEN student is auto-assigned without showing the disambiguation modal
AND the confirmation bar shows "[Child Name] – Grade X" as a confirmed badge
```

### AC-5: Multi-Child Disambiguation
```
GIVEN a parent has two children (Grade 8, Grade 10)
AND uploaded document contains "Grade 10"
WHEN classification completes
THEN system auto-selects the Grade 10 child
AND shows confirmation badge without modal
```

### AC-6: Multi-Child — Ambiguous
```
GIVEN a parent has two children with no grade match in document
WHEN classification completes
THEN disambiguation modal appears with both children as selectable pills
AND parent must select before chips are enabled
```

### AC-7: Teacher Auto-Assignment
```
GIVEN the selected course for the upload has teacher_id = non-null
WHEN classification completes
THEN teacher is auto-assigned from the course record
AND "Teacher: [Name]" badge shown as confirmed
```

### AC-8: Low Confidence UI
```
GIVEN the AI classifier returns confidence = 0.65 for document_type
WHEN classification completes
THEN the material type badge shows a dashed border with "?" indicator
AND an inline message "Does this look right? [Edit]" appears
AND chips are still shown based on the detected (unconfirmed) type
```

### AC-9: Manual Override
```
GIVEN a parent taps "Edit ✎" on the confirmation bar
WHEN parent changes Material Type from "Worksheet" to "Past Exam"
THEN chips update to the Past Exam set without page reload
AND the course_content record is updated with classification_override = true
AND the new document_type and detected_subject are persisted
```

### AC-10: Worksheet Generation
```
GIVEN a parent uploads teacher notes for Grade 10 Math
AND taps "Generate Worksheets"
WHEN generation completes
THEN a worksheet with 10 math word problems is generated
AND the worksheet is viewable at /worksheets/{id}
AND the worksheet is accessible from the course material detail page
AND template_key = "worksheet_math_word_problems" on the worksheets record
```

### AC-11: High Level Summary
```
GIVEN a parent uploads a syllabus
AND taps "High Level Summary"
WHEN generation completes
THEN a study guide is generated with 3–5 bullet summary of key topics
AND template_key = "high_level_summary" on the study_guides record
AND the guide completes in < 15 seconds
```

### AC-12: Weak Area Analysis
```
GIVEN a parent uploads a student's marked test (student_test type)
AND taps "Weak Area Analysis"
WHEN analysis completes
THEN the analysis identifies 2–5 specific weak topic areas
AND each area has a plain-language explanation
AND the output is viewable on the course material page
AND the AI engine used = Claude (claude-sonnet)
```

---

## 10. Frontend Components

### New Components

| Component | File | Purpose |
|-----------|------|---------|
| `ClassificationBar` | `components/study/ClassificationBar.tsx` | Shows 4 detected dimension badges + Edit button |
| `ChildDisambiguationModal` | `components/study/ChildDisambiguationModal.tsx` | Multi-child selector modal |
| `MaterialTypeSuggestionChips` | `components/study/MaterialTypeSuggestionChips.tsx` | Replaces generic chips; driven by document_type |
| `ClassificationOverridePanel` | `components/study/ClassificationOverridePanel.tsx` | Inline override form for all 4 dimensions |
| `WorksheetViewer` | `pages/WorksheetViewer.tsx` | View/download generated worksheet |
| `WeakAreaAnalysisViewer` | `pages/WeakAreaAnalysisViewer.tsx` | View weak area analysis output |

### Modified Components

| Component | Change |
|-----------|--------|
| `UploadWizardStep2` | Add `ClassificationBar` + `MaterialTypeSuggestionChips` below existing `DocumentTypeSelector` |
| `DocumentTypeSelector` | Extend to support new values: `worksheet`, `student_test`, `quiz_paper` |
| `CourseDetailPage` | Add "Worksheets" tab alongside Study Guide | Quiz | Flashcards |

---

## 11. Story Breakdown & Implementation Order

| Story | Title | Effort | Phase | Dependencies |
|-------|-------|--------|-------|-------------|
| **S1** | Extend classification — add subject + confidence to existing Haiku call | S | Phase 2 | None |
| **S2** | DB migration — add columns to course_content + study_guides; new worksheets + weak_area_analyses tables | S | Phase 2 | None |
| **S3** | Template key resolver — extend `StudyGuideStrategyService.get_strategy()` | S | Phase 2 | S1 |
| **S4** | ClassificationBar component — 4 badges + confidence states | M | Phase 2 | S1 |
| **S5** | ChildDisambiguationModal — multi-child selector | S | Phase 2 | None |
| **S6** | MaterialTypeSuggestionChips — replace generic chips with type-driven sets | M | Phase 2 | S1, S4 |
| **S7** | ClassificationOverridePanel — manual override for all 4 dimensions + PATCH endpoint | M | Phase 2 | S4, S6 |
| **S8** | Worksheet generation endpoint + WorksheetViewer page | L | Phase 2 | S2, S3 |
| **S9** | Answer key generation endpoint | M | Phase 2 | S8 |
| **S10** | Weak area analysis endpoint (Claude API) + WeakAreaAnalysisViewer | L | Phase 2 | S2 |
| **S11** | Teacher auto-assignment logic | S | Phase 2 | S4 |
| **S12** | High Level Summary template variant | S | Phase 2 | S3 |
| **S13** | CourseDetailPage Worksheets tab | M | Phase 2 | S8 |
| **S14** | Mobile (Expo) — ClassificationBar + Chips on upload flow | M | Phase 2 | S4, S6 |
| **S15** | Tests — unit (classifier), integration (upload→classify→chip), E2E (worksheet generation) | M | Phase 2 | All |

**Parallel streams available:** S1+S2 can run in parallel (no dependency). S4+S5 can run in parallel with S3.

---

## 12. MFIPPA / Privacy Compliance

| Requirement | Implementation |
|-------------|----------------|
| Uploaded files scoped to parent's own children only | Existing RBAC on course_content — no change |
| `detected_subject` and `classification_override` are not PII | No special handling required |
| Worksheets and weak area analyses scoped to student | `student_id` FK enforces scoping; RBAC check on all new endpoints |
| `subject_keywords_found` logged only at DEBUG level | Do not log in production INFO/WARNING |
| Worksheet output retention: same as study guides | 1-year soft delete, 7-year hard delete (existing §6.25 lifecycle policy applies) |
| Weak area analysis: sensitive — do not include in parent-facing analytics aggregates | `weak_area_analyses` excluded from performance analytics aggregation |

---

## 13. AI Cost Estimates

| Output Type | Engine | Est. Input Tokens | Est. Output Tokens | Cost/Generation |
|-------------|--------|------------------|-------------------|----------------|
| Classification (extended) | Claude Haiku | ~800 | ~100 | ~$0.0001 |
| Worksheet (10 questions) | GPT-4o-mini | ~1500 | ~800 | ~$0.0004 |
| Answer Key | GPT-4o-mini | ~500 | ~600 | ~$0.0002 |
| High Level Summary | GPT-4o-mini | ~1000 | ~300 | ~$0.0002 |
| Weak Area Analysis | Claude Sonnet | ~2000 | ~1000 | ~$0.018 |

**Cost gate:** Weak Area Analysis consumes credits from existing AI usage limit system (§6.107). Use existing `check_ai_credits()` guard before triggering Claude Sonnet call.

---

## 14. Out of Scope (This Version)

- French-language UI localization of chips (chips text stays English)
- Teacher uploading on behalf of a student
- Classification retraining from override feedback (Phase 3)
- Worksheet sharing between parents (Phase 3)
- Print-formatted worksheet PDF export (Phase 3 — note: existing PDF print on study guides can be adapted later)
- Cloud Storage (Google Drive/OneDrive) destination for worksheets (Phase 3 — existing §6.95 handles study guides)

---

## 15. GitHub Issues to Create

| # | Title | Labels | Story |
|---|-------|--------|-------|
| New | [CB-UTDF-001] Epic: Unified Template + Detection Framework | `epic`, `phase-2`, `study-tools` | Epic |
| New | [CB-UTDF-S1] Extend document classification: add subject + confidence | `backend`, `ai`, `phase-2` | S1 |
| New | [CB-UTDF-S2] DB migration: detected_subject, template_key, worksheets table, weak_area_analyses table | `backend`, `db`, `migration`, `phase-2` | S2 |
| New | [CB-UTDF-S3] Template key resolver in StudyGuideStrategyService | `backend`, `ai`, `phase-2` | S3 |
| New | [CB-UTDF-S4] ClassificationBar component (4 badges + confidence states) | `frontend`, `phase-2` | S4 |
| New | [CB-UTDF-S5] ChildDisambiguationModal — multi-child selector | `frontend`, `phase-2` | S5 |
| New | [CB-UTDF-S6] MaterialTypeSuggestionChips — type-driven chip sets | `frontend`, `phase-2` | S6 |
| New | [CB-UTDF-S7] ClassificationOverridePanel + PATCH /classification endpoint | `frontend`, `backend`, `phase-2` | S7 |
| New | [CB-UTDF-S8] Worksheet generation: POST endpoint + WorksheetViewer page | `backend`, `frontend`, `ai`, `phase-2` | S8 |
| New | [CB-UTDF-S9] Answer key generation endpoint | `backend`, `ai`, `phase-2` | S9 |
| New | [CB-UTDF-S10] Weak area analysis: Claude Sonnet endpoint + viewer | `backend`, `frontend`, `ai`, `phase-2` | S10 |
| New | [CB-UTDF-S11] Teacher auto-assignment from course record | `backend`, `phase-2` | S11 |
| New | [CB-UTDF-S12] High Level Summary template variant | `backend`, `ai`, `phase-2` | S12 |
| New | [CB-UTDF-S13] CourseDetailPage: add Worksheets tab | `frontend`, `phase-2` | S13 |
| New | [CB-UTDF-S14] Mobile (Expo): ClassificationBar + chips on upload flow | `mobile`, `phase-2` | S14 |
| New | [CB-UTDF-S15] Tests: classifier unit, upload→chip integration, worksheet E2E | `testing`, `phase-2` | S15 |

---

## 16. References

- §3.9 Study Guide Strategy Pattern (#1972, #1985, #1987, #1989) — **extends this**
- §6.25 Course Materials Lifecycle — retention policy applies to worksheets
- §6.60 Digital Wallet / Credit System — credit guard for Weak Area Analysis (Claude Sonnet)
- §6.66 Responsible AI Parent Tools — Weak Spot Report is the parent-facing surface for weak_area_analyses
- §6.95 Cloud Storage Destination — Phase 3: extend to worksheets
- §6.106 Strategy Pattern — **this feature is the direct extension**
- §6.128 Ask a Question — reuses `parent_question` document_type; ensure classification doesn't conflict
- §6.129 Study Guide TOC — apply to worksheet viewer Phase 2
- §6.130 Inline Resource Links — consider adding to worksheet viewer Phase 3
- CB-PEDI-001 Parent Email Digest — worksheet generation events should be includable in digest (Phase 3)
- CB-MCNI-001 Multi-Channel Notifications — worksheet ready notification via WhatsApp/SMS (Phase 3)

---

## 17. Post-Review Data Model Decision (2026-04-09)

**Decision:** Worksheets and weak area analyses will **NOT** use separate tables as proposed in §8.2 and §8.3. Instead, they extend the existing `study_guides` table:

- `guide_type = 'worksheet'` for worksheets
- `guide_type = 'weak_area_analysis'` for weak area analyses
- New nullable columns on `study_guides`: `num_questions`, `difficulty`, `answer_key_markdown`, `weak_topics`, `template_key`

**Rationale:** The existing architecture stores all AI outputs (study guides, quizzes, flashcards) in `study_guides` with `guide_type` enum. Adding worksheet/analysis as additional types reuses existing: viewer infrastructure, print/export, course linking, status tracking, AI token logging, and RBAC. Creating separate tables would duplicate all of this.

**Impact:** §8.2 (`worksheets` table) and §8.3 (`weak_area_analyses` table) are superseded. §8.1 column additions to `course_content` and `study_guides` remain valid.

**GitHub Issues:** Epic #2948, Stories #2949-#2961

---

## 18. Gap Resolutions (2026-04-09)

### 18.1 Confidence Threshold UX — Priority Model

**Problem:** AC-6 (child disambiguation blocks chips) and AC-8 (low-confidence shows chips anyway) conflicted when both conditions overlap.

**Resolution — Child is the ONLY blocker:**

| Dimension | Low Confidence Behavior | Blocking? |
|-----------|------------------------|-----------|
| **Child** (ambiguous) | Disambiguation modal appears | **YES — chips disabled until resolved** |
| Material Type (< 0.80) | Dashed border + "?" on badge | No — chips shown based on detected type |
| Subject (< 0.80) | Dashed border + "?" on badge | No — template defaults to generic |
| Teacher (not found) | Optional "Add teacher?" prompt | No — dismissible, non-blocking |

**Multiple low-confidence dimensions:** All show dashed borders simultaneously. No stacking of modals or sequential prompts — just visual indicators. Parent can correct any/all via the Edit panel (S7).

**Updated AC-6:**
```
GIVEN a parent has two children with no grade match in document
AND document_type confidence = 0.65
WHEN classification completes
THEN disambiguation modal appears (child is blocking)
AND material type badge shows dashed border with "?" (non-blocking)
AND chips are disabled ONLY because child is unresolved
AND after child selection, chips appear based on detected (unconfirmed) material type
```

### 18.2 Credit Costs for New Output Types

| Output Type | AI Engine | Est. Cost/Call | Credits Consumed |
|-------------|-----------|---------------|-----------------|
| Study Guide | GPT-4o-mini | ~$0.0004 | 1 credit |
| Quiz | GPT-4o-mini | ~$0.0003 | 1 credit |
| Flashcards | GPT-4o-mini | ~$0.0003 | 1 credit |
| **Worksheet** | GPT-4o-mini | ~$0.0004 | **1 credit** |
| **Answer Key** | GPT-4o-mini | ~$0.0002 | **0 credits (free)** |
| **High Level Summary** | GPT-4o-mini | ~$0.0002 | **0 credits (free)** |
| **Weak Area Analysis** | Claude Sonnet | ~$0.018 | **2 credits** |

**Rationale:**
- Answer keys and summaries are cheap enough to be freebies that drive engagement
- Worksheets cost the same as study guides (comparable token usage)
- Weak area analysis is the only premium action (45x more expensive, Claude Sonnet)

**Implementation:** Use existing `check_ai_credits(cost=N)` guard. Pass `cost=0` for free actions (still logged in `ai_usage_history` for analytics), `cost=1` for worksheets, `cost=2` for weak area analysis.

### 18.3 Existing Upload Backfill Strategy

**Decision: No batch backfill. Graceful fallback + opt-in classification.**

| Scenario | Behavior |
|----------|----------|
| New upload (post-UTDF) | Full 4-dimension classification runs automatically |
| Existing upload (pre-UTDF, `detected_subject` = NULL) | ClassificationBar shows `document_type` badge only (if set). No subject/confidence/teacher badges. Generic chip set (current behavior). |
| Existing upload — user wants classification | "Detect subject" link in ClassificationBar triggers on-demand classification. Populates `detected_subject`, `detection_confidence`. Chips update to type-driven set. |

**New AC-13: Legacy Material Fallback**
```
GIVEN a course material was uploaded before UTDF deployment
AND detected_subject IS NULL
WHEN user views the material
THEN ClassificationBar shows only the document_type badge (if set)
AND suggestion chips show the generic set (current behavior)
AND a "Detect subject" link is visible
WHEN user clicks "Detect subject"
THEN classification runs (Claude Haiku, 1 API call)
AND detected_subject + confidence populate on the record
AND chips update to the material-type-driven set
AND no credit is consumed (classification is free)
```

---

## 19. Architecture Review

Architecture review issues G1–G12 (#3019–#3030) track cross-cutting fixes identified during PRD finalization. These are tracked separately from the 13 feature stories (S1–S15) above.

| Issue | Title | GitHub |
|-------|-------|--------|
| G1 | Template key collision guard | #3019 |
| G2 | Classification retry / timeout handling | #3020 |
| G3 | Chip set extensibility (plugin model) | #3021 |
| G4 | Override audit trail | #3022 |
| G5 | Credit cost configuration (not hard-coded) | #3023 |
| G6 | Worksheet PDF export | #3024 |
| G7 | Rate-limit on classification endpoint | #3025 |
| G8 | Mobile scope reduction (WebView for actions) | #3026 |
| G9 | Accessibility — screen reader for ClassificationBar | #3027 |
| G10 | Confidence threshold configurability | #3028 |
| G11 | Telemetry — classification accuracy tracking | #3029 |
| G12 | Documentation — UTDF developer guide | #3030 |

---

## 20. Deployment Report (2026-04-11)

### Deployment Timeline
- **2026-04-10 21:08** — PR #3068 merged to master (17 parallel streams)
- **2026-04-10 21:18** — First deploy: tests passed but production 500 errors on all course_contents queries
- **Root cause:** PostgreSQL ALTER TABLE migrations blocked by `pg_advisory_lock(1)` held by previous Cloud Run instance
- **2026-04-11 01:00–04:00** — Multiple hotfix attempts: deferred columns, synchronous migrations, advisory lock fix
- **2026-04-11 ~17:30** — Final resolution: columns manually added via Cloud SQL Studio + code redeployed with columns enabled
- **2026-04-11 17:40** — PR #3085 merged (Gmail callback, classifier prompt, pagination, PDF export, guide cleanup, digest format)

### Lessons Learned
1. **pg_advisory_lock blocks forever** — replaced with pg_try_advisory_lock (3 retries, 5s wait)
2. **SQLAlchemy deferred() doesn't prevent INSERT crashes** — only affects SELECT queries
3. **Pydantic from_attributes triggers deferred loads** — response schema fields must match actual DB columns
4. **Cloud Run keeps old instances alive** — must use `gcloud run services update-traffic --to-latest` after deploy
5. **Module-level logger output may not reach Cloud Run logs** — use print(flush=True) for startup debugging
6. **Admin migration endpoint added** — POST /api/admin/run-migrations for future column additions

### Issues Created During Deployment
- #3070–#3075: PR review findings (all fixed)
- #3077–#3078: Enhancement suggestions (pagination, PDF export — fixed in #3085)
- #3079: Advisory lock root cause (fixed)
- #3080: Re-enable columns (fixed)
- #3081–#3082: Documentation (added to CLAUDE.md)
- #3083: Gmail callback (fixed in #3085)
