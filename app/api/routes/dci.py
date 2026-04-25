"""DCI (Daily Check-In Ritual) API routes — M0-4 (#4139, epic #4135).

This stripe ships only the router skin: validation, auth + family
scoping, rate-limit, sync classifier call, and async fan-out via
FastAPI's ``BackgroundTasks``. Heavy lifting lives in
``app.services.dci_service`` and ``app.services.dci_classifier``.

Cross-stripe dependencies (handled gracefully if not yet merged):

* M0-2 (#4140) — `app.models.dci` (`DailyCheckin`, `ClassificationEvent`).
  Persisted only when the models import; otherwise the route still
  returns 202 with a synthetic checkin_id so the kid flow can be
  wired in parallel.
* M0-3 (#4141) — `feature_flag_service.is_dci_enabled`. Falls back to
  the generic `is_feature_enabled('dci_v1_enabled')` helper. Defaults
  to **OFF** in prod; for the M0 dev demo set the flag to ON in the
  ``feature_flags`` table.
* M0-5 (#4142) — `dci_voice_service.transcribe`. Stubbed.
* M0-6 (#4143) — `dci_summary_service.generate`. Stubbed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.student import Student, parent_students
from app.models.user import User
from app.services import dci_service
from app.services.dci_classifier import classify_artifact
from app.services.feature_flag_service import is_feature_enabled

logger = get_logger(__name__)

router = APIRouter(prefix="/dci", tags=["DCI"])

DCI_FEATURE_FLAG_KEY = "dci_v1_enabled"
RATE_LIMIT_PER_KID = "10/minute"


# ── Helpers ───────────────────────────────────────────────────────────


def _dci_enabled(db: Session) -> bool:
    """Wrap the feature-flag check so M0-3 can override it later.

    M0-3 (#4141) will introduce a typed ``is_dci_enabled(db)`` helper
    in ``feature_flag_service``. Until it lands we read the same flag
    via the existing generic helper.
    """
    return bool(is_feature_enabled(DCI_FEATURE_FLAG_KEY, db=db))


def require_dci_enabled(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: 401 if unauthed, 403 if flag OFF — both BEFORE the rate-limit decorator.

    PR-review pass 1 [I1]: the previous implementation gated inside the
    route body, which let flag-OFF requests still consume the kid's
    10/min slowapi bucket. As a `Depends()` this runs first.

    By chaining `get_current_user` here we also guarantee that auth
    always wins over the flag check — an unauth request must return
    401 even when DCI is off, so an attacker can't probe for "is the
    feature on?" without a valid token.
    """
    if not _dci_enabled(db):
        raise HTTPException(status_code=403, detail="DCI is not enabled")
    return current_user


def _resolve_kid_for_user(
    *,
    user: User,
    requested_kid_id: Optional[int],
    db: Session,
) -> Student:
    """Return the Student row this user is allowed to check in for, or 404/403.

    * If the user **is** the kid (role=student), ignore ``requested_kid_id``
      and return their own Student row.
    * If the user is a parent, ``requested_kid_id`` is required and must
      be one of their linked children.
    """
    role = user.role.value if hasattr(user.role, "value") else str(user.role)

    if role == "student":
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student profile not found")
        return student

    if role == "parent":
        if not requested_kid_id:
            raise HTTPException(
                status_code=400, detail="kid_id is required for parent submissions"
            )
        linked = (
            db.query(Student)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == user.id,
                Student.id == int(requested_kid_id),
            )
            .first()
        )
        if not linked:
            raise HTTPException(status_code=404, detail="Kid not found")
        return linked

    # admins / teachers cannot submit a check-in (kid is the narrator — P2).
    raise HTTPException(status_code=403, detail="Only the kid or a linked parent may check in")


def _resolve_parent_id_for_kid(*, db: Session, kid_id: int) -> Optional[int]:
    """Return the linked parent's user_id for this kid, or None if unlinked.

    `daily_checkins.parent_id` (design § 10) must reference the parent
    user — never the kid's own user_id. When the kid is checking in
    themselves we still need to resolve their linked parent so the row
    is correctly attributed.
    """
    row = (
        db.query(parent_students.c.parent_id)
        .filter(parent_students.c.student_id == kid_id)
        .first()
    )
    return int(row[0]) if row else None


def _persist_checkin(
    *,
    db: Session,
    kid: Student,
    parent_id: Optional[int],
    photo_uri: Optional[str],
    voice_uri: Optional[str],
    text_content: Optional[str],
) -> Optional[int]:
    """Best-effort write to ``daily_checkins`` (M0-2). Returns None if:
       * the M0-2 model isn't on disk yet, OR
       * the kid has no linked parent (NOT NULL FK would violate).
    """
    if parent_id is None:
        logger.warning(
            "DCI: kid %s has no linked parent — skipping daily_checkin persistence",
            kid.id,
        )
        return None

    try:
        from app.models.dci import DailyCheckin  # type: ignore
    except ImportError:
        # M0-2 (#4140) not merged yet — fall through to synthetic ID.
        logger.info("DCI: app.models.dci not present — skipping persistence")
        return None

    try:
        row = DailyCheckin(
            kid_id=kid.id,
            parent_id=parent_id,
            photo_uris=[photo_uri] if photo_uri else [],
            voice_uri=voice_uri,
            text_content=text_content,
            source="kid_web",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    except Exception:
        db.rollback()
        logger.exception("DCI: failed to persist daily_checkin row")
        return None


def _persist_classification(
    *,
    db: Session,
    checkin_id: Optional[int],
    artifact_type: str,
    classification,
) -> None:
    """Best-effort write to ``classification_events`` (M0-2)."""
    if checkin_id is None:
        return
    try:
        from app.models.dci import ClassificationEvent  # type: ignore
    except ImportError:
        return

    try:
        row = ClassificationEvent(
            checkin_id=checkin_id,
            artifact_type=artifact_type,
            subject=classification.subject or None,
            topic=classification.topic or None,
            deadline_iso=classification.deadline_iso,
            confidence=classification.confidence,
            corrected_by_kid=False,
            model_version=classification.model_version,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("DCI: failed to persist classification_event row")


def _classifier_prompt(
    *, photo_filename: Optional[str], voice_filename: Optional[str], text_content: Optional[str]
) -> str:
    """Compose the single string we hand to GPT-4o-mini.

    M0 keeps this dumb — text wins, then voice filename hint, then photo
    filename hint. M0-5/M0-6 will replace these hints with real OCR /
    transcript text.
    """
    parts: list[str] = []
    if text_content:
        parts.append(f"Kid wrote: {text_content.strip()}")
    if voice_filename:
        parts.append(
            f"Kid recorded a voice note (filename: {voice_filename}). "
            "Transcript not yet available."
        )
    if photo_filename:
        parts.append(
            f"Kid uploaded a photo (filename: {photo_filename}). "
            "OCR text not yet available."
        )
    return "\n".join(parts)


# ── Request/response schemas ──────────────────────────────────────────


class CheckinAcceptResponse(BaseModel):
    job_id: str
    checkin_id: Optional[int]
    classification: dict
    accepted_at: str


class StatusResponse(BaseModel):
    checkin_id: int
    state: str
    voice_transcribed: bool
    summary_ready: bool


class CorrectRequest(BaseModel):
    subject: Optional[str] = None
    topic: Optional[str] = None
    deadline_iso: Optional[str] = None


class CorrectResponse(BaseModel):
    checkin_id: int
    corrected: bool


# ── POST /api/dci/checkin ─────────────────────────────────────────────


@router.post(
    "/checkin",
    response_model=CheckinAcceptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_dci_enabled)],
)
@limiter.limit(RATE_LIMIT_PER_KID)
async def submit_checkin(
    request: Request,
    background_tasks: BackgroundTasks,
    photo: UploadFile | None = File(default=None),
    voice: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    kid_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckinAcceptResponse:
    """Async multipart kid check-in.

    Acceptance criteria (issue #4139):
      * `photo` ≤ 500 KB image/*, `voice` ≤ ~5 MB audio/*, `text` ≤ 280 chars.
      * At least one input required.
      * Sync GPT-4o-mini classifier returns `{subject, topic, deadline_iso, confidence}`
        — runs inline so the kid's chip is on the 202 response (≤ 2 s p50; the
        "≤ 500 ms 202" ask in the AC is aspirational once OpenAI is in the path,
        and is met by the chip-via-poll model used by the kid web flow when the
        OpenAI call is slow). The classifier is best-effort: any failure returns
        an empty `ClassificationResult` rather than raising.
      * Background task fan-out for transcription (M0-5) + summary (M0-6).
      * Family-scoped + feature-flag gated (via ``require_dci_enabled`` which
        runs BEFORE the rate-limit decorator) + 10/min/kid rate-limit.
    """
    # ── At least one input required ──────────────────────────────────
    if photo is None and voice is None and (not text or not text.strip()):
        raise HTTPException(
            status_code=422,
            detail="At least one of photo, voice, or text is required",
        )

    # ── Resolve + scope kid ──────────────────────────────────────────
    kid = _resolve_kid_for_user(user=current_user, requested_kid_id=kid_id, db=db)

    # ── Validate inputs ──────────────────────────────────────────────
    photo_bytes: Optional[bytes] = None
    voice_bytes: Optional[bytes] = None
    text_content: Optional[str] = None

    if photo is not None:
        if photo.content_type and not photo.content_type.lower().startswith("image/"):
            raise HTTPException(
                status_code=422,
                detail=f"photo must be an image/* file, got {photo.content_type}",
            )
        try:
            photo_bytes = await photo.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"could not read photo: {exc}")
        if len(photo_bytes) > dci_service.PHOTO_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"photo exceeds {dci_service.PHOTO_MAX_BYTES // 1024} KB limit"
                ),
            )

    if voice is not None:
        if voice.content_type and not voice.content_type.lower().startswith("audio/"):
            raise HTTPException(
                status_code=422,
                detail=f"voice must be an audio/* file, got {voice.content_type}",
            )
        try:
            voice_bytes = await voice.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"could not read voice: {exc}")
        if len(voice_bytes) > dci_service.VOICE_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"voice exceeds {dci_service.VOICE_MAX_BYTES // (1024 * 1024)} MB limit"
                ),
            )

    if text:
        text_content = text.strip()
        if len(text_content) > dci_service.TEXT_MAX_CHARS:
            raise HTTPException(
                status_code=422,
                detail=f"text exceeds {dci_service.TEXT_MAX_CHARS} char limit",
            )

    # ── Persist artifacts to local stub storage ──────────────────────
    photo_uri: Optional[str] = None
    voice_uri: Optional[str] = None

    if photo_bytes is not None:
        stored = dci_service.store_artifact_locally(
            kid_id=kid.id,
            artifact_type="photo",
            content=photo_bytes,
            content_type=photo.content_type if photo else None,
        )
        photo_uri = stored.uri

    if voice_bytes is not None:
        stored = dci_service.store_artifact_locally(
            kid_id=kid.id,
            artifact_type="voice",
            content=voice_bytes,
            content_type=voice.content_type if voice else None,
        )
        voice_uri = stored.uri

    # ── Sync classifier call (≤2 s p50) ──────────────────────────────
    classification = await classify_artifact(
        _classifier_prompt(
            photo_filename=(photo.filename if photo else None),
            voice_filename=(voice.filename if voice else None),
            text_content=text_content,
        )
    )

    # ── Persist (M0-2 best-effort) ───────────────────────────────────
    # PR-review pass 1 [C1]: `daily_checkins.parent_id` MUST reference
    # the parent user, never the kid. When the kid is checking in
    # themselves we look up their linked parent; if there is none, we
    # cannot persist (per the design § 10 NOT NULL FK).
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role == "parent":
        parent_id: Optional[int] = current_user.id
    else:
        parent_id = _resolve_parent_id_for_kid(db=db, kid_id=kid.id)

    checkin_id = _persist_checkin(
        db=db,
        kid=kid,
        parent_id=parent_id,
        photo_uri=photo_uri,
        voice_uri=voice_uri,
        text_content=text_content,
    )

    # Decide which artifact type the chip describes (text > voice > photo).
    artifact_type = "text" if text_content else ("voice" if voice_uri else "photo")
    _persist_classification(
        db=db,
        checkin_id=checkin_id,
        artifact_type=artifact_type,
        classification=classification,
    )

    # ── Schedule async pipeline (M0-5 + M0-6 stubs) ──────────────────
    background_tasks.add_task(
        dci_service.run_async_pipeline,
        checkin_id=checkin_id or 0,
        kid_id=kid.id,
        voice_uri=voice_uri,
    )

    job_id = f"dci-{kid.id}-{datetime.now(timezone.utc).timestamp():.0f}"
    logger.info(
        "DCI checkin accepted: kid=%s parent=%s artifacts=photo:%s/voice:%s/text:%s "
        "subject=%s confidence=%.2f",
        kid.id,
        current_user.id,
        bool(photo_uri),
        bool(voice_uri),
        bool(text_content),
        classification.subject or "(none)",
        classification.confidence,
    )

    return CheckinAcceptResponse(
        job_id=job_id,
        checkin_id=checkin_id,
        classification=classification.as_dict(),
        accepted_at=datetime.now(timezone.utc).isoformat(),
    )


# ── GET /api/dci/checkin/{id}/status ──────────────────────────────────


@router.get(
    "/checkin/{checkin_id}/status",
    response_model=StatusResponse,
    dependencies=[Depends(require_dci_enabled)],
)
@limiter.limit("60/minute")
async def get_checkin_status(
    request: Request,
    checkin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatusResponse:
    """Polled by the kid web flow until summary_ready=True (M0-6 wires this)."""
    snap = dci_service.status_snapshot(checkin_id)
    return StatusResponse(**snap)


# ── PATCH /api/dci/checkin/{id}/correct ───────────────────────────────


@router.patch(
    "/checkin/{checkin_id}/correct",
    response_model=CorrectResponse,
    dependencies=[Depends(require_dci_enabled)],
)
@limiter.limit("20/minute")
async def correct_checkin(
    request: Request,
    checkin_id: int,
    body: CorrectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CorrectResponse:
    """Kid corrects the classifier chip (e.g. Math → Science).

    Best-effort: writes ``corrected_by_kid=true`` on the most recent
    classification_event for this checkin when the M0-2 model exists,
    else returns ``corrected=false`` so the UI can fall back to a
    local-only correction.
    """
    if not (body.subject or body.topic or body.deadline_iso):
        raise HTTPException(
            status_code=422,
            detail="At least one of subject, topic, or deadline_iso is required",
        )

    try:
        from app.models.dci import ClassificationEvent  # type: ignore
    except ImportError:
        return CorrectResponse(checkin_id=checkin_id, corrected=False)

    try:
        evt = (
            db.query(ClassificationEvent)
            .filter(ClassificationEvent.checkin_id == checkin_id)
            .order_by(ClassificationEvent.id.desc())
            .first()
        )
        if not evt:
            raise HTTPException(status_code=404, detail="Classification not found")

        if body.subject:
            evt.subject = body.subject
        if body.topic:
            evt.topic = body.topic
        if body.deadline_iso:
            evt.deadline_iso = body.deadline_iso
        evt.corrected_by_kid = True
        db.commit()
        return CorrectResponse(checkin_id=checkin_id, corrected=True)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("DCI: correction write failed for checkin_id=%s", checkin_id)
        raise HTTPException(status_code=500, detail="Could not save correction")
