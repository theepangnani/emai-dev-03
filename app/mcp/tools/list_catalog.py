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

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults / bounds
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
DEFAULT_STATE = "APPROVED"


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

    Raises :class:`HTTPException` (422) on malformed input — opaque
    cursors should be treated like a token: garbage in → caller error,
    not a 500.
    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        created_iso = payload.get("created_at")
        row_id = int(payload["id"])
    except (ValueError, KeyError, binascii.Error, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid cursor: {exc}",
        ) from exc

    if created_iso is None:
        return None, row_id
    try:
        created_at = datetime.fromisoformat(created_iso)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid cursor created_at: {exc}",
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
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid limit: {exc}",
            ) from exc
    if limit < 1 or limit > MAX_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"limit must be between 1 and {MAX_LIMIT} "
                f"(got {limit})"
            ),
        )
    out["limit"] = limit
    return out


def _opt_str(args: Mapping[str, Any], key: str) -> str | None:
    """Return ``args[key]`` if a non-empty string, else ``None``."""
    val = args.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{key!r} must be a string",
        )
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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{key!r} must be an integer",
        )
    try:
        return int(val)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{key!r} must be an integer ({exc})",
        ) from exc


# ---------------------------------------------------------------------------
# Role scoping
# ---------------------------------------------------------------------------


def _resolve_caller_board_id(user: Any) -> str | None:
    """Best-effort lookup of a BOARD_ADMIN caller's board id.

    Mirrors :func:`app.mcp.tools.get_artifact._resolve_caller_board_id`.
    The ``User`` model does not currently carry a ``board_id`` column
    (board affiliation is a CB-CMCP-001 M3-E concern); until that lands,
    we read an attribute off the user instance if a downstream stripe
    sets one, otherwise return ``None``. Returning ``None`` collapses
    the BOARD_ADMIN scope filter to "no rows visible" — the same
    deny-by-default posture as 2B-2.
    """
    return getattr(user, "board_id", None)


def _apply_role_scope(query, current_user, db: Session):  # type: ignore[no-untyped-def]
    """Narrow ``query`` to artifacts the caller's role may see.

    Mirrors the access-matrix in 2B-2's ``get_artifact``:

    - ``ADMIN`` / ``CURRICULUM_ADMIN`` → every artifact (no narrowing).
    - ``BOARD_ADMIN`` → artifacts whose ``board_id`` matches the
      admin's board scope AND ``board_id IS NOT NULL`` (legacy rows
      with a NULL ``board_id`` are denied — same conservative default
      as 2B-2's ``_user_can_view``). When the caller has no resolvable
      ``board_id`` (the M2 default until M3-E lands), the result is an
      empty selection.
    - ``TEACHER`` → artifacts authored by the teacher OR pinned to a
      course the teacher owns. Course ownership is detected via
      ``courses.teacher_id → teachers.user_id == current_user.id`` so
      this stripe doesn't depend on the assignment-context graph.
    - ``PARENT`` → artifacts authored by the parent OR by any of their
      linked students.
    - ``STUDENT`` → artifacts authored by the student.
    - Anything else (None / unknown) → empty result. The route layer
      403s before we get here for unknown roles, but keep the
      defence-in-depth.
    """
    # Lazy imports inside services that catch broadly — see CLAUDE.md
    # "lazy-import ORM models" rule for why this isn't at module top.
    from app.models.course import Course
    from app.models.student import Student, parent_students
    from app.models.study_guide import StudyGuide
    from app.models.teacher import Teacher
    from app.models.user import UserRole  # noqa: F401

    role = current_user.role if current_user is not None else None
    if role is None:
        return query.filter(False)

    role_name = role.name if hasattr(role, "name") else str(role).upper()

    if role_name in ("ADMIN", "CURRICULUM_ADMIN"):
        return query

    if role_name == "BOARD_ADMIN":
        caller_board = _resolve_caller_board_id(current_user)
        if caller_board is None:
            # No resolvable board → fail closed. Mirrors 2B-2 row-level
            # behaviour: BOARD_ADMINs never see legacy unscoped rows.
            return query.filter(False)
        return query.filter(
            StudyGuide.board_id.is_not(None),
            StudyGuide.board_id == str(caller_board),
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
        return query.filter(
            (StudyGuide.user_id == current_user.id)
            | (StudyGuide.course_id.in_(owned_course_ids))
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
        return query.filter(
            (StudyGuide.user_id == current_user.id)
            | (StudyGuide.user_id.in_(kid_user_ids))
        )

    if role_name == "STUDENT":
        return query.filter(StudyGuide.user_id == current_user.id)

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


def list_catalog(
    arguments: Mapping[str, Any],
    current_user: Any,
    db: Session,
) -> dict[str, Any]:
    """MCP tool handler: paginated, role-scoped artifact list.

    Returns ``{"artifacts": [...], "next_cursor": str | None}``. Empty
    result yields ``{"artifacts": [], "next_cursor": None}`` (NOT 404 —
    a list endpoint on an empty selection is success, not failure).
    """
    # Lazy imports — see ``_apply_role_scope`` for the rationale.
    from app.models.study_guide import StudyGuide

    args = _validate_arguments(arguments)

    query = db.query(StudyGuide).filter(
        StudyGuide.archived_at.is_(None),
        StudyGuide.state == args["state"],
    )

    # Curriculum filters: only narrow when the row carries the metadata.
    # ``subject_code`` + ``grade`` are post-filtered in Python (after the
    # role-scope subquery narrows the candidate set) because the
    # ``se_codes`` JSON array shape isn't portable across SQLite + PG
    # without a dialect branch. See the post-filter pass below for the
    # Python-side implementation; both filters share the same window so
    # we don't pay double the over-fetch cost.
    #
    # Pagination contract under post-filtering: an over-fetched window
    # of ``limit + 1`` rows can shrink to fewer than ``limit`` matches
    # (or even zero). When that happens we still emit a ``next_cursor``
    # if the SQL window's last row exists, so the caller can advance
    # past unmatched rows. Callers must NOT use "empty page → done";
    # they must check ``next_cursor is None`` instead.
    if args["grade"] is not None and hasattr(StudyGuide, "grade"):
        # Forward-compat: if a future schema adds a real ``grade``
        # column we'll prefer the SQL filter over the post-filter.
        query = query.filter(StudyGuide.grade == args["grade"])
    if args["content_type"]:
        # ``guide_type`` is the existing column; map ``content_type``
        # (the MCP-spec name) to it.
        query = query.filter(StudyGuide.guide_type == args["content_type"])

    # Apply role scope BEFORE the cursor pagination so the cursor's
    # tuple comparison only sees rows the caller may legally see.
    query = _apply_role_scope(query, current_user, db)

    # Cursor pagination: rows ordered ``id DESC`` (which is functionally
    # equivalent to ``created_at DESC`` because ``id`` is monotonic on
    # insert). Cursor predicate is ``id < cursor_id``. See the module
    # docstring for why we don't include ``created_at`` in the predicate.
    if args["cursor"]:
        _cursor_created_at, cursor_id = _decode_cursor(args["cursor"])
        query = query.filter(StudyGuide.id < cursor_id)

    query = query.order_by(StudyGuide.id.desc())

    # Over-fetch by 1 to detect "more rows exist?" without COUNT.
    rows = query.limit(args["limit"] + 1).all()

    has_more = len(rows) > args["limit"]
    if has_more:
        # Anchor the cursor to the LAST page-window row BEFORE any
        # Python-side post-filter trims it. If we anchored to the
        # post-filter tail instead, a page that emits 0 ``subject_code``
        # matches would emit no cursor and the caller couldn't continue
        # past the unmatched window.
        cursor_anchor = rows[args["limit"] - 1]
        rows = rows[: args["limit"]]
    else:
        cursor_anchor = None

    # Post-filters for ``subject_code`` + ``grade`` (Python-side because
    # the SE codes JSON shape isn't portable across dialects — see the
    # pre-filter docstring above). Order doesn't matter; both predicates
    # are applied to the same row collection.
    if args["subject_code"]:
        prefix = args["subject_code"].upper() + "."
        rows = [
            r
            for r in rows
            if r.se_codes
            and any(
                isinstance(c, str) and c.upper().startswith(prefix)
                for c in r.se_codes
            )
        ]
    if args["grade"] is not None and not hasattr(StudyGuide, "grade"):
        # Skip the post-filter when a real ``grade`` column exists
        # (already handled by the SQL pre-filter above). For today's
        # schema (no column) we parse the SE code's grade segment.
        target = args["grade"]
        rows = [
            r
            for r in rows
            if r.se_codes and _se_grade(r.se_codes) == target
        ]

    next_cursor: str | None = None
    if cursor_anchor is not None:
        next_cursor = _encode_cursor(
            cursor_anchor.created_at, cursor_anchor.id
        )

    logger.info(
        "mcp.list_catalog user_id=%s role=%s state=%s subject=%s grade=%s "
        "content_type=%s page_size=%s has_more=%s",
        getattr(current_user, "id", None),
        getattr(getattr(current_user, "role", None), "value", None),
        args["state"],
        args["subject_code"],
        args["grade"],
        args["content_type"],
        len(rows),
        has_more,
    )

    return {
        "artifacts": [_row_to_summary(r) for r in rows],
        "next_cursor": next_cursor,
    }


__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "DEFAULT_STATE",
    "list_catalog",
]
