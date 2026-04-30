"""CB-CMCP-001 M3-E 3E-1 (#4653) — Board catalog REST endpoint.

``GET /api/board/{board_id}/catalog`` exposes the artifact catalog for a
given board. This is the **primary board surface** under D7=B — REST + LTI
are the canonical interfaces for pilot boards; MCP is the secondary
machine-to-machine surface (already shipped in M2).

Role gating
-----------
- ``BOARD_ADMIN`` → may only fetch their own board's catalog. Any other
  ``board_id`` in the path returns ``404`` (no existence oracle — a
  cross-board probe must read identically to a non-existent board).
- ``ADMIN`` → may fetch any board's catalog (ops / debug bypass; matches
  the role-scope bypass in the MCP ``list_catalog`` handler).
- Any other role → ``403`` (insufficient permissions).
- ``BOARD_ADMIN`` whose ``resolve_caller_board_id`` returns ``None``
  (the M2 default until per-user board stamping lands) → ``404`` for
  *any* path ``board_id``. Same fail-closed posture as M2's MCP tools.

Visibility filter
-----------------
Returns only ``state == 'APPROVED'`` rows whose ``board_id`` matches the
path. ``archived_at IS NULL`` is also enforced. SELF_STUDY rows never
surface here — D3=C makes them family-private, and the BOARD_ADMIN
matrix in 2B-2 / 2B-3 already denies them at the row level.

Pagination contract
-------------------
Cursor pagination matches M2-followup #4568's over-fetch-loop semantics
exactly — the cursor encoding + decoding + over-fetch helper is reused
from :mod:`app.mcp.tools.list_catalog` so a future change to the cursor
shape only has to land in one place. Standard semantics:
``next_cursor is None`` → caller has reached the end of iteration.

Out of scope
------------
- LTI surface (separate stripe — D7=B's LTI primary lands later in M3).
- Filters beyond what 2B-3 already exposes (subject_code / grade /
  content_type) — this stripe ships the minimum viable board catalog
  and inherits the 2B-3 query parameters via direct mapping.
- Boards-of-boards / federation. Single board scope only.
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.routes.curriculum import require_cmcp_enabled
from app.db.database import get_db
from app.mcp.tools._visibility import resolve_caller_board_id
from app.mcp.tools.list_catalog import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MAX_OVERFETCH_PASSES,
    _decode_cursor,
    _encode_cursor,
    _post_filter_rows,
    _se_grade,
    _se_subject,
)
from app.models.user import User, UserRole
from app.services import gcs_service
from app.services.cmcp.artifact_state import ArtifactState
from app.services.cmcp.coverage_map_service import compute_coverage_map

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/board", tags=["CMCP Board Catalog"])


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------


class BoardCatalogArtifact(BaseModel):
    """Public summary of a single artifact in a board catalog response.

    Mirrors the fields called out in #4653's "metadata" list (id,
    content_type, subject, grade, se_codes, alignment_score, created_at,
    ai_engine) plus the small set of identifiers the M2 ``list_catalog``
    response already exposes (title, state) so existing MCP clients can
    reuse their summary parsers.
    """

    id: int
    title: str
    content_type: str
    state: str
    subject_code: str | None = None
    grade: int | None = None
    se_codes: list[str] = Field(default_factory=list)
    alignment_score: float | None = None
    ai_engine: str | None = None
    course_id: int | None = None
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=False)


class BoardCatalogResponse(BaseModel):
    """Top-level response envelope.

    ``next_cursor`` is ``None`` when the caller has reached the end of
    iteration (see #4568 over-fetch-loop contract).
    """

    artifacts: list[BoardCatalogArtifact]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Role gate
# ---------------------------------------------------------------------------


def _require_board_or_admin(
    current_user: User = Depends(require_cmcp_enabled),
) -> User:
    """403 unless the caller is BOARD_ADMIN or ADMIN.

    Layered on top of ``require_cmcp_enabled`` so unauth → 401, flag-off
    → 403, and not-allowlisted-role → 403. Mirrors the gating pattern
    used by ``cmcp_review`` (#4576).
    """
    if not (
        current_user.has_role(UserRole.BOARD_ADMIN)
        or current_user.has_role(UserRole.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for board catalog",
        )
    return current_user


# ---------------------------------------------------------------------------
# Row → response dict
# ---------------------------------------------------------------------------


def _row_to_artifact(row: Any) -> BoardCatalogArtifact:
    """Project a ``StudyGuide`` row to the public artifact summary.

    The board catalog payload is intentionally similar to the MCP
    ``list_catalog`` summary (so clients can share parsing) but adds
    ``alignment_score`` + ``ai_engine`` per #4653's metadata list.
    """
    created_at = row.created_at.isoformat() if row.created_at else None
    alignment = row.alignment_score
    if alignment is not None:
        # ``alignment_score`` is stored as Numeric — coerce to float so
        # the JSON response is a plain number, not a Decimal string.
        alignment = float(alignment)
    return BoardCatalogArtifact(
        id=row.id,
        title=row.title,
        content_type=row.guide_type,
        state=row.state,
        subject_code=_se_subject(row.se_codes),
        grade=_se_grade(row.se_codes),
        se_codes=list(row.se_codes) if row.se_codes else [],
        alignment_score=alignment,
        ai_engine=row.ai_engine,
        course_id=row.course_id,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/{board_id}/catalog",
    response_model=BoardCatalogResponse,
    summary="List APPROVED artifacts within a board (BOARD_ADMIN-scoped)",
)
def get_board_catalog(
    board_id: str,
    cursor: str | None = Query(default=None, description="Opaque pagination cursor"),
    limit: int = Query(
        default=DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Page size (1..{MAX_LIMIT})",
    ),
    subject_code: str | None = Query(
        default=None,
        description="Optional SE-code subject prefix filter (e.g. MATH)",
    ),
    grade: int | None = Query(
        default=None,
        description="Optional grade filter (matched against SE-code segment)",
    ),
    content_type: str | None = Query(
        default=None,
        description="Optional content-type filter (maps to guide_type column)",
    ),
    current_user: User = Depends(_require_board_or_admin),
    db: Session = Depends(get_db),
) -> BoardCatalogResponse:
    """Paginated APPROVED-artifact list for a single board.

    Cross-board reads by a BOARD_ADMIN return ``404`` (no existence
    oracle): we never let a BOARD_ADMIN distinguish "this board doesn't
    exist" from "this board exists but you don't admin it" — both leak
    the same byte. ADMIN may fetch any board.

    ``BOARD_ADMIN`` whose ``resolve_caller_board_id`` returns ``None``
    (the M2 default state until per-user board stamping lands) gets
    ``404`` for any ``board_id``. Same fail-closed posture as the MCP
    tools' BOARD_ADMIN scope.
    """
    # Lazy import to match the project-wide ORM-import rule (services
    # that catch broadly must lazy-import models so conftest reloads
    # don't silently desync them; CLAUDE.md "lazy-import ORM models").
    from app.models.study_guide import StudyGuide

    # ── Cross-board / scope check ─────────────────────────────────────
    is_admin = current_user.has_role(UserRole.ADMIN)
    if not is_admin:
        caller_board = resolve_caller_board_id(current_user)
        if caller_board is None or str(caller_board) != str(board_id):
            # No existence oracle — same response for "wrong board" and
            # "no board scope at all".
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )

    has_real_grade_column = hasattr(StudyGuide, "grade")

    # Strip whitespace to match list_catalog's _opt_str semantics — keep
    # the inputs aligned so a downstream change in 2B-3 doesn't desync.
    subject_code_norm = subject_code.strip() if subject_code else None
    if subject_code_norm == "":
        subject_code_norm = None
    content_type_norm = content_type.strip() if content_type else None
    if content_type_norm == "":
        content_type_norm = None

    def _build_window_query(cursor_id: int | None):
        """Build the SQL window query for one over-fetch pass.

        The shape mirrors :func:`list_catalog._build_window_query` —
        ``state == APPROVED`` + ``archived_at IS NULL`` + the board
        scope filter (always applied on this surface, regardless of
        caller role) + cursor predicate. We deliberately keep the
        ``board_id`` filter on the SQL window even for ADMIN callers
        because the route's purpose is "this board's catalog" — an
        ADMIN reading another board's catalog still wants only that
        board's rows.
        """
        q = db.query(StudyGuide).filter(
            StudyGuide.archived_at.is_(None),
            StudyGuide.state == ArtifactState.APPROVED,
            StudyGuide.board_id.is_not(None),
            StudyGuide.board_id == str(board_id),
        )
        if grade is not None and has_real_grade_column:
            q = q.filter(StudyGuide.grade == grade)
        if content_type_norm:
            q = q.filter(StudyGuide.guide_type == content_type_norm)
        if cursor_id is not None:
            q = q.filter(StudyGuide.id < cursor_id)
        return q.order_by(StudyGuide.id.desc())

    # ── Cursor seeding ────────────────────────────────────────────────
    if cursor:
        try:
            _cursor_created_at, cursor_id = _decode_cursor(cursor)
        except Exception as exc:
            # ``_decode_cursor`` raises MCPToolValidationError on
            # malformed input. Translate to FastAPI 422 (matches
            # request-validation conventions).
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid cursor: {exc}",
            ) from exc
    else:
        cursor_id = None

    # ── Over-fetch loop (#4568 contract) ──────────────────────────────
    accumulated: list = []
    last_raw_row = None
    db_exhausted = False
    passes = 0

    while passes < MAX_OVERFETCH_PASSES and len(accumulated) < limit:
        passes += 1
        raw_rows = _build_window_query(cursor_id).limit(limit + 1).all()
        if not raw_rows:
            db_exhausted = True
            break

        has_more_in_window = len(raw_rows) > limit
        page_rows = raw_rows[:limit] if has_more_in_window else raw_rows

        last_raw_row = page_rows[-1]
        accumulated.extend(
            _post_filter_rows(
                page_rows,
                subject_code=subject_code_norm,
                grade=grade,
                has_real_grade_column=has_real_grade_column,
            )
        )

        if not has_more_in_window:
            db_exhausted = True
            break

        cursor_id = last_raw_row.id

    if len(accumulated) > limit:
        artifacts_rows = accumulated[:limit]
        cursor_anchor = artifacts_rows[-1]
    else:
        artifacts_rows = accumulated
        if db_exhausted:
            cursor_anchor = None
        else:
            cursor_anchor = last_raw_row

    next_cursor: str | None = None
    if cursor_anchor is not None:
        next_cursor = _encode_cursor(
            cursor_anchor.created_at, cursor_anchor.id
        )

    logger.info(
        "board_catalog board=%s user_id=%s role=%s page_size=%s passes=%s "
        "db_exhausted=%s",
        board_id,
        getattr(current_user, "id", None),
        getattr(getattr(current_user, "role", None), "value", None),
        len(artifacts_rows),
        passes,
        db_exhausted,
    )

    return BoardCatalogResponse(
        artifacts=[_row_to_artifact(r) for r in artifacts_rows],
        next_cursor=next_cursor,
    )


# ---------------------------------------------------------------------------
# CB-CMCP-001 M3-E 3E-3 (#4660) — Signed CSV export
# ---------------------------------------------------------------------------

#: TTL for the V4 signed download URL handed back to the caller.
#: Per spec: 1 hour (3600 seconds).
SIGNED_CSV_TTL_SECONDS = 3600


class BoardCatalogExportResponse(BaseModel):
    """Response envelope for a CSV-export request.

    ``download_url`` is a TTL-limited V4 signed GCS URL pointing at the
    just-uploaded CSV object. ``expires_at`` is the absolute UTC ISO-8601
    timestamp at which the signed URL stops working (caller should not
    rely on the embedded ``X-Goog-Expires`` query param).
    """

    download_url: str
    expires_at: str


def _build_catalog_csv_bytes(
    *,
    board_id: str,
    coverage_map: dict[str, dict[int, int]],
    artifacts: list[Any],
) -> bytes:
    """Render the export CSV to bytes (UTF-8).

    The export is a single CSV with two stacked sections:

    1. **Coverage map** — one row per (strand, grade, count) tuple. Empty
       strands simply don't appear (matches the coverage_map_service
       contract — see :func:`compute_coverage_map`).
    2. **Artifact list** — one row per APPROVED artifact with the same
       fields the REST catalog endpoint exposes (id, title, content_type,
       state, subject_code, grade, se_codes, alignment_score, ai_engine,
       course_id, created_at).

    Sections are separated by a blank line + section-header row so the
    file remains a valid CSV (consumers that only know the artifact
    section can grep past the header divider).
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    # Header row — board_id surfaced for caller cross-checks.
    writer.writerow(["board_id", board_id])
    writer.writerow([])

    # Section 1 — coverage map.
    writer.writerow(["section", "coverage_map"])
    writer.writerow(["strand", "grade", "count"])
    for strand in sorted(coverage_map.keys()):
        grades = coverage_map[strand]
        for grade in sorted(grades.keys()):
            writer.writerow([strand, grade, grades[grade]])

    # Section divider.
    writer.writerow([])

    # Section 2 — artifact list.
    writer.writerow(["section", "artifacts"])
    writer.writerow(
        [
            "id",
            "title",
            "content_type",
            "state",
            "subject_code",
            "grade",
            "se_codes",
            "alignment_score",
            "ai_engine",
            "course_id",
            "created_at",
        ]
    )
    for art in artifacts:
        writer.writerow(
            [
                art.id,
                art.title,
                art.content_type,
                art.state,
                art.subject_code or "",
                art.grade if art.grade is not None else "",
                # Pipe-separate SE codes so the CSV stays one-row-per-artifact.
                "|".join(art.se_codes) if art.se_codes else "",
                (
                    f"{art.alignment_score:.3f}"
                    if art.alignment_score is not None
                    else ""
                ),
                art.ai_engine or "",
                art.course_id if art.course_id is not None else "",
                art.created_at or "",
            ]
        )

    return buf.getvalue().encode("utf-8")


def _query_all_approved_artifacts(
    db: Session, *, board_id: str
) -> list[BoardCatalogArtifact]:
    """Load every APPROVED artifact for a board (no pagination).

    The CSV export is intentionally NOT paginated — a board admin
    pulling a snapshot of their catalog should get the whole thing in
    one file. We reuse the :func:`_row_to_artifact` projector so the CSV
    columns match the JSON catalog endpoint exactly.
    """
    from app.models.study_guide import StudyGuide

    rows = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.archived_at.is_(None),
            StudyGuide.state == ArtifactState.APPROVED,
            StudyGuide.board_id.is_not(None),
            StudyGuide.board_id == str(board_id),
        )
        .order_by(StudyGuide.id.desc())
        .all()
    )
    return [_row_to_artifact(r) for r in rows]


@router.post(
    "/{board_id}/catalog/export.csv",
    response_model=BoardCatalogExportResponse,
    summary="Export the board's APPROVED catalog as a TTL-limited signed CSV URL",
)
def export_board_catalog_csv(
    board_id: str,
    current_user: User = Depends(_require_board_or_admin),
    db: Session = Depends(get_db),
) -> BoardCatalogExportResponse:
    """Generate a CSV of the board's catalog, upload to GCS, return a
    1-hour signed download URL.

    Auth + cross-board posture exactly mirrors :func:`get_board_catalog`:

    - BOARD_ADMIN may export only their own board (mismatched / unscoped
      → 404, no existence oracle).
    - ADMIN may export any board.
    - Non-(BOARD_ADMIN/ADMIN) → 403 (handled by ``_require_board_or_admin``).

    The CSV stacks the 3E-2 coverage map + the 3E-1 artifact list in one
    file. The bucket itself is private; the V4 signed URL is the only
    handle the caller is given.
    """
    # ── Cross-board / scope check (mirrors get_board_catalog) ─────────
    is_admin = current_user.has_role(UserRole.ADMIN)
    if not is_admin:
        caller_board = resolve_caller_board_id(current_user)
        if caller_board is None or str(caller_board) != str(board_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )

    coverage_map = compute_coverage_map(board_id, db)
    artifacts = _query_all_approved_artifacts(db, board_id=str(board_id))

    csv_bytes = _build_catalog_csv_bytes(
        board_id=str(board_id),
        coverage_map=coverage_map,
        artifacts=artifacts,
    )

    # GCS object path — bucket is shared, so namespace by board + a
    # request-scoped UUID so two concurrent exports never collide.
    issued_at = datetime.now(tz=timezone.utc)
    gcs_path = (
        f"cmcp/board_catalog_exports/{board_id}/"
        f"{issued_at.strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex}.csv"
    )

    gcs_service.upload_file(gcs_path, csv_bytes, "text/csv")
    download_url = gcs_service.generate_signed_url(
        gcs_path, ttl_seconds=SIGNED_CSV_TTL_SECONDS
    )
    expires_at = issued_at + timedelta(seconds=SIGNED_CSV_TTL_SECONDS)

    logger.info(
        "board_catalog_export board=%s user_id=%s artifacts=%s strands=%s "
        "csv_bytes=%s gcs_path=%s",
        board_id,
        getattr(current_user, "id", None),
        len(artifacts),
        len(coverage_map),
        len(csv_bytes),
        gcs_path,
    )

    return BoardCatalogExportResponse(
        download_url=download_url,
        expires_at=expires_at.isoformat(),
    )


__all__ = [
    "router",
    "BoardCatalogArtifact",
    "BoardCatalogResponse",
    "BoardCatalogExportResponse",
    "SIGNED_CSV_TTL_SECONDS",
]
