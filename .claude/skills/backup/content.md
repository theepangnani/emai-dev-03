# /content - Course Content & File Upload

## 1. Course Content (Lightweight Reference Links)

Manage structured content items attached to courses (notes, syllabus, labs, assignments, readings, resources, other).

### Architecture
- **Model**: `app/models/course_content.py` — `CourseContent` with `course_id` FK, `content_type` (String(20)), `reference_url`, `google_classroom_url`
- **Schemas**: `app/schemas/course_content.py` — Create/Update/Response with `field_validator` for content_type normalization
- **Routes**: `app/api/routes/course_contents.py` — CRUD at `/api/course-contents/`
- **Content types**: `notes`, `syllabus`, `labs`, `assignments`, `readings`, `resources`, `other`

### API
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/course-contents/` | Create content item |
| GET | `/api/course-contents/?course_id=N` | List by course |
| GET | `/api/course-contents/{id}` | Get single item |
| PATCH | `/api/course-contents/{id}` | Update (creator only) |
| DELETE | `/api/course-contents/{id}` | Delete (creator only) |

### Frontend
- `courseContentsApi` in `frontend/src/api/client.ts`
- CoursesPage: expandable cards with content panel, color-coded type badges
- Add/Edit modal uses shared `.modal-overlay`/`.modal` from Dashboard.css

---

## 2. File Upload System (PDF, Word, OCR)

Standalone file upload for manual course material uploads.

### Architecture
- **Model**: `app/models/content.py` — `Content` with `content_type`, `storage_path`, `extracted_text`
- **Schemas**: `app/schemas/content.py` — `ContentUpload`, `ContentResponse`
- **File processing**: `app/services/file_processor.py` — PDF (PyPDF2), Word (python-docx), Images (pytesseract OCR)

### API
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/content/upload` | Upload file |
| POST | `/api/content/text` | Submit text directly |
| GET | `/api/content` | List user's content |
| GET | `/api/content/{id}` | Get specific content |
| DELETE | `/api/content/{id}` | Delete content |
| POST | `/api/content/{id}/generate` | Generate study material |

### Storage
- Dev: `uploads/` directory
- Prod: Google Cloud Storage (`GCS_BUCKET_NAME` env var)

### Dependencies
PyPDF2, python-docx, pytesseract, Pillow, python-multipart
