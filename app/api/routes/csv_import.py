"""CSV template import endpoints (#2167)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.csv_import_service import get_template_csv, import_csv, TEMPLATES

router = APIRouter(tags=["CSV Import"])

VALID_TYPES = set(TEMPLATES.keys())


@router.get("/import/templates/{template_type}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def download_template(
    request: Request,
    template_type: str,
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER)),
):
    """Download a blank CSV template with the correct headers."""
    if template_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid template type. Must be one of: {', '.join(sorted(VALID_TYPES))}")

    csv_content = get_template_csv(template_type)
    filename = f"{template_type}_template.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/csv")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def upload_csv(
    request: Request,
    template_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER)),
):
    """Upload and import a CSV file. Returns import results with per-row errors."""
    if template_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid template type. Must be one of: {', '.join(sorted(VALID_TYPES))}")

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv file")

    # Limit file size to 1MB
    content = await file.read()
    if len(content) > 1_048_576:
        raise HTTPException(status_code=400, detail="File size must be under 1MB")

    result = import_csv(db, template_type, content, current_user)
    return result
