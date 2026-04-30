"""CB-CMCP-001 M3α 3C-1 (#4586) — Surface dispatch audit + queue table.

One row per (artifact, surface) pair, written by the surface dispatcher
when an APPROVED CMCP artifact fans out to one of the three M3α
surfaces (bridge / dci / digest). Doubles as:

* **Audit trail** for the 24h-surface-rate metric (per surface_telemetry
  3C-5). The dispatcher emits ``cmcp.surface.dispatched`` log lines on
  success, but the persisted row is the ground-truth source the
  3C-4 frontend (Bridge card list) reads from.
* **Bridge queue** — 3C-4's frontend queries
  ``cmcp_surface_dispatches WHERE surface='bridge' AND parent_id=?``
  to render the Bridge card list. The renderer at consumption time
  hydrates the artifact body from ``study_guides``.
* **DCI / digest dispatch records** — the in-process DCI / digest
  block-list endpoints (M3β, future stripes) read these rows when
  composing the parent's daily ritual / email digest. Until those
  endpoints land, the rows still serve as a "this artifact was
  dispatched to this surface" durability check.

Schema rationale
----------------
* ``status`` is a free-form 16-char string (``ok`` / ``failed`` for
  M3α). Kept short + unindexed because the dispatcher never queries by
  status — the surface-list endpoints filter on (parent_id, surface,
  state). Failures become an ops-log signal, not a queue item.
* ``parent_id`` + ``kid_id`` are nullable so the audit row can record
  a dispatch even when the surface fan-out determined the artifact had
  no eligible parent / kid (for the bridge surface, there's still a
  card to write — for digest, a no-eligible-parent row is just an
  audit no-op the dispatcher records once and skips).
* ``(artifact_id, surface, parent_id, kid_id)`` is the natural unique
  key — re-dispatching the same tuple on retry must NOT insert a
  duplicate row. We rely on a unique index in the DB layer.
* No FK to ``study_guides.id`` despite logical reference — the table
  is an audit log; if the artifact is ever hard-deleted the audit row
  must outlive it for ops recovery. ``ON DELETE SET NULL`` would lose
  the artifact_id on delete, which is worse for forensics.

Out of scope (per #4586)
------------------------
* Cross-process queue worker (M3α is in-process synchronous; M3β
  optional async).
* Per-surface render endpoints (3C-4 frontend reads bridge rows
  directly via existing artifact endpoints).
"""
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func

from app.db.database import Base


class CMCPSurfaceDispatch(Base):
    __tablename__ = "cmcp_surface_dispatches"

    id = Column(Integer, primary_key=True, index=True)

    # Logical FK to study_guides.id — see module docstring on why no FK.
    artifact_id = Column(Integer, nullable=False, index=True)

    # One of {"bridge", "dci", "digest"}. See
    # ``app.services.cmcp.surface_telemetry.SURFACES`` for the canonical
    # allow-list. Stored as a 16-char string (not a Python Enum) so PG
    # + SQLite agree on the storage representation.
    surface = Column(String(16), nullable=False, index=True)

    # Parent recipient ``users.id`` for digest / bridge surfaces; the
    # DCI surface is keyed by parent + kid pair. ``parent_id`` is
    # nullable for the rare "no eligible parent" audit path.
    parent_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    # Kid ``students.id`` for DCI ritual; nullable for parent-only paths
    # (bridge, digest summary block).
    kid_id = Column(Integer, nullable=True)

    # ``ok`` on successful fan-out; ``failed`` after the retry budget
    # is exhausted. Kept open-string for forward compatibility (future
    # M3β statuses: ``deferred``, ``skipped_visibility``).
    status = Column(String(16), nullable=False, default="ok")

    # Number of attempts the dispatcher needed before terminal status.
    # Helps isolate flaky surfaces in the ops dashboard.
    attempts = Column(Integer, nullable=False, default=1)

    # Last-error excerpt (truncated to 500 chars). Null on success.
    last_error = Column(String(500), nullable=True)

    dispatched_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "artifact_id",
            "surface",
            "parent_id",
            "kid_id",
            name="uq_cmcp_surface_dispatch_tuple",
        ),
        Index(
            "ix_cmcp_surface_dispatch_artifact_surface",
            "artifact_id",
            "surface",
        ),
        Index(
            "ix_cmcp_surface_dispatch_parent_surface",
            "parent_id",
            "surface",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover — debug only
        return (
            "CMCPSurfaceDispatch("
            f"id={self.id}, artifact_id={self.artifact_id}, "
            f"surface={self.surface!r}, parent_id={self.parent_id}, "
            f"kid_id={self.kid_id}, status={self.status!r})"
        )
