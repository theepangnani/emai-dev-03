# /content-upload - Scaffold Content Upload Feature

Create the content upload system for manual course material uploads.

## Feature Overview

This feature allows users to upload course content manually:
- PDF documents
- Word documents (.doc, .docx)
- Text notes
- Images with OCR

## Instructions

When implementing this feature, create the following:

### 1. Backend Model (app/models/content.py)

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db.database import Base


class ContentType(str, enum.Enum):
    PDF = "pdf"
    WORD = "word"
    TEXT = "text"
    IMAGE = "image"


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    title = Column(String(255), nullable=False)
    content_type = Column(String(50), nullable=False)
    original_filename = Column(String(255))
    storage_path = Column(String(500))  # GCS path or local path
    extracted_text = Column(Text)  # OCR/parsed text
    tags = Column(String(500))  # Comma-separated tags
    is_public = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="contents")
    course = relationship("Course", back_populates="contents")
```

### 2. Backend Schema (app/schemas/content.py)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ContentUpload(BaseModel):
    title: str
    course_id: Optional[int] = None
    tags: Optional[str] = None
    is_public: bool = False


class ContentResponse(BaseModel):
    id: int
    title: str
    content_type: str
    original_filename: Optional[str]
    extracted_text: Optional[str]
    tags: Optional[str]
    is_public: bool
    version: int
    created_at: datetime

    class Config:
        from_attributes = True
```

### 3. Backend Routes (app/api/routes/content.py)

Key endpoints to implement:
- `POST /api/content/upload` - Upload file
- `POST /api/content/text` - Submit text directly
- `GET /api/content` - List user's content
- `GET /api/content/{id}` - Get specific content
- `DELETE /api/content/{id}` - Delete content
- `POST /api/content/{id}/generate` - Generate study material from content

### 4. File Processing Service (app/services/file_processor.py)

Implement handlers for each content type:
- PDF: Use PyPDF2 or pdfplumber
- Word: Use python-docx
- Images: Use pytesseract for OCR
- Text: Direct storage

### 5. Frontend Components

- `ContentUploadModal.tsx` - File upload modal
- `ContentList.tsx` - Display user's uploaded content
- `ContentViewer.tsx` - View content details

## Dependencies to Add

### Backend (requirements.txt)
```
PyPDF2>=3.0.0
python-docx>=1.1.0
pytesseract>=0.3.10
Pillow>=10.0.0
python-multipart>=0.0.6
```

### System Requirements
- Tesseract OCR installed for image text extraction

## API Usage Example

```bash
# Upload a file
curl -X POST http://localhost:8000/api/content/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf" \
  -F "title=Chapter 5 Notes" \
  -F "course_id=1" \
  -F "tags=math,algebra"

# Upload text directly
curl -X POST http://localhost:8000/api/content/text \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Notes",
    "content": "Notes content here...",
    "course_id": 1
  }'
```

## Storage Options

### Development
- Store files locally in `uploads/` directory

### Production
- Use Google Cloud Storage bucket
- Configure via `GCS_BUCKET_NAME` environment variable

## Related Issues

- GitHub Issue #25: Manual content upload and OCR
- GitHub Issue #28: Central document repository
