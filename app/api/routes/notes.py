import io
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, File, status
from PIL import Image
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.note import Note
from app.models.note_image import NoteImage
from app.models.note_version import NoteVersion
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.note import NoteListItem, NoteResponse, NoteUpsert, NoteVersionListItem, NoteVersionResponse
from app.schemas.note_image import NoteImageResponse
from app.services.gcs_service import upload_file as gcs_upload_file, download_file as gcs_download_file

router = APIRouter(prefix="/notes", tags=["Notes"])


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace to produce plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _has_images(html: str) -> bool:
    """Check if HTML content contains image tags or base64 image data."""
    return bool(re.search(r"<img[\s>]", html, re.IGNORECASE))


def _get_linked_child_user_ids(db: Session, parent_id: int) -> list[int]:
    """Return user_ids for all children linked to the given parent."""
    rows = db.query(parent_students.c.student_id).filter(
        parent_students.c.parent_id == parent_id
    ).all()
    child_student_ids = [r[0] for r in rows]
    if not child_student_ids:
        return []
    students = db.query(Student.user_id).filter(
        Student.id.in_(child_student_ids)
    ).all()
    return [s[0] for s in students]


def _save_version(db: Session, note: Note, user_id: int) -> NoteVersion:
    """Save the current note content as a new version before updating."""
    max_version = db.query(sa_func.coalesce(sa_func.max(NoteVersion.version_number), 0)).filter(
        NoteVersion.note_id == note.id
    ).scalar()

    version = NoteVersion(
        note_id=note.id,
        content=note.content,
        version_number=max_version + 1,
        created_by_user_id=user_id,
    )
    db.add(version)
    return version


def _verify_note_access(db: Session, note: Note, current_user: User) -> None:
    """Raise 404 if user cannot access the note."""
    if note.user_id == current_user.id:
        return
    if current_user.has_role(UserRole.PARENT):
        child_user_ids = _get_linked_child_user_ids(db, current_user.id)
        if note.user_id in child_user_ids:
            return
    if current_user.has_role(UserRole.ADMIN):
        return
    raise HTTPException(status_code=404, detail="Note not found")


@router.get("/", response_model=list[NoteListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_notes(
    request: Request,
    course_content_id: int | None = Query(None),
    user_id: int | None = Query(None, description="Filter by user (admin only)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notes for the current user, optionally filtered by course_content_id."""
    query = db.query(Note)

    if current_user.has_role(UserRole.ADMIN) and user_id is not None:
        query = query.filter(Note.user_id == user_id)
    else:
        query = query.filter(Note.user_id == current_user.id)

    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)

    query = query.order_by(Note.updated_at.desc().nullsfirst(), Note.created_at.desc())
    return query.offset(offset).limit(limit).all()


@router.get("/children/{student_id}", response_model=list[NoteListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_child_notes(
    request: Request,
    student_id: int,
    course_content_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parent endpoint: list notes for a linked child (read-only)."""
    if not current_user.has_role(UserRole.PARENT):
        raise HTTPException(status_code=403, detail="Only parents can access children's notes")

    child_user_ids = _get_linked_child_user_ids(db, current_user.id)
    if student_id not in child_user_ids:
        raise HTTPException(status_code=403, detail="Student is not linked to your account")

    query = db.query(Note).filter(Note.user_id == student_id)
    if course_content_id is not None:
        query = query.filter(Note.course_content_id == course_content_id)

    query = query.order_by(Note.updated_at.desc().nullsfirst(), Note.created_at.desc())
    return query.offset(offset).limit(limit).all()


@router.get("/{note_id}", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single note. Owner sees own; parent can see child's note."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    _verify_note_access(db, note, current_user)
    return note


@router.put("/", response_model=NoteResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def upsert_note(
    request: Request,
    data: NoteUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a note. Empty content auto-deletes the note."""
    plain = _strip_html(data.content)

    # Empty content -> auto-delete
    if not plain:
        existing = db.query(Note).filter(
            Note.user_id == current_user.id,
            Note.course_content_id == data.course_content_id,
        ).first()
        if existing:
            # Save version before deleting
            if existing.content and existing.content.strip():
                _save_version(db, existing, current_user.id)
            db.delete(existing)
            db.commit()
        return Response(status_code=204)

    existing = db.query(Note).filter(
        Note.user_id == current_user.id,
        Note.course_content_id == data.course_content_id,
    ).first()

    if existing:
        # Save current content as a version before overwriting
        if existing.content and existing.content != data.content:
            _save_version(db, existing, current_user.id)
        existing.content = data.content
        existing.plain_text = plain
        existing.has_images = _has_images(data.content)
        existing.highlights_json = data.highlights_json
        db.commit()
        db.refresh(existing)
        return existing

    note = Note(
        user_id=current_user.id,
        course_content_id=data.course_content_id,
        content=data.content,
        plain_text=plain,
        has_images=_has_images(data.content),
        highlights_json=data.highlights_json,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_note(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a note. Owner only."""
    note = db.query(Note).filter(
        Note.id == note_id,
        Note.user_id == current_user.id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()


# --- Version history endpoints ---

@router.get("/{note_id}/versions", response_model=list[NoteVersionListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_versions(
    request: Request,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all saved versions for a note."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    _verify_note_access(db, note, current_user)

    versions = db.query(NoteVersion).filter(
        NoteVersion.note_id == note_id
    ).order_by(NoteVersion.version_number.desc()).all()

    result = []
    for v in versions:
        plain = _strip_html(v.content)
        result.append(NoteVersionListItem(
            id=v.id,
            note_id=v.note_id,
            version_number=v.version_number,
            created_at=v.created_at,
            created_by_user_id=v.created_by_user_id,
            preview=plain[:120] + ("..." if len(plain) > 120 else ""),
        ))
    return result


@router.get("/{note_id}/versions/{version_id}", response_model=NoteVersionResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_version(
    request: Request,
    note_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View a specific version's full content."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    _verify_note_access(db, note, current_user)

    version = db.query(NoteVersion).filter(
        NoteVersion.id == version_id,
        NoteVersion.note_id == note_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{note_id}/restore/{version_id}", response_model=NoteResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def restore_version(
    request: Request,
    note_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore a previous version. Saves the current content as a new version first."""
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    # Only owner can restore
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the note owner can restore versions")

    version = db.query(NoteVersion).filter(
        NoteVersion.id == version_id,
        NoteVersion.note_id == note_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    # Save current content as a new version before restoring
    if note.content and note.content != version.content:
        _save_version(db, note, current_user.id)

    # Restore the old version's content
    note.content = version.content
    note.plain_text = _strip_html(version.content)
    note.has_images = _has_images(version.content)
    db.commit()
    db.refresh(note)
    return note


# --- Note image endpoints ---

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_WIDTH = 1200


def _compress_note_image(image_bytes: bytes, max_width: int = MAX_IMAGE_WIDTH) -> tuple[bytes, str]:
    """Resize image to max_width and compress. Returns (compressed_bytes, media_type)."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
    # Keep PNG for images with transparency
    if img.mode in ("RGBA", "LA", "P"):
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), "image/png"
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"


def _verify_image_access(db: Session, image: NoteImage, current_user: User) -> None:
    """Raise 404 if user cannot access the image."""
    if image.user_id == current_user.id:
        return
    if current_user.has_role(UserRole.PARENT):
        child_user_ids = _get_linked_child_user_ids(db, current_user.id)
        if image.user_id in child_user_ids:
            return
    if current_user.has_role(UserRole.ADMIN):
        return
    raise HTTPException(status_code=404, detail="Image not found")


@router.post("/images", response_model=NoteImageResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def upload_note_image(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an image for use in notes."""
    # Validate content type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Allowed: {', '.join(sorted(ALLOWED_IMAGE_TYPES))}",
        )

    # Read file and validate size
    file_bytes = file.file.read()
    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)} MB.",
        )

    # Compress image
    try:
        compressed_bytes, media_type = _compress_note_image(file_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not process image. The file may be corrupt.")

    # Determine file extension from media_type
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}
    ext = ext_map.get(media_type, "jpg")
    gcs_path = f"notes/{current_user.id}/{uuid.uuid4().hex}.{ext}"

    # Upload to GCS
    try:
        gcs_upload_file(gcs_path, compressed_bytes, media_type)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to upload image. Please try again.")

    # Create DB record
    note_image = NoteImage(
        user_id=current_user.id,
        gcs_path=gcs_path,
        media_type=media_type,
        file_size=len(compressed_bytes),
    )
    db.add(note_image)
    db.commit()
    db.refresh(note_image)

    return NoteImageResponse(
        id=note_image.id,
        note_id=note_image.note_id,
        user_id=note_image.user_id,
        media_type=note_image.media_type,
        file_size=note_image.file_size,
        created_at=note_image.created_at,
        image_url=f"/api/notes/images/{note_image.id}",
    )


@router.get("/images/{image_id}")
@limiter.limit("120/minute", key_func=get_user_id_or_ip)
def serve_note_image(
    request: Request,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve a note image. Auth: owner, parent of owner, or admin."""
    image = db.query(NoteImage).filter(NoteImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    _verify_image_access(db, image, current_user)

    # Download from GCS
    try:
        image_bytes = gcs_download_file(image.gcs_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Image file not found in storage")

    return Response(
        content=image_bytes,
        media_type=image.media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


def cleanup_old_versions(db: Session) -> int:
    """Delete note versions older than 365 days. Returns count of deleted rows."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    count = db.query(NoteVersion).filter(NoteVersion.created_at < cutoff).delete()
    db.commit()
    return count
