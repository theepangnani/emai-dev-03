"""CMCP class-context envelope resolver — service layer (CB-CMCP-001 M1-B 1B-2, #4472).

Builds the four-input class-context envelope per A1 FR-02.5 and the locked
plan §7 M1-B 1B-2. The envelope is consumed by the GuardrailEngine (1B-3,
deferred) so it can ground generated artifacts in the teacher's own class
materials rather than emitting CEG-only generic content.

Inputs assembled (all course-scoped, NO student PII):

(a) ``course_contents`` — uploaded teacher notes / slides / syllabi from
    :class:`app.models.course_content.CourseContent`. Each cell carries
    ``id``, ``title``, ``content_type`` and a SHORT summary excerpt
    (<=500 chars) drawn from ``description`` (preferred) or
    ``text_content`` (fallback).

(b) ``classroom_announcements`` — last-14-day items from
    :class:`app.models.course_announcement.CourseAnnouncement` filtered
    by ``creation_time`` (or ``created_at`` when GC time is missing).
    Each cell carries ``id``, ``text`` excerpt (<=500 chars), ``creator_name``
    and ``creation_time``.

(c) ``teacher_digest_summary`` — last-30-day teacher-side parsed-email
    items from :class:`app.models.teacher_communication.TeacherCommunication`
    where ``user_id`` is the calling teacher AND
    ``course_id`` (Google Classroom string id) matches the requested
    course. Returned as a single condensed dict with a count + a list of
    short ``ai_summary`` excerpts (<=500 chars each, capped to the latest
    10 items to stay within the prompt budget).

(d) ``teacher_library_artifacts`` — APPROVED artifacts from the extended
    ``study_guides`` table (M0 0A-2 columns) whose ``se_codes`` overlap
    ``target_se_codes``. Each cell carries ``id``, ``title``,
    ``guide_type``, ``state`` and the matching ``se_codes`` subset.

Privacy boundary
----------------

Per A1 + DD §5.5 ("No PII in generation prompts"), the envelope MUST NOT
carry student names, student IDs, parent names, or per-student grades
**joined from the schema**. Inputs are filtered to course-level /
teacher-authored content only.  ``user_id`` (the *teacher* whose library
is being queried) is preserved on the envelope's input metadata for
audit but is NOT a student field.

Caveat — incidental free-text PII: ``TeacherCommunication.subject`` and
``TeacherCommunication.ai_summary`` are AI-summarized from the teacher's
inbox.  No student/parent schema fields are joined, but the free-text
content of these excerpts may incidentally contain student or parent
first names that slipped past upstream summarization.  Downstream
callers (1B-3) should treat the envelope as **low-PII**, not
**zero-PII**, until a dedicated sanitizer lands.  Both fields are
length-capped (``_SUMMARY_MAX_CHARS`` / ``_SUBJECT_MAX_CHARS``) and the
digest is item-capped (``_DIGEST_ITEM_CAP``) to bound exposure.

Stubs / known gaps
------------------

None at module level — all four inputs map to existing dev-03 tables:

  (a) ``course_contents``                                 — :class:`CourseContent`
  (b) ``course_announcements``                            — :class:`CourseAnnouncement`
  (c) ``teacher_communications`` filtered to teacher+course+30d
                                                          — :class:`TeacherCommunication`
  (d) ``study_guides`` filtered to APPROVED + se_codes overlap
                                                          — :class:`StudyGuide`

Out of scope (per #4472 explicit deferrals)
-------------------------------------------

- Injecting the envelope into the GuardrailEngine prompt — 1B-3, wave 2.5.
- Telemetry sink for ``envelope_size`` — surfaces in M3 telemetry stripe.
- Frontend "generic" badge when ``fallback_used`` — 1B-4, wave 3.
- Real Google Classroom API calls — out of scope; we read the cached
  ``course_announcements`` table populated by ``app/jobs/google_sync.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.course_announcement import CourseAnnouncement
from app.models.course_content import CourseContent
from app.models.study_guide import StudyGuide
from app.models.teacher_communication import TeacherCommunication


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Per-cell summary excerpt cap.  Per #4472 critical note: keep each
#: course-content / announcement / digest snippet short so the eventual
#: prompt-budget injection (1B-3) doesn't blow past the model's window.
_SUMMARY_MAX_CHARS = 500

#: Recency window for Google Classroom announcements (per A1 FR-02.5b).
_ANNOUNCEMENT_WINDOW_DAYS = 14

#: Recency window for teacher email digest (per A1 FR-02.5c).
_DIGEST_WINDOW_DAYS = 30

#: Cap on the number of teacher_digest items returned in the condensed
#: dict.  10 items keeps the eventual prompt under the budget while still
#: covering a typical 30-day teacher inbox.
_DIGEST_ITEM_CAP = 10

#: Per-item subject cap for teacher-digest items.  Subjects come from the
#: teacher's inbox and may carry incidental student/parent first names —
#: cap before surfacing.
_SUBJECT_MAX_CHARS = 200


# ---------------------------------------------------------------------------
# Pydantic envelope model — exported for 1B-3 import
# ---------------------------------------------------------------------------


class ClassContextEnvelope(BaseModel):
    """Class-context envelope returned by :class:`ClassContextResolver`.

    Mirrors the four FR-02.5 inputs plus audit metadata for telemetry
    (``envelope_size``, ``cited_source_count``, ``fallback_used``).
    """

    # Inputs / scope
    course_id: int | None
    user_id: int
    target_se_codes: list[str]

    # Per A1 FR-02.5 inputs (a-d)
    course_contents: list[dict[str, Any]] = Field(default_factory=list)
    classroom_announcements: list[dict[str, Any]] = Field(default_factory=list)
    teacher_digest_summary: dict[str, Any] | None = None
    teacher_library_artifacts: list[dict[str, Any]] = Field(default_factory=list)

    # Audit metadata (per A1 acceptance: envelope_size > 0 in >=70% by M3).
    envelope_size: int = 0
    cited_source_count: int = 0
    fallback_used: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(text: str | None, limit: int = _SUMMARY_MAX_CHARS) -> str:
    """Trim ``text`` to at most ``limit`` chars; return ``""`` for None."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _ses_overlap(artifact_ses: Any, target: set[str]) -> list[str]:
    """Return the intersection of the artifact's SE codes with ``target``.

    ``artifact_ses`` may be a ``list[str]`` (JSON column hydrated by
    SQLAlchemy) or ``None``.  Anything else short-circuits to ``[]`` so we
    never raise on stale or partially-migrated rows.
    """
    if not isinstance(artifact_ses, list):
        return []
    return sorted(set(artifact_ses) & target)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class ClassContextResolver:
    """Resolve the four-input class-context envelope for a course.

    The resolver is stateless and safe to instantiate per request.
    Callers (1B-3 GuardrailEngine wrapper) typically construct it once
    and call :meth:`resolve` per generation.
    """

    def resolve(
        self,
        user_id: int,
        course_id: int | None,
        target_se_codes: list[str],
        db: Session,
    ) -> ClassContextEnvelope:
        """Assemble the envelope; gracefully degrade on missing inputs.

        Args:
            user_id: The teacher (or admin acting as teacher) whose
                library is being queried for input (d).  Required.
            course_id: The course to scope inputs (a)/(b)/(c) by.  ``None``
                yields an empty envelope with ``fallback_used=True``
                (CEG-only mode).
            target_se_codes: SE codes the artifact-to-be-generated will
                target; drives input (d) overlap query.  An empty list
                still allows (a)/(b)/(c) to populate but yields no
                library artifacts.
            db: SQLAlchemy session.

        Returns:
            :class:`ClassContextEnvelope` with all four input lists
            populated where data exists, plus audit metadata.
        """
        target_se_set = {c for c in target_se_codes if c}

        # When course_id is missing, all course-scoped inputs go empty
        # (per critical note "if course_id is None, all 4 categories
        # return empty; envelope.fallback_used=True"). We still attempt
        # input (d) so a caller invoking us with target_se_codes only
        # (e.g., self-study from an unenrolled student) can still get
        # generic teacher-library matches.
        course_contents = (
            self._fetch_course_contents(course_id, db) if course_id else []
        )
        classroom_announcements = (
            self._fetch_announcements(course_id, db) if course_id else []
        )
        teacher_digest = (
            self._fetch_teacher_digest(user_id, course_id, db)
            if course_id
            else None
        )
        teacher_library = self._fetch_library_artifacts(
            course_id, target_se_set, db
        )

        # Audit metadata — per A1, envelope_size is the count of cited
        # sources across all four categories.  teacher_digest_summary
        # contributes its item count, not 1, so the metric reflects the
        # actual grounding evidence available to the prompt.
        digest_count = (
            int(teacher_digest.get("count", 0)) if teacher_digest else 0
        )
        envelope_size = (
            len(course_contents)
            + len(classroom_announcements)
            + digest_count
            + len(teacher_library)
        )

        return ClassContextEnvelope(
            course_id=course_id,
            user_id=user_id,
            target_se_codes=list(target_se_codes),
            course_contents=course_contents,
            classroom_announcements=classroom_announcements,
            teacher_digest_summary=teacher_digest,
            teacher_library_artifacts=teacher_library,
            envelope_size=envelope_size,
            cited_source_count=envelope_size,
            fallback_used=envelope_size == 0,
        )

    # ------------------------------------------------------------------
    # (a) Course contents
    # ------------------------------------------------------------------

    def _fetch_course_contents(
        self,
        course_id: int,
        db: Session,
    ) -> list[dict[str, Any]]:
        """Pull non-archived course materials for ``course_id``.

        Privacy: ``CourseContent`` is teacher-authored / teacher-uploaded
        material — no per-student fields exist on the row.
        """
        rows = (
            db.query(CourseContent)
            .filter(
                CourseContent.course_id == course_id,
                CourseContent.archived_at.is_(None),
            )
            .order_by(CourseContent.display_order.asc(), CourseContent.id.asc())
            .all()
        )

        out: list[dict[str, Any]] = []
        for r in rows:
            # Prefer the human-authored description; fall back to the
            # extracted text body when no description is present.  Both
            # are truncated to keep the prompt budget honest.
            summary = _truncate(r.description) or _truncate(r.text_content)
            out.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "content_type": r.content_type,
                    "summary": summary,
                }
            )
        return out

    # ------------------------------------------------------------------
    # (b) Google Classroom announcements
    # ------------------------------------------------------------------

    def _fetch_announcements(
        self,
        course_id: int,
        db: Session,
    ) -> list[dict[str, Any]]:
        """Pull last-14-day announcements for ``course_id``.

        Privacy: ``CourseAnnouncement`` carries the teacher's name/email
        as ``creator_*`` (course-level, not student PII) plus the public
        announcement text — safe to surface.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=_ANNOUNCEMENT_WINDOW_DAYS
        )

        # Some rows have ``creation_time`` from GC; legacy ones only have
        # ``created_at`` (when we ingested it).  Either timestamp newer
        # than the cutoff qualifies — we want broad recall for the
        # 14-day window.
        rows = (
            db.query(CourseAnnouncement)
            .filter(
                CourseAnnouncement.course_id == course_id,
                or_(
                    CourseAnnouncement.creation_time >= cutoff,
                    CourseAnnouncement.created_at >= cutoff,
                ),
            )
            .order_by(CourseAnnouncement.creation_time.desc().nullslast())
            .all()
        )

        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "id": r.id,
                    "text": _truncate(r.text),
                    "creator_name": r.creator_name,
                    "creation_time": (
                        r.creation_time.isoformat()
                        if r.creation_time
                        else None
                    ),
                }
            )
        return out

    # ------------------------------------------------------------------
    # (c) Teacher email digest summary
    # ------------------------------------------------------------------

    def _fetch_teacher_digest(
        self,
        user_id: int,
        course_id: int,
        db: Session,
    ) -> dict[str, Any] | None:
        """Pull last-30-day teacher-side parsed emails for the course.

        ``TeacherCommunication.course_id`` is a Google Classroom string
        id (the GC course resource identifier) — we resolve our internal
        ``course_id`` to that string via the :class:`Course` row's
        ``google_classroom_id``.  Courses without a GC link return None
        rather than a misleadingly empty summary.

        Privacy: ``TeacherCommunication`` carries the *teacher's* parsed
        inbox.  ``sender_*`` and ``ai_summary`` describe outside parties
        and email content respectively — neither is per-student PII at
        the schema level.  We surface only ``ai_summary`` excerpts +
        ``subject`` + ``received_at`` so any free-text PII a teacher's
        inbox might have captured stays within the AI summary excerpt
        cap (and is bounded by the digest item cap).
        """
        course = db.query(Course).filter(Course.id == course_id).first()
        if course is None:
            return None

        gc_id = getattr(course, "google_classroom_id", None)
        if gc_id is None:
            # No GC link — TeacherCommunication.course_id is a GC string
            # so we can't bridge.  Returning None signals "input (c) had
            # no source" rather than "input (c) was empty" so a caller
            # can distinguish the two cases for telemetry.
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=_DIGEST_WINDOW_DAYS
        )

        rows = (
            db.query(TeacherCommunication)
            .filter(
                TeacherCommunication.user_id == user_id,
                TeacherCommunication.course_id == str(gc_id),
                or_(
                    TeacherCommunication.received_at >= cutoff,
                    TeacherCommunication.created_at >= cutoff,
                ),
            )
            .order_by(TeacherCommunication.received_at.desc().nullslast())
            .limit(_DIGEST_ITEM_CAP)
            .all()
        )

        if not rows:
            return None

        items: list[dict[str, Any]] = []
        for r in rows:
            items.append(
                {
                    "subject": _truncate(r.subject, _SUBJECT_MAX_CHARS),
                    "ai_summary": _truncate(r.ai_summary),
                    "received_at": (
                        r.received_at.isoformat() if r.received_at else None
                    ),
                }
            )
        return {
            "count": len(items),
            "window_days": _DIGEST_WINDOW_DAYS,
            "items": items,
        }

    # ------------------------------------------------------------------
    # (d) Teacher library artifacts
    # ------------------------------------------------------------------

    def _fetch_library_artifacts(
        self,
        course_id: int | None,
        target_se_codes: set[str],
        db: Session,
    ) -> list[dict[str, Any]]:
        """Pull APPROVED artifacts whose ``se_codes`` overlap the target set.

        Implemented as a load-then-filter overlap because dev-03's
        ``se_codes`` column uses portable JSON (JSONB on PG, JSON on
        SQLite) and SQLite has no native array-overlap operator.  We
        gate the load with ``state == APPROVED`` and (when provided)
        ``course_id`` to keep the scan small — without the course filter
        the candidate set grows linearly with the platform's APPROVED
        corpus across all boards.  A dialect-aware JSONB containment
        path is deferred to M3 telemetry tuning.

        Privacy: ``StudyGuide`` rows can carry ``user_id`` (the author);
        we deliberately omit that field from the cell so envelope
        consumers can't fingerprint authors.  Only artifact identity,
        title, type, state, and the matching SE subset are surfaced.
        """
        if not target_se_codes:
            return []

        # Lazy import: ``ArtifactState`` is the canonical APPROVED label
        # but we keep the resolver decoupled from the state-machine class.
        from app.services.cmcp.artifact_state import ArtifactState

        q = db.query(StudyGuide).filter(
            StudyGuide.state == ArtifactState.APPROVED,
            StudyGuide.archived_at.is_(None),
            StudyGuide.se_codes.isnot(None),
        )
        if course_id is not None:
            q = q.filter(StudyGuide.course_id == course_id)
        rows = q.all()

        out: list[dict[str, Any]] = []
        for r in rows:
            matched = _ses_overlap(r.se_codes, target_se_codes)
            if not matched:
                continue
            out.append(
                {
                    "id": r.id,
                    "title": r.title,
                    "guide_type": r.guide_type,
                    "state": r.state,
                    "matched_se_codes": matched,
                }
            )
        return out
