"""CB-DCI-001 M0-11 — DCI consent + settings service.

Owns:
- Read / upsert ``checkin_consent`` rows (spec § 10 — parent-controlled
  per-(parent, kid) consent for photo / voice / AI processing /
  retention).
- Read / upsert ``checkin_settings`` rows (M0-11 extension — DCI
  on/off, mute, push time pickers).
- ``assert_dci_consent(db, kid_id, parent_id, …)`` helper that M0-4's
  ``POST /api/dci/checkin`` route imports to gate every write.
- Audit trail (``audit_service.log_action``) for every mutation.

Spec: docs/design/CB-DCI-001-daily-checkin.md § 11.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.checkin_consent import CheckinConsent, CheckinSettings
from app.models.student import Student, parent_students
from app.services.audit_service import log_action

# Allowed retention values per spec § 11 ("90d / 1y / 3y").
ALLOWED_RETENTION_DAYS = (90, 365, 1095)

# HH:MM 24h format validator (rough — service-layer guard, not security).
_TIME_LEN = 5


@dataclass(frozen=True)
class ConsentSnapshot:
    """Immutable view of a (parent, kid) consent + settings pair."""

    parent_id: int
    kid_id: int
    photo_ok: bool
    voice_ok: bool
    ai_ok: bool
    retention_days: int
    dci_enabled: bool
    muted: bool
    kid_push_time: str
    parent_push_time: str


def _to_snapshot(
    consent: CheckinConsent | None,
    settings_row: CheckinSettings | None,
    parent_id: int,
    kid_id: int,
) -> ConsentSnapshot:
    return ConsentSnapshot(
        parent_id=parent_id,
        kid_id=kid_id,
        photo_ok=bool(consent.photo_ok) if consent else False,
        voice_ok=bool(consent.voice_ok) if consent else False,
        ai_ok=bool(consent.ai_ok) if consent else False,
        retention_days=int(consent.retention_days) if consent else 90,
        dci_enabled=bool(settings_row.dci_enabled) if settings_row else True,
        muted=bool(settings_row.muted) if settings_row else False,
        kid_push_time=(settings_row.kid_push_time if settings_row else "15:15") or "15:15",
        parent_push_time=(settings_row.parent_push_time if settings_row else "19:00") or "19:00",
    )


def _verify_parent_owns_kid(db: Session, parent_id: int, kid_id: int) -> None:
    """Raise 404 if the kid is not linked to this parent.

    We use 404 rather than 403 to avoid leaking the existence of a kid the
    requester is not authorized to see.
    """
    student = db.query(Student).filter(Student.id == kid_id).first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kid not found")

    link = (
        db.query(parent_students.c.parent_id)
        .filter(
            parent_students.c.parent_id == parent_id,
            parent_students.c.student_id == kid_id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kid not found")


def _validate_time(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != _TIME_LEN or value[2] != ":":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} must be HH:MM (24h)",
        )
    try:
        hh = int(value[:2])
        mm = int(value[3:])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} must be HH:MM (24h)",
        )
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field} must be HH:MM (24h)",
        )
    return value


def _load_consent(db: Session, parent_id: int, kid_id: int) -> CheckinConsent | None:
    return (
        db.query(CheckinConsent)
        .filter(
            CheckinConsent.parent_id == parent_id,
            CheckinConsent.kid_id == kid_id,
        )
        .first()
    )


def _load_settings(db: Session, parent_id: int, kid_id: int) -> CheckinSettings | None:
    return (
        db.query(CheckinSettings)
        .filter(
            CheckinSettings.parent_id == parent_id,
            CheckinSettings.kid_id == kid_id,
        )
        .first()
    )


def get_consent(
    db: Session,
    *,
    parent_id: int,
    kid_id: int,
) -> ConsentSnapshot:
    """Return the current consent + settings state for a (parent, kid) pair.

    Raises 404 if the kid is not linked to this parent.
    Returns a fail-closed default snapshot if no row exists yet.
    """
    _verify_parent_owns_kid(db, parent_id, kid_id)
    return _to_snapshot(
        _load_consent(db, parent_id, kid_id),
        _load_settings(db, parent_id, kid_id),
        parent_id,
        kid_id,
    )


def upsert_consent(
    db: Session,
    *,
    parent_id: int,
    kid_id: int,
    photo_ok: bool | None = None,
    voice_ok: bool | None = None,
    ai_ok: bool | None = None,
    retention_days: int | None = None,
    dci_enabled: bool | None = None,
    muted: bool | None = None,
    kid_push_time: str | None = None,
    parent_push_time: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ConsentSnapshot:
    """Create or update consent + settings rows, returning the new snapshot.

    Every write is audit-logged via ``audit_service.log_action`` with
    ``action='dci_consent_update'`` and the field-level diff in ``details``.
    """
    _verify_parent_owns_kid(db, parent_id, kid_id)

    if retention_days is not None and retention_days not in ALLOWED_RETENTION_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"retention_days must be one of {list(ALLOWED_RETENTION_DAYS)}",
        )
    kid_push_time = _validate_time(kid_push_time, "kid_push_time")
    parent_push_time = _validate_time(parent_push_time, "parent_push_time")

    consent = _load_consent(db, parent_id, kid_id)
    settings_row = _load_settings(db, parent_id, kid_id)

    consent_created = consent is None
    settings_created = settings_row is None

    before = {
        "photo_ok": bool(consent.photo_ok) if consent else False,
        "voice_ok": bool(consent.voice_ok) if consent else False,
        "ai_ok": bool(consent.ai_ok) if consent else False,
        "retention_days": int(consent.retention_days) if consent else 90,
        "dci_enabled": bool(settings_row.dci_enabled) if settings_row else True,
        "muted": bool(settings_row.muted) if settings_row else False,
        "kid_push_time": (settings_row.kid_push_time if settings_row else "15:15") or "15:15",
        "parent_push_time": (settings_row.parent_push_time if settings_row else "19:00") or "19:00",
    }

    consent_touched = any(
        v is not None for v in (photo_ok, voice_ok, ai_ok, retention_days)
    )
    settings_touched = any(
        v is not None for v in (dci_enabled, muted, kid_push_time, parent_push_time)
    )

    if consent is None and consent_touched:
        consent = CheckinConsent(
            parent_id=parent_id,
            kid_id=kid_id,
            photo_ok=False,
            voice_ok=False,
            ai_ok=False,
            retention_days=90,
        )
        db.add(consent)
    if settings_row is None and settings_touched:
        settings_row = CheckinSettings(
            parent_id=parent_id,
            kid_id=kid_id,
            dci_enabled=True,
            muted=False,
            kid_push_time="15:15",
            parent_push_time="19:00",
        )
        db.add(settings_row)

    if consent is not None:
        if photo_ok is not None:
            consent.photo_ok = bool(photo_ok)
        if voice_ok is not None:
            consent.voice_ok = bool(voice_ok)
        if ai_ok is not None:
            consent.ai_ok = bool(ai_ok)
        if retention_days is not None:
            consent.retention_days = int(retention_days)

    if settings_row is not None:
        if dci_enabled is not None:
            settings_row.dci_enabled = bool(dci_enabled)
        if muted is not None:
            settings_row.muted = bool(muted)
        if kid_push_time is not None:
            settings_row.kid_push_time = kid_push_time
        if parent_push_time is not None:
            settings_row.parent_push_time = parent_push_time

    # Flush so attribute reads below see post-mutation values, but defer
    # the outer commit until AFTER log_action stages the audit row in its
    # SAVEPOINT. This keeps consent change + audit entry atomic — Bill 194
    # § 11 requires every consent change to be auditable; a mid-flow crash
    # must not leave a consent change persisted without its audit row.
    db.flush()

    after = {
        "photo_ok": bool(consent.photo_ok) if consent else False,
        "voice_ok": bool(consent.voice_ok) if consent else False,
        "ai_ok": bool(consent.ai_ok) if consent else False,
        "retention_days": int(consent.retention_days) if consent else 90,
        "dci_enabled": bool(settings_row.dci_enabled) if settings_row else True,
        "muted": bool(settings_row.muted) if settings_row else False,
        "kid_push_time": (settings_row.kid_push_time if settings_row else "15:15") or "15:15",
        "parent_push_time": (settings_row.parent_push_time if settings_row else "19:00") or "19:00",
    }

    log_action(
        db,
        user_id=parent_id,
        action="dci_consent_update",
        resource_type="checkin_consent",
        resource_id=kid_id,
        details={
            "consent_created": consent_created and consent is not None,
            "settings_created": settings_created and settings_row is not None,
            "before": before,
            "after": after,
            "kid_id": kid_id,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    # Single commit persists consent + settings + audit row atomically.
    db.commit()
    if consent is not None:
        db.refresh(consent)
    if settings_row is not None:
        db.refresh(settings_row)

    return _to_snapshot(consent, settings_row, parent_id, kid_id)


def assert_dci_consent(
    db: Session,
    *,
    kid_id: int,
    parent_id: int,
    requires_photo: bool = False,
    requires_voice: bool = False,
) -> ConsentSnapshot:
    """Gate helper for ``POST /api/dci/checkin`` (M0-4).

    Raises ``HTTPException(403, {'error': 'consent_required'})`` if the
    parent has not granted active consent for AI processing on this kid,
    OR if the specific input modality required by the request has not
    been consented to, OR if DCI has been disabled in settings.

    Returns the snapshot on success (so M0-4 can also gate retention etc.).

    Defense-in-depth: this helper also verifies the (parent, kid) link
    via the ``parent_students`` join — a forged ``kid_id`` raises 404
    rather than falling through to the deny path. Callers should still
    perform their own ownership checks at the route level; this is the
    second line of defense.

    Performance (#4191): ownership + consent + settings are fetched in a
    single round-trip via an inner join to ``parent_students`` (ownership
    gate) plus outer joins to ``checkin_consent`` and ``checkin_settings``
    (both may legitimately be NULL on first checkin attempt). The previous
    implementation issued 4 separate queries per call.

    Caller contract::

        from app.services.dci_consent_service import assert_dci_consent

        snapshot = assert_dci_consent(
            db,
            kid_id=kid_id,
            parent_id=current_user.id,
            requires_photo=bool(payload.photo_uris),
            requires_voice=bool(payload.voice_uri),
        )
    """
    # Single round-trip: inner join on ownership, outer joins on consent +
    # settings (both may be NULL pre-first-checkin). A None result row means
    # the (parent, kid) link doesn't exist => 404. A row with consent=None
    # means owned-but-no-consent-yet => 403.
    row = (
        db.query(CheckinConsent, CheckinSettings)
        .select_from(parent_students)
        .outerjoin(
            CheckinConsent,
            (CheckinConsent.parent_id == parent_students.c.parent_id)
            & (CheckinConsent.kid_id == parent_students.c.student_id),
        )
        .outerjoin(
            CheckinSettings,
            (CheckinSettings.parent_id == parent_students.c.parent_id)
            & (CheckinSettings.kid_id == parent_students.c.student_id),
        )
        .filter(
            parent_students.c.parent_id == parent_id,
            parent_students.c.student_id == kid_id,
        )
        .first()
    )

    if row is None:
        # Parent does not own this kid — 404 (avoid leaking existence).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kid not found"
        )

    consent, settings_row = row

    def _deny() -> "HTTPException":
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "consent_required"},
        )

    if consent is None:
        raise _deny()
    if settings_row is not None and not settings_row.dci_enabled:
        raise _deny()
    if not consent.ai_ok:
        raise _deny()
    if requires_photo and not consent.photo_ok:
        raise _deny()
    if requires_voice and not consent.voice_ok:
        raise _deny()
    return _to_snapshot(consent, settings_row, parent_id, kid_id)
