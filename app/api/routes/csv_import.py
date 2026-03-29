"""CSV template import endpoints (#2167)."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.csv_import_service import (
    TEMPLATES,
    generate_template_csv,
    import_assignments,
    import_courses,
    import_students,
    parse_csv,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["CSV Import"])


@router.get("/templates/{template_type}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def download_template(
    request: Request,
    template_type: str,
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER, UserRole.ADMIN)),
):
    """Download a blank CSV template with headers."""
    if template_type not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown template type: {template_type}. Valid types: {', '.join(TEMPLATES.keys())}")

    csv_content = generate_template_csv(template_type)
    filename = f"{template_type}_template.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/templates")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
async def list_templates(
    request: Request,
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER, UserRole.ADMIN)),
):
    """List available CSV template types with their columns."""
    result = []
    for name, columns in TEMPLATES.items():
        result.append({
            "type": name,
            "columns": [
                {"name": col, "required": req, "description": desc}
                for col, (req, desc) in columns.items()
            ],
        })
    return result


@router.post("/csv")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def upload_csv(
    request: Request,
    template_type: str = Query(..., description="Template type: students, courses, or assignments"),
    file: UploadFile = File(...),
    confirm: bool = Query(False, description="Set to true to actually import (otherwise preview only)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.TEACHER, UserRole.ADMIN)),
):
    """Upload and parse/import a CSV file.

    Without confirm=true, returns a preview with validation results.
    With confirm=true, imports valid rows into the database.
    """
    if template_type not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown template type: {template_type}")

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv file")

    # Read file content
    try:
        content_bytes = await file.read()
        if len(content_bytes) > 5 * 1024 * 1024:  # 5 MB
            raise HTTPException(status_code=400, detail="CSV file too large (max 5 MB)")
        content = content_bytes.decode("utf-8-sig")  # Handle BOM from Excel
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read file")

    # Parse and validate
    result = parse_csv(template_type, content)

    if not confirm:
        return {
            "preview": True,
            "template_type": template_type,
            "rows": result["rows"],
            "errors": result["errors"],
            "total": result["total"],
            "valid": result["valid"],
        }

    # Import
    if result["errors"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "CSV has validation errors. Fix errors and re-upload.",
                "errors": result["errors"],
            },
        )

    if not result["rows"]:
        raise HTTPException(status_code=400, detail="No valid rows to import")

    importers = {
        "students": import_students,
        "courses": import_courses,
        "assignments": import_assignments,
    }

    import_result = importers[template_type](db, result["rows"], current_user)

    if import_result["errors"] and import_result["created"] == 0:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Import failed due to errors.",
                "errors": import_result["errors"],
            },
        )

    return {
        "preview": False,
        "template_type": template_type,
        "created": import_result["created"],
        "skipped": import_result["skipped"],
        "errors": import_result["errors"],
    }
