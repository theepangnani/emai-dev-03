"""Data export endpoints (PIPEDA Right of Access)."""
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User
from app.models.data_export import DataExportRequest
from app.schemas.data_export import DataExportRequestResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/users/me", tags=["Data Export"])


def _build_response(export: DataExportRequest) -> DataExportRequestResponse:
    """Build response with computed download URL."""
    download_url = None
    if export.status == "completed" and export.expires_at:
        now = datetime.now(timezone.utc)
        expires_at = export.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at > now:
            download_url = f"/api/users/me/exports/{export.download_token}/download"
    return DataExportRequestResponse(
        id=export.id,
        status=export.status,
        created_at=export.created_at,
        completed_at=export.completed_at,
        expires_at=export.expires_at,
        download_url=download_url,
    )


@router.post("/export", response_model=DataExportRequestResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/hour", key_func=get_user_id_or_ip)
def request_data_export(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Request a data export. Creates a background job to generate the export ZIP.

    Rate limited to 3 requests per hour per user.
    """
    # Check for pending/processing exports — don't allow overlapping requests
    active_export = db.query(DataExportRequest).filter(
        DataExportRequest.user_id == current_user.id,
        DataExportRequest.status.in_(["pending", "processing"]),
    ).first()
    if active_export:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An export is already in progress. Please wait for it to complete.",
        )

    # Create export request
    download_token = secrets.token_urlsafe(48)
    export_request = DataExportRequest(
        user_id=current_user.id,
        status="pending",
        download_token=download_token,
    )
    db.add(export_request)
    db.commit()
    db.refresh(export_request)

    # Process synchronously for now (small datasets).
    # For large datasets, this should be moved to a background worker.
    from app.services.data_export_service import process_export_request
    process_export_request(db, export_request.id)

    # Refresh to get updated status
    db.refresh(export_request)
    return _build_response(export_request)


@router.get("/exports", response_model=list[DataExportRequestResponse])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def list_exports(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's data export requests."""
    exports = db.query(DataExportRequest).filter(
        DataExportRequest.user_id == current_user.id
    ).order_by(DataExportRequest.created_at.desc()).limit(10).all()
    return [_build_response(e) for e in exports]


@router.get("/exports/{token}/download")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def download_export(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a completed data export by token.

    Token-based access with 48-hour expiry. Only the requesting user can download.
    """
    export = db.query(DataExportRequest).filter(
        DataExportRequest.download_token == token,
        DataExportRequest.user_id == current_user.id,
    ).first()

    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")

    if export.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export is not ready (status: {export.status})",
        )

    # Check expiry
    if export.expires_at:
        expires_at = export.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Export download link has expired. Please request a new export.",
            )

    if not export.file_path or not os.path.exists(export.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found. It may have been cleaned up.",
        )

    filename = f"classbridge_data_export_{current_user.id}.zip"
    return FileResponse(
        path=export.file_path,
        media_type="application/zip",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
