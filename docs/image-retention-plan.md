# Image Retention in Study Guides — Implementation Plan & Cost Analysis

**Project:** EMAI (ClassBridge)
**Date:** 2026-03-07
**Status:** Approved for Implementation
**GitHub Issues:** #1308, #1309, #1310, #1311, #1312, #1313

---

## 1. Problem Statement

When users upload documents (PDF, DOCX, PPTX) containing images — diagrams, charts, formulas, screenshots — the study guide generation pipeline extracts text via OCR but **discards the original image binaries**. The resulting study guides are text-only, losing valuable visual context that is critical for learning.

### Impact
- Students lose diagrams, charts, and visual aids that are essential for subjects like science, math, and geography
- Teachers' carefully crafted visual materials are reduced to text descriptions
- Study guide quality is significantly lower than the source material

---

## 2. Current Architecture

```
Document Upload
    └── file_processor.py
         ├── Text extraction (paragraphs, tables, headers)
         ├── Image extraction (DOCX only)
         │    └── Vision OCR → text description
         │         └── Text appended to content ← images DISCARDED here
         └── text_content stored in CourseContent table

Study Guide Generation
    └── ai_service.py
         ├── Input: text_content (text only)
         ├── AI model: Claude (configurable)
         └── Output: Markdown text (no images)

Frontend Rendering
    └── MarkdownBody component
         └── Renders markdown → HTML (text only)
```

---

## 3. Proposed Solution: Image Extraction + Reference Embedding

### Architecture Overview

```
Document Upload (Enhanced)
    └── file_processor.py
         ├── Text extraction (unchanged)
         └── Image extraction (enhanced)
              ├── Extract images from PDF, DOCX, PPTX
              ├── Capture surrounding text context
              ├── Run Vision OCR (existing — no new cost)
              ├── Compress/resize to max 800px width
              └── Store as ContentImage records (NEW)

Study Guide Generation (Enhanced)
    └── ai_service.py
         ├── Input: text_content + image metadata
         │    └── "[IMG-1] Photosynthesis diagram (near: 'Light reactions...')"
         ├── AI returns markdown with {{IMG-N}} placement markers
         └── Post-processing: append unplaced images as "Additional Figures"

Frontend Rendering (Enhanced)
    └── MarkdownBody component
         ├── Parse {{IMG-N}} markers
         ├── Replace with <img> tags pointing to image serving endpoint
         └── Render images inline within study guide
```

---

## 4. Implementation Tasks

### Batch 1 — Foundation (must complete first)

| Task | Issue | Description | Files Modified |
|------|-------|-------------|---------------|
| ContentImage model | #1308 | New SQLAlchemy model + migration | `app/models/content_image.py`, `main.py` |

### Batch 2 — Core Features (parallel after Batch 1)

| Task | Issue | Description | Files Modified |
|------|-------|-------------|---------------|
| Image extraction & storage | #1309 | Extract images from PDF/DOCX/PPTX during upload | `app/services/file_processor.py`, `app/api/routes/course_contents.py` |
| AI prompt integration | #1310 | Include image metadata in AI prompts | `app/services/ai_service.py`, `app/api/routes/study.py` |
| Image serving endpoint | #1311 | API to serve stored images | `app/api/routes/course_contents.py` |

### Batch 3 — Frontend & Polish (parallel after Batch 2)

| Task | Issue | Description | Files Modified |
|------|-------|-------------|---------------|
| Frontend rendering | #1312 | Render images inline in study guides | `frontend/src/components/MarkdownBody.tsx`, `frontend/src/pages/StudyGuidePage.tsx` |
| Fallback section | #1313 | Append unplaced images at bottom | `app/api/routes/study.py` |

---

## 5. Cost Analysis

### Current Costs Per Study Guide Generation

| Step | Model | Input Tokens | Output Tokens | Cost |
|------|-------|-------------|---------------|------|
| Content safety check | Haiku 4.5 | ~150 | ~20 | ~$0.0002 |
| Vision OCR (embedded images) | Haiku 4.5 | ~10,000 (10 images) | ~4,096 | ~$0.024 |
| Study guide generation | Configured model | ~2,000-4,000 | ~2,000 | ~$0.01-0.03 |
| **Current Total** | | | | **~$0.03-0.05** |

### Added Costs With Image Retention

| New Step | Model | What Changes | Added Cost |
|----------|-------|-------------|------------|
| Image description storage | None | Reuse existing Vision OCR output (currently discarded) | **$0.00** |
| Extra tokens in prompt | Same model | +500-1,000 tokens for image metadata (10-20 images) | **~$0.002-0.005** |
| Image binary storage | Database | ~50-200KB per image, compressed | Storage only |

### Cost Comparison

| Metric | Current | With Image Retention | Change |
|--------|---------|---------------------|--------|
| Per generation | $0.03-0.05 | $0.035-0.055 | +5-10% |
| Monthly (500 generations) | $15-25 | $17.50-27.50 | +$2.50 |
| Storage (100 docs/month) | — | 50-300MB | ~$0.05-0.09/mo |

### Why NOT Multimodal Generation?

Sending image binaries directly to the AI for study guide generation was considered but rejected:

| Factor | Reference-Based (chosen) | Multimodal |
|--------|------------------------|------------|
| Cost per generation | +$0.002-0.005 | +$0.10-0.50 (10x increase) |
| Token limits | Minimal impact | Hits limits with 5+ images |
| Image quality in output | Original images preserved | AI can't "pass through" images |
| Implementation complexity | Moderate | High |

---

## 6. Database Schema

### New Table: `content_images`

```sql
CREATE TABLE content_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_content_id INTEGER NOT NULL REFERENCES course_contents(id) ON DELETE CASCADE,
    image_data BLOB NOT NULL,
    media_type VARCHAR(50) NOT NULL,
    description TEXT,
    position_context TEXT,
    position_index INTEGER NOT NULL DEFAULT 0,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_content_images_content ON content_images(course_content_id);
```

### Storage Estimates

| Scenario | Images/Doc | Avg Size | Per Document | Monthly (100 docs) |
|----------|-----------|----------|-------------|-------------------|
| Light | 5 | 100KB | 500KB | 50MB |
| Medium | 10 | 150KB | 1.5MB | 150MB |
| Heavy | 20 | 200KB | 4MB | 400MB |

---

## 7. API Changes

### New Endpoints

```
GET  /api/course-contents/{content_id}/images          → List image metadata
GET  /api/course-contents/{content_id}/images/{image_id} → Serve image binary
```

### Modified Functions

```python
# ai_service.py
generate_study_guide(..., images: list[dict] | None = None)
generate_quiz(..., images: list[dict] | None = None)
generate_flashcards(..., images: list[dict] | None = None)

# file_processor.py
extract_and_store_images(file_content, filename, course_content_id, db) → list[ContentImage]
```

---

## 8. Frontend Changes

### MarkdownBody Component
- Parse `{{IMG-N}}` markers in markdown content
- Replace with `<img src="/api/course-contents/{id}/images/{imageId}" />` tags
- Graceful fallback for missing images (show alt text)

### PDF Export
- Fetch images as base64 during PDF generation
- Embed inline in jsPDF output

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| AI ignores image markers | Medium | Low | Fallback "Additional Figures" section (#1313) |
| Large docs with 50+ images | Low | Medium | Cap at 20 images, skip decorative/tiny |
| Image extraction fails | Low | Low | Graceful degradation — text-only guide (current behavior) |
| DB bloat from images | Low | Medium | Compress/resize on ingest, cleanup orphans |
| Performance impact on page load | Low | Medium | Cache headers, lazy loading |

---

## 10. Testing Plan

- **Unit tests:** Image extraction from sample PDF, DOCX, PPTX files
- **Integration tests:** Upload → extract → generate → render flow
- **Regression:** Verify existing study guide generation unchanged when no images
- **Load:** Test with documents containing 20+ images
- **Cross-browser:** Verify image rendering in Chrome, Firefox, Safari

---

## 11. Rollout Plan

1. **Batch 1** → Merge & deploy ContentImage model (no user-facing changes)
2. **Batch 2** → Merge & deploy extraction + AI + endpoint (images start being stored and referenced)
3. **Batch 3** → Merge & deploy frontend rendering (images visible to users)

Each batch is independently deployable with no breaking changes.
