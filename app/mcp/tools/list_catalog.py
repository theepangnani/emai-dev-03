"""MCP tool ``list_catalog`` — paginated, role-scoped, filtered list of artifacts.

CB-CMCP-001 M2-B 2B-3 (#4554).

Returns a cursor-paginated list of CB-CMCP / study-guide artifacts the
caller may access. The catalog reuses the existing ``study_guides`` table
(D2=B locked decision); per the M3-precondition "no persistence yet"
caveat, this tool also serves *non-CMCP* study-guide rows. Curriculum-
specific filters (``subject_code`` / ``grade``) only narrow the result
when the underlying rows actually carry those tags — otherwise they
short-circuit to "no rows".

Cursor design
-------------
Cursors are opaque base64-encoded JSON of ``{"created_at": ISO, "id": int}``.
The list orders by ``id DESC`` (which mirrors ``created_at DESC`` because
``id`` is monotonically increasing on insert) and the cursor's predicate
filters by ``id < cursor_id``.

We deliberately do NOT use ``created_at`` in the SQL predicate because
SQLite + SQLAlchemy's ``DateTime`` adapter renders bound parameters with
microseconds (``2026-04-29 15:42:27.000000``) while server-stored values
have no microseconds (``2026-04-29 15:42:27``). SQLite text-comparison
then treats the stored value as ``<`` the bound value when they should
be equal, breaking pagination. ``id`` is integer-typed and not subject
to that quirk. ``created_at`` IS retained in the cursor payload (for
future cross-DB filters once the adapter is fixed and so the cursor
payload remains forward-compatible) and is exposed in the response so
clients can render the boundary if useful.

We over-fetch ``limit + 1`` to detect "more rows exist?" without a
separate ``COUNT`` query.

Out of scope (per #4554)
------------------------
- Free-text search — use the curriculum search surface from M0-B.
- Sort options other than ``created_at DESC`` — would change cursor shape.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import datetime
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.mcp.tools._errors import MCPToolValidationError
from app.mcp.tools._visibility import resolve_caller_board_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults / bounds
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
DEFAULT_STATE = "APPROVED"

# Maximum number of over-fetch SQL passes per ``list_catalog`` call before
# we surrender and return a partial page with a non-null cursor (#4568).
# Each pass fetches ``limit + 1`` rows from the DB; once we hit this cap,
# we stop trying to fill the page and let the caller advance the cursor
# on the next request. Without this guard a degenerate filter (e.g. a
# subject_code that no row matches) would walk the entire table.
MAX_OVERFETCH_PASSES = 5


# ---------------------------------------------------------------------------
# Cursor helpers
# ---------------------------------------------------------------------------


def _encode_cursor(created_at: datetime, row_id: int) -> str:
    """Encode the ``(created_at, id)`` pair as a URL-safe base64 string.

    Using ISO 8601 (UTC) for ``created_at`` keeps the cursor portable
    across SQLite (no native ``timestamptz``) and PG. ``id`` is the tie
    breaker for rows that share a timestamp.
    """
    payload = {
        "created_at": created_at.isoformat() if created_at else None,
        "id": int(row_id),
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime | None, int]:
    """Decode an opaque cursor back into ``(created_at, id)``.

    Raises :class:`MCPToolValidationError` on malformed input — the
    dispatcher translates that to ``422``. Opaque cursors should be
    treated like a token: garbage in → caller error, not a 500.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        created_iso = payload.get("created_at")
        row_id = int(payload["id"])
    except (ValueError, KeyError, binascii.Error, json.JSONDecodeError) as exc:
        raise MCPToolValidationError(
            f"Invalid cursor: {exc}"
        ) from exc

    if created_iso is None:
        return None, row_id
    try:
        created_at = datetime.fromisoformat(created_iso)
    except ValueError as exc:
        raise MCPToolValidationError(
            f"Invalid cursor created_at: {exc}"
        ) from exc
    return created_at, row_id


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _validate_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize / validate the MCP tool ``arguments`` payload.

    Pydantic isn't used here because the registry's ``input_schema`` is
    the public contract; we keep validation inline + return a typed dict
    the handler can rely on. 422 on every user-input mistake (matches
    FastAPI's request-validation conventions).
    """
    out: dict[str, Any] = {}

    out["subject_code"] = _opt_str(arguments, "subject_code")
    out["grade"] = _opt_int(arguments, "grade")
    out["content_type"] = _opt_str(arguments, "content_type")
    out["state"] = _opt_str(arguments, "state") or DEFAULT_STATE
    out["cursor"] = _opt_str(arguments, "cursor")

    limit_raw = arguments.get("limit", DEFAULT_LIMIT)
    if limit_raw is None:
        limit = DEFAULT_LIMIT
    else:
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError) as exc:
            raise MCPToolValidationError(
                f"Invalid limit: {exc}"
            ) from exc
    if limit < 1 or limit > MAX_LIMIT:
        raise MCPToolValidationError(
            f"limit must be between 1 and {MAX_LIMIT} (got {limit})"
        )
    out["limit"] = limit
    return out


def _opt_str(args: Mapping[str, Any], key: str) -> str | None:
    """Return ``args[key]`` if a non-empty string, else ``None``."""
    val = args.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise MCPToolValidationError(f"{key!r} must be a string")
    val = val.strip()
    return val or None


def _opt_int(args: Mapping[str, Any], key: str) -> int | None:
    """Return ``args[key]`` coerced to ``int``, else ``None``."""
    val = args.get(key)
    if val is None:
        return None
    if isinstance(val, bool):
        # ``bool`` is an ``int`` subclass — guard explicitly so a
        # ``True``/``False`` doesn't slip through as ``1``/``0``.
        raise MCPToolValidationError(f"{key!r} must be an integer")
    try:
        return int(val)
    except (TypeError, ValueError) as exc:
        raise MCPToolValidationError(
            f"{key!r} must be an integer ({exc})"
        ) from exc


# ---------------------------------------------------------------------------
# Role scoping
# ---------------------------------------------------------------------------


def _apply_role_scope(  # type: ignore[no-untyped-def]
    query, current_user, db: Session, *, state_filter: str | None = None
):
    """Narrow ``query`` to artifacts the caller's role may see.

    Mirrors the access-matrix in 2B-2's ``get_artifact``:

    - ``ADMIN`` → every artifact (no narrowing).
    - ``CURRICULUM_ADMIN`` → every non-SELF_STUDY artifact + own
      self-initiated SELF_STUDY artifacts (3B-3 / #4585 narrowed the
      previously-open scope so curriculum work doesn't leak into
      private learner workspaces).
    - ``BOARD_ADMIN`` → artifacts whose ``board_id`` matches the
      admin's board scope AND ``board_id IS NOT NULL`` (legacy rows
      with a NULL ``board_id`` are denied — same conservative default
      as 2B-2's ``_user_can_view``). When the caller has no resolvable
      ``board_id`` (the M2 default until M3-E lands), the result is an
      empty selection. SELF_STUDY rows are denied even on board match.
    - ``TEACHER`` → artifacts authored by the teacher OR pinned to a
      course the teacher owns. Course ownership is detected via
      ``courses.teacher_id → teachers.user_id == current_user.id`` so
      this stripe doesn't depend on the assignment-context graph.
      SELF_STUDY rows are denied via the course branch (private to
      family, not class-distributable).
    - ``PARENT`` → artifacts authored by the parent OR by any of their
      linked students. Same scope covers SELF_STUDY family pair.
    - ``STUDENT`` → artifacts authored by the student, plus SELF_STUDY
      rows owned by their linked PARENTS (3B-3 family override).
    - Anything else (None / unknown) → empty result. The route layer
      403s before we get here for unknown roles, but keep the
      defence-in-depth.

    SELF_STUDY override (3B-3 / #4585)
    ----------------------------------
    Per D3=C, SELF_STUDY-state rows are private to a family pair. The
    extra filters below exclude any SELF_STUDY row whose ``user_id``
    isn't the caller or one of their linked-children/linked-parents
    user ids. ``ADMIN`` keeps the catch-all bypass (mirrors
    ``_user_can_view``); ``CURRICULUM_ADMIN`` / ``BOARD_ADMIN`` /
    ``TEACHER`` lose access to SELF_STUDY rows even when the
    standard matrix would otherwise show them.

    The optional ``state_filter`` argument lets the caller skip the
    SELF_STUDY family-allowlist DB lookup when the upstream state
    filter already excludes SELF_STUDY rows. The default
    ``list_catalog`` state is ``APPROVED`` — the dominant traffic
    shape — and a non-SELF_STUDY filter means the family allowlist
    is dead weight, so we no-op the lookup. ``state_filter=None`` is
    treated as "could include SELF_STUDY" (matches the upstream
    behavior of an unfiltered query).
    """
    # Lazy imports inside services that catch broadly — see CLAUDE.md
    # "lazy-import ORM models" rule for why this isn't at module top.
    from app.models.course import Course
    from app.models.student import Student, parent_students
    from app.models.study_guide import StudyGuide
    from app.models.teacher import Teacher
    from app.models.user import UserRole  # noqa: F401
    from app.services.cmcp.artifact_state import ArtifactState

    role = current_user.role if current_user is not None else None
    if role is None:
        return query.filter(False)

    role_name = role.name if hasattr(role, "name") else str(role).upper()

    # ADMIN — full bypass (matches ``_user_can_view``). No SELF_STUDY
    # narrowing applied either, so ops/debug retains visibility.
    if role_name == "ADMIN":
        return query

    # If the upstream state filter excludes SELF_STUDY entirely, we can
    # short-circuit the family-allowlist lookup — no SELF_STUDY rows
    # can match the query, so no SELF_STUDY narrowing or widening
    # predicates need to fire. ``state_filter=None`` means the caller
    # didn't pre-filter (could include SELF_STUDY) → keep the override.
    self_study_could_match = (
        state_filter is None or state_filter == ArtifactState.SELF_STUDY
    )

    # ── Family allowlist for SELF_STUDY rows (STUDENT only) ───────────────
    # The 3B-3 SELF_STUDY rule extends STUDENT visibility to artifacts
    # owned by their linked PARENTS. STUDENT is the only role whose
    # standard scope doesn't already cover the family pair — PARENT's
    # standard scope (own + linked-children) already IS the family
    # allowlist. CURRICULUM_ADMIN / BOARD_ADMIN / TEACHER never get a
    # family-pair grant on a learner's SELF_STUDY artifact; their
    # SELF_STUDY override predicate uses ``current_user.id`` directly
    # (caller-as-creator only).
    student_self_study_family_ids: list[int] = [current_user.id]
    if self_study_could_match and role_name == "STUDENT":
        student_record = (
            db.query(Student)
            .filter(Student.user_id == current_user.id)
            .first()
        )
        if student_record is not None:
            parent_user_ids_for_family = [
                row[0]
                for row in db.query(parent_students.c.parent_id)
                .filter(parent_students.c.student_id == student_record.id)
                .all()
            ]
            student_self_study_family_ids.extend(parent_user_ids_for_family)

    if role_name == "CURRICULUM_ADMIN":
        # CURRICULUM_ADMIN sees all non-SELF_STUDY rows; SELF_STUDY rows
        # are private to the family pair, with the curriculum-admin
        # capped to their own self-initiated artifacts. This narrows
        # the previously-open CURRICULUM_ADMIN scope so curriculum work
        # doesn't leak into private learner workspaces.
        if not self_study_could_match:
            return query
        return query.filter(
            (StudyGuide.state != ArtifactState.SELF_STUDY)
            | (StudyGuide.user_id == current_user.id)
        )

    if role_name == "BOARD_ADMIN":
        caller_board = resolve_caller_board_id(current_user)
        if caller_board is None:
            # No resolvable board → fail closed. Mirrors 2B-2 row-level
            # behaviour: BOARD_ADMINs never see legacy unscoped rows.
            return query.filter(False)
        scoped = query.filter(
            StudyGuide.board_id.is_not(None),
            StudyGuide.board_id == str(caller_board),
        )
        if not self_study_could_match:
            return scoped
        # SELF_STUDY rows are denied to BOARD_ADMIN even when the
        # board_id matches — the override only opens up the caller's
        # own self-initiated artifacts.
        return scoped.filter(
            (StudyGuide.state != ArtifactState.SELF_STUDY)
            | (StudyGuide.user_id == current_user.id)
        )

    if role_name == "TEACHER":
        # Authored by the teacher OR pinned to a course the teacher
        # owns. ``Course.teacher_id`` is the ``teachers.id`` PK, not
        # the ``users.id`` PK — bridge through the Teacher row.
        teacher_pk_subq = (
            db.query(Teacher.id)
            .filter(Teacher.user_id == current_user.id)
            .subquery()
        )
        owned_course_ids = (
            db.query(Course.id)
            .filter(Course.teacher_id.in_(teacher_pk_subq))
            .subquery()
        )
        if not self_study_could_match:
            # No SELF_STUDY can match — emit the standard TEACHER scope
            # without the SELF_STUDY suppression on the course branch.
            return query.filter(
                (StudyGuide.user_id == current_user.id)
                | (StudyGuide.course_id.in_(owned_course_ids))
            )
        # TEACHER cannot see a student's SELF_STUDY artifact via the
        # course-pinned branch — SELF_STUDY rows are private to the
        # family pair. The teacher only sees their own self-initiated
        # SELF_STUDY artifacts (caller-as-creator branch).
        #
        # D3=C invariant: ``TEACHER + course_id`` resolves to
        # ``PENDING_REVIEW`` (never ``SELF_STUDY``) in
        # ``persist_cmcp_artifact._resolve_state``, so a SELF_STUDY
        # row with a course_id should not exist by construction. The
        # ``state != SELF_STUDY`` clause is therefore defence-in-depth
        # against a row that the persistence layer should never produce.
        return query.filter(
            (StudyGuide.user_id == current_user.id)
            | (
                (StudyGuide.course_id.in_(owned_course_ids))
                & (StudyGuide.state != ArtifactState.SELF_STUDY)
            )
        )

    if role_name == "PARENT":
        kid_user_ids = (
            db.query(Student.user_id)
            .join(
                parent_students,
                parent_students.c.student_id == Student.id,
            )
            .filter(parent_students.c.parent_id == current_user.id)
            .subquery()
        )
        # Parent's standard scope (own + linked-children) already
        # matches the SELF_STUDY family allowlist for a PARENT (a
        # parent can only have linked-children pairs, not linked-
        # parents), so no extra narrowing is needed for SELF_STUDY.
        return query.filter(
            (StudyGuide.user_id == current_user.id)
            | (StudyGuide.user_id.in_(kid_user_ids))
        )

    if role_name == "STUDENT":
        if not self_study_could_match:
            # No SELF_STUDY rows in scope — emit the standard "own
            # user_id only" filter without the SELF_STUDY widening.
            return query.filter(StudyGuide.user_id == current_user.id)
        # STUDENT's standard scope is "own user_id only" — but for
        # SELF_STUDY the family override extends visibility to the
        # student's linked PARENTS (parent's self-study is visible to
        # their kid). Apply the SELF_STUDY family allowlist as an
        # additional OR branch so a child can see a parent's
        # self-study without widening visibility on non-SELF_STUDY
        # rows.
        return query.filter(
            (StudyGuide.user_id == current_user.id)
            | (
                (StudyGuide.state == ArtifactState.SELF_STUDY)
                & (StudyGuide.user_id.in_(student_self_study_family_ids))
            )
        )

    # Defence in depth — unknown role shouldn't reach the dispatcher
    # because the registry's allowlist gates first, but if it does, fail
    # closed.
    return query.filter(False)


# ---------------------------------------------------------------------------
# Row → response dict
# ---------------------------------------------------------------------------


def _row_to_summary(row) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Project a ``StudyGuide`` row to the public summary dict.

    Deliberately small (no Markdown body) — clients fetch the full
    artifact via ``get_artifact`` (2B-2). This both keeps the list
    payload small for paginated UIs and avoids leaking large bodies for
    rows the caller might not actually open.
    """
    created_at = row.created_at.isoformat() if row.created_at else None
    return {
        "id": row.id,
        "title": row.title,
        "guide_type": row.guide_type,
        "content_type": row.guide_type,  # alias for MCP-spec consumers
        "state": row.state,
        "subject_code": _se_subject(row.se_codes),
        "grade": row.grade if hasattr(row, "grade") else None,
        "se_codes": list(row.se_codes) if row.se_codes else [],
        "course_id": row.course_id,
        "created_at": created_at,
    }


def _se_subject(se_codes: Any) -> str | None:
    """Best-effort subject prefix from the first SE code.

    Ontario SE codes are namespaced ``<SUBJECT>.<GRADE>.<STRAND>.<...>``
    (e.g. ``MATH.5.A.1``); the prefix before the first ``.`` is the
    canonical subject code. Returns ``None`` when the row carries no SE
    codes — non-CMCP study-guide rows fall here, which is fine because
    the response field is informational only (the list filter still
    works through the explicit ``subject_code`` filter on the query).
    """
    if not se_codes:
        return None
    try:
        first = se_codes[0]
    except (IndexError, TypeError):
        return None
    if not isinstance(first, str) or "." not in first:
        return None
    return first.split(".", 1)[0].upper()


def _se_grade(se_codes: Any) -> int | None:
    """Best-effort grade integer from the first SE code.

    Ontario SE codes are namespaced ``<SUBJECT>.<GRADE>.<STRAND>.<...>``;
    the second segment is the grade. Returns ``None`` when the row has
    no SE codes, the second segment isn't an integer, or the row's
    schema doesn't expose a parseable code. Used by the Python-side
    ``grade`` post-filter in :func:`list_catalog` because the
    ``study_guides`` table has no dedicated ``grade`` column today (it's
    embedded in the SE code; M3+ may add a real column).
    """
    if not se_codes:
        return None
    try:
        first = se_codes[0]
    except (IndexError, TypeError):
        return None
    if not isinstance(first, str):
        return None
    parts = first.split(".")
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def _post_filter_rows(
    rows: list,
    *,
    subject_code: str | None,
    grade: int | None,
    has_real_grade_column: bool,
) -> list:
    """Apply Python-side ``subject_code`` + ``grade`` filters to a row list.

    Extracted from :func:`list_catalog` so the over-fetch loop (#4568)
    can reuse the same predicate without duplicating the comprehension.
    Order doesn't matter; both predicates are applied to the same row
    collection.

    ``has_real_grade_column`` short-circuits the grade post-filter when
    the SQL pre-filter already handled it (forward-compat for an M3
    schema that adds ``study_guides.grade``).
    """
    if subject_code:
        prefix = subject_code.upper() + "."
        rows = [
            r
            for r in rows
            if r.se_codes
            and any(
                isinstance(c, str) and c.upper().startswith(prefix)
                for c in r.se_codes
            )
        ]
    if grade is not None and not has_real_grade_column:
        rows = [
            r
            for r in rows
            if r.se_codes and _se_grade(r.se_codes) == grade
        ]
    return rows


def list_catalog(
    arguments: Mapping[str, Any],
    current_user: Any,
    db: Session,
) -> dict[str, Any]:
    """MCP tool handler: paginated, role-scoped artifact list.

    Returns ``{"artifacts": [...], "next_cursor": str | None}``. Empty
    result yields ``{"artifacts": [], "next_cursor": None}`` (NOT 404 —
    a list endpoint on an empty selection is success, not failure).

    Pagination contract (#4568)
    ---------------------------
    Standard cursor semantics: ``next_cursor is None`` → caller has
    reached the end of iteration. The over-fetch loop below runs up to
    :data:`MAX_OVERFETCH_PASSES` SQL pages to fill the requested
    ``limit`` of *post-filtered* matches. Empty pages with a non-null
    cursor are only emitted when the cap is hit — degenerate filters
    can't infinitely walk the table, but a typical client paginating an
    APPROVED-only catalog will see "empty page → done" hold.
    """
    # Lazy imports — see ``_apply_role_scope`` for the rationale.
    from app.models.study_guide import StudyGuide

    args = _validate_arguments(arguments)
    has_real_grade_column = hasattr(StudyGuide, "grade")
    limit = args["limit"]

    def _build_window_query(cursor_id: int | None):
        """Build the SQL window query for one over-fetch pass.

        Recomputed inside the loop because each pass advances the
        cursor predicate. The non-cursor filters + role scope are
        identical across passes, but SQLAlchemy ``Query`` objects are
        immutable to ``filter()`` chaining only — re-deriving from
        ``db.query()`` keeps the loop body readable.
        """
        q = db.query(StudyGuide).filter(
            StudyGuide.archived_at.is_(None),
            StudyGuide.state == args["state"],
        )
        # Curriculum filters: only narrow when the row carries the
        # metadata. ``subject_code`` + ``grade`` are post-filtered in
        # Python because the ``se_codes`` JSON array shape isn't
        # portable across SQLite + PG without a dialect branch.
        if args["grade"] is not None and has_real_grade_column:
            # Forward-compat: if a future schema adds a real ``grade``
            # column we'll prefer the SQL filter over the post-filter.
            q = q.filter(StudyGuide.grade == args["grade"])
        if args["content_type"]:
            # ``guide_type`` is the existing column; map ``content_type``
            # (the MCP-spec name) to it.
            q = q.filter(StudyGuide.guide_type == args["content_type"])
        # Apply role scope BEFORE the cursor pagination so the cursor's
        # tuple comparison only sees rows the caller may legally see.
        # Passing the resolved state lets the role-scope skip the
        # SELF_STUDY family-allowlist DB lookup when the upstream
        # filter already excludes SELF_STUDY (the dominant default
        # ``state="APPROVED"`` traffic shape).
        q = _apply_role_scope(
            q, current_user, db, state_filter=args["state"]
        )
        # Cursor predicate. See the module docstring for why we don't
        # include ``created_at`` in the predicate.
        if cursor_id is not None:
            q = q.filter(StudyGuide.id < cursor_id)
        return q.order_by(StudyGuide.id.desc())

    # Seed the loop with the caller's incoming cursor (or None for the
    # first page).
    if args["cursor"]:
        _cursor_created_at, cursor_id = _decode_cursor(args["cursor"])
    else:
        cursor_id = None

    accumulated: list = []
    last_raw_row = None  # Last SQL row from the most recent over-fetch.
    db_exhausted = False
    passes = 0

    while passes < MAX_OVERFETCH_PASSES and len(accumulated) < limit:
        passes += 1
        # Over-fetch by 1 to detect "more rows exist?" without COUNT.
        raw_rows = _build_window_query(cursor_id).limit(limit + 1).all()
        if not raw_rows:
            db_exhausted = True
            break

        # ``has_more_in_window`` is true when this pass actually saw
        # ``limit + 1`` rows — i.e. the DB has at least one row past
        # the window we just consumed. False when the table tail is
        # within the window and there are no more rows after it.
        has_more_in_window = len(raw_rows) > limit
        # Trim the over-fetch sentinel before post-filtering — we only
        # used it to detect "more rows exist?", not to surface the
        # extra row in the response.
        page_rows = raw_rows[:limit] if has_more_in_window else raw_rows

        last_raw_row = page_rows[-1]
        accumulated.extend(
            _post_filter_rows(
                page_rows,
                subject_code=args["subject_code"],
                grade=args["grade"],
                has_real_grade_column=has_real_grade_column,
            )
        )

        if not has_more_in_window:
            db_exhausted = True
            break

        # Advance the cursor for the next pass past the last row we
        # just consumed (NOT the over-fetch sentinel — it's part of the
        # next window).
        cursor_id = last_raw_row.id

    # Trim to the requested page size. Any matches beyond ``limit`` are
    # discarded; the cursor is anchored so the caller picks them up on
    # the next request.
    if len(accumulated) > limit:
        artifacts_rows = accumulated[:limit]
        # Anchor to the last *emitted* match so the next call resumes
        # immediately after it. This re-scans rows the next pass already
        # saw if they're in the SQL window, but keeps the cursor
        # contract precise: id < anchor.id picks up after the last
        # emitted row.
        cursor_anchor = artifacts_rows[-1]
    else:
        artifacts_rows = accumulated
        if db_exhausted:
            # Standard "no more results" — empty cursor signals done.
            cursor_anchor = None
        else:
            # We hit MAX_OVERFETCH_PASSES without filling the page.
            # Anchor to the last *raw* row we consumed so the caller
            # can keep paginating past the unmatched window. This is
            # the only path that emits ``len(artifacts) < limit`` with
            # a non-null cursor — see the module docstring.
            cursor_anchor = last_raw_row

    next_cursor: str | None = None
    if cursor_anchor is not None:
        next_cursor = _encode_cursor(
            cursor_anchor.created_at, cursor_anchor.id
        )

    logger.info(
        "mcp.list_catalog user_id=%s role=%s state=%s subject=%s grade=%s "
        "content_type=%s page_size=%s passes=%s db_exhausted=%s",
        getattr(current_user, "id", None),
        getattr(getattr(current_user, "role", None), "value", None),
        args["state"],
        args["subject_code"],
        args["grade"],
        args["content_type"],
        len(artifacts_rows),
        passes,
        db_exhausted,
    )

    return {
        "artifacts": [_row_to_summary(r) for r in artifacts_rows],
        "next_cursor": next_cursor,
    }


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "MAX_OVERFETCH_PASSES",
    "DEFAULT_STATE",
    "list_catalog",
]
