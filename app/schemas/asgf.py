"""Schemas for the Ask-a-Question / Study Guide Flow (ASGF) endpoints."""

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    """Metadata for a single uploaded file."""

    file_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    text_preview: str

    model_config = {"from_attributes": True}


class MultiFileUploadResponse(BaseModel):
    """Response for a multi-file upload request."""

    files: list[FileUploadResponse]
    total_size_bytes: int

    model_config = {"from_attributes": True}
