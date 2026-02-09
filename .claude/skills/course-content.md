# /course-content - Course Content Types System

Manage structured content items attached to courses (notes, syllabus, labs, assignments, readings, resources, other).

## Architecture

### Backend

- **Model**: `app/models/course_content.py` — `CourseContent` table with `course_id` FK, `content_type` (String(20), not Enum), `reference_url`, `google_classroom_url`, `created_by_user_id`
- **ContentType enum**: Python enum for validation only; stored as lowercase string in DB for SQLite/PostgreSQL cross-DB compatibility
- **Schemas**: `app/schemas/course_content.py` — `CourseContentCreate`, `CourseContentUpdate`, `CourseContentResponse` with `field_validator` for content_type normalization
- **Routes**: `app/api/routes/course_contents.py` — CRUD at `/api/course-contents/`
- **Indexes**: `ix_course_contents_course` (course_id), `ix_course_contents_type` (course_id, content_type)

### API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/course-contents/` | Any user | Create content item |
| GET | `/api/course-contents/?course_id=N` | Any user | List by course (required param) |
| GET | `/api/course-contents/{id}` | Any user | Get single item |
| PATCH | `/api/course-contents/{id}` | Creator only | Update item |
| DELETE | `/api/course-contents/{id}` | Creator only | Delete item |

### Content Types

`notes`, `syllabus`, `labs`, `assignments`, `readings`, `resources`, `other`

### Frontend

- **API client**: `courseContentsApi` in `frontend/src/api/client.ts` with `CourseContentItem` interface
- **CoursesPage**: Expandable course cards — click to toggle content panel below
- **Content panel**: Lists items with color-coded type badges, reference links, Google Classroom links, edit/delete actions
- **Add/Edit modal**: Uses shared `.modal-overlay`/`.modal` from Dashboard.css; fields for Title*, Type (select), Description, Reference URL, Google Classroom URL
- **CSS**: Content styles in `CoursesPage.css` — `.course-content-panel`, `.content-item`, `.content-type-badge` variants

### Badge Colors

| Type | Background | Text |
|------|-----------|------|
| syllabus | purple 0.12 | #9c27b0 |
| labs | orange 0.12 | #f57c00 |
| readings | blue 0.12 | #1976d2 |
| resources | green 0.12 | #388e3c |
| assignments | red 0.12 | #d32f2f |
| notes/other | teal 0.12 | accent-strong |

## Key Patterns

- Content type stored as `String(20)` not `Enum` — per MEMORY.md cross-DB lesson
- `model_dump(exclude_unset=True)` for partial PATCH updates
- Course relationship uses `backref="contents"` on Course model
- Frontend loads contents lazily on card expand via `courseContentsApi.list(courseId)`

## Related

- `content-upload.md` — File upload system (PDF, Word, OCR) — separate from this lightweight reference link system
- GitHub Issue #116 (closed)
