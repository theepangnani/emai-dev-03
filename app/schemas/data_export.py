from datetime import datetime

from pydantic import BaseModel


class DataExportRequestResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    download_url: str | None = None

    class Config:
        from_attributes = True


class DataExportRequestCreate(BaseModel):
    """Empty body — just triggers the export."""
    pass
