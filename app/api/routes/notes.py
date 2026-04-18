import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.note import Note
from app.models.note_version import NoteVersion
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.note import NoteListItem, NoteResponse, NoteUpsert, NoteVersionListItem, NoteVersionResponse, SaveAsMaterialRequest, SaveAsMaterialResponse

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


@router.post("/{note_id}/save-as-material", response_model=SaveAsMaterialResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def save_as_material(
    request: Request,
    note_id: int,
    data: SaveAsMaterialRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a CourseContent record from a note's content."""
    from app.models.course import Course, student_courses
    from app.models.course_content import CourseContent

    # Fetch note and verify ownership
    note = db.query(Note).filter(
        Note.id == note_id,
        Note.user_id == current_user.id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Reject empty notes
    if not note.content or not _strip_html(note.content).strip():
        raise HTTPException(status_code=400, detail="Note has no content to save")

    # Verify user has access to the target course
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    has_access = False
    if current_user.has_role(UserRole.ADMIN):
        has_access = True
    elif course.created_by_user_id == current_user.id:
        has_access = True
    else:
        # Check if user (as student) is enrolled in the course
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            enrolled = db.query(student_courses.c.student_id).filter(
                student_courses.c.student_id == student.id,
                student_courses.c.course_id == data.course_id,
            ).first()
            if enrolled:
                has_access = True

        # Check if user (as parent) has a child enrolled in the course
        if not has_access and current_user.has_role(UserRole.PARENT):
            child_user_ids = _get_linked_child_user_ids(db, current_user.id)
            if child_user_ids:
                child_students = db.query(Student.id).filter(Student.user_id.in_(child_user_ids)).all()
                child_student_ids = [s[0] for s in child_students]
                if child_student_ids:
                    enrolled = db.query(student_courses.c.student_id).filter(
                        student_courses.c.student_id.in_(child_student_ids),
                        student_courses.c.course_id == data.course_id,
                    ).first()
                    if enrolled:
                        has_access = True

    if not has_access:
        raise HTTPException(status_code=403, detail="You do not have access to this course")

    # Prevent duplicate materials from the same note content
    existing_material = db.query(CourseContent).filter(
        CourseContent.course_id == data.course_id,
        CourseContent.created_by_user_id == current_user.id,
        CourseContent.source_type == "note",
        CourseContent.text_content == note.content,
    ).first()
    if existing_material:
        raise HTTPException(status_code=409, detail="This note has already been saved as material in this course")

    content = CourseContent(
        course_id=data.course_id,
        title=data.title.strip(),
        text_content=note.content,
        content_type="notes",
        created_by_user_id=current_user.id,
        source_type="note",
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    return SaveAsMaterialResponse(
        id=content.id,
        title=content.title,
        message="Note saved as class material",
    )


def cleanup_old_versions(db: Session) -> int:
    """Delete note versions older than 365 days. Returns count of deleted rows."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    count = db.query(NoteVersion).filter(NoteVersion.created_at < cutoff).delete()
    db.commit()
    return count
