"""
CB-CMCP-001 M0-A 0A-1 — Curriculum Expectations Graph (CEG) schema.

Four core tables backing the Curriculum bounded context (plan §3.2):

- `ceg_subjects`        — top-level subject dimension (e.g., MATH, LANG, SCI)
- `ceg_strands`         — per-subject strand grouping (e.g., "B: Number Sense")
- `ceg_expectations`    — Ontario curriculum expectations (OE + SE rows;
                          SE rows carry `parent_oe_id` self-FK)
- `curriculum_versions` — versioned snapshots per subject/grade with
                          a `change_severity` enum (D9=B locked decision):
                          ``wording_only`` vs ``scope_substantive``

Embedding column on `ceg_expectations` is dialect-aware:

- PostgreSQL: ``vector(1536)`` via the pgvector SQLAlchemy bindings.
- SQLite:     ``JSON`` column storing a list of floats; semantic-search
              query path uses Python-side cosine similarity (acceptable
              for dev/test corpora ≤ ~2,000 expectations).

The pgvector extension itself (``CREATE EXTENSION IF NOT EXISTS vector``)
is created during the M0-A 0A-4 migration stripe — not here. This module
only declares the SQLAlchemy column type per dialect; ``Base.metadata.
create_all()`` handles the table CREATE on first startup.

Reuse anchor: phase-2 ``CurriculumExpectation`` (28 LOC) at
``c:/dev/emai/class-bridge-phase-2/app/models/curriculum.py``. This
dev-03 model is a NEW model with the locked D9 + DD §2.1 spec — the
phase-2 model is left untouched.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.core.config import settings
from app.db.database import Base

# Dialect gate: pgvector on PG, JSON list of floats on SQLite.
# Pattern matches existing dev-03 dialect-aware models (e.g., demo_session.py,
# learning_cycle.py).
_IS_PG = "sqlite" not in settings.database_url

if _IS_PG:
    # pgvector ships SQLAlchemy bindings as ``Vector`` (alias of ``VECTOR``).
    # Importing inside the gate keeps SQLite-only test environments from
    # requiring the pgvector extension to be installed at the DB layer.
    from pgvector.sqlalchemy import Vector

    _EmbeddingType = Vector(1536)
else:
    _EmbeddingType = JSON


# --- change_severity enum (D9=B locked) ----------------------------------
# Stored as ``String(20)`` rather than SQLAlchemy ``Enum(PythonEnum)`` —
# per project memory, ``Enum(PythonEnum)`` stores enum NAMES on PostgreSQL
# (not values), which silently breaks cross-dialect string comparisons.
# The two valid values are pinned by a CHECK constraint on the column.
CHANGE_SEVERITY_WORDING_ONLY = "wording_only"
CHANGE_SEVERITY_SCOPE_SUBSTANTIVE = "scope_substantive"
CHANGE_SEVERITY_VALUES = (
    CHANGE_SEVERITY_WORDING_ONLY,
    CHANGE_SEVERITY_SCOPE_SUBSTANTIVE,
)


# --- expectation_type enum (OE vs SE) ------------------------------------
# Same rationale: store as ``String(20)`` with a CHECK constraint.
EXPECTATION_TYPE_OVERALL = "overall"
EXPECTATION_TYPE_SPECIFIC = "specific"
EXPECTATION_TYPE_VALUES = (
    EXPECTATION_TYPE_OVERALL,
    EXPECTATION_TYPE_SPECIFIC,
)


class CEGSubject(Base):
    """Top-level subject dimension (e.g., ``MATH``, ``LANG``, ``SCI``).

    A subject groups strands and expectations and is the anchor for
    per-subject curriculum versions.
    """

    __tablename__ = "ceg_subjects"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    strands = relationship(
        "CEGStrand", back_populates="subject", cascade="all, delete-orphan"
    )
    expectations = relationship(
        "CEGExpectation", back_populates="subject", cascade="all, delete-orphan"
    )


class CEGStrand(Base):
    """Per-subject strand (e.g., ``A: Number Sense and Numeration``)."""

    __tablename__ = "ceg_strands"

    id = Column(Integer, primary_key=True)
    subject_id = Column(
        Integer,
        ForeignKey("ceg_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code = Column(String(20), nullable=False)  # e.g., "A", "B", "C"
    name = Column(String(200), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    subject = relationship("CEGSubject", back_populates="strands")
    expectations = relationship(
        "CEGExpectation", back_populates="strand", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("subject_id", "code", name="uq_ceg_strands_subject_code"),
    )


class CEGExpectation(Base):
    """Ontario curriculum expectation (overall or specific).

    OE rows have ``expectation_type='overall'`` and ``parent_oe_id IS NULL``.
    SE rows have ``expectation_type='specific'`` and a ``parent_oe_id`` FK
    pointing back to the OE row they fall under (DD §2.1 invariant).
    """

    __tablename__ = "ceg_expectations"

    id = Column(Integer, primary_key=True)

    # Ministry / internal identifiers (split per stripe 0A-1 spec).
    ministry_code = Column(String(40), nullable=False)  # e.g., "B2.3"
    cb_code = Column(String(80), nullable=True)  # e.g., "CB-G7-MATH-B2-SE3"

    # Dimensions.
    subject_id = Column(
        Integer,
        ForeignKey("ceg_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    strand_id = Column(
        Integer,
        ForeignKey("ceg_strands.id", ondelete="CASCADE"),
        nullable=False,
    )
    grade = Column(Integer, nullable=False)
    expectation_type = Column(String(20), nullable=False)
    parent_oe_id = Column(
        Integer,
        ForeignKey("ceg_expectations.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Content.
    description = Column(Text, nullable=False)

    # Versioning.
    curriculum_version_id = Column(
        Integer,
        ForeignKey("curriculum_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    active = Column(
        Boolean, nullable=False, default=True, server_default="TRUE"
    )

    # Embedding (dialect-aware). Nullable because extraction (M0-B) backfills
    # embeddings asynchronously; rows can be inserted before the embedding
    # job runs.
    embedding = Column(_EmbeddingType, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    subject = relationship("CEGSubject", back_populates="expectations")
    strand = relationship("CEGStrand", back_populates="expectations")
    curriculum_version = relationship(
        "CurriculumVersion", back_populates="expectations"
    )
    parent_oe = relationship(
        "CEGExpectation",
        remote_side=[id],
        backref="specific_expectations",
    )

    __table_args__ = (
        # Per stripe 0A-1 spec: indexes on (grade, subject_id), strand_id,
        # expectation_type. The pgvector ivfflat index is created in the
        # M0-A 0A-4 migration (PG-only; can't be expressed cross-dialect
        # in __table_args__).
        Index("ix_ceg_expectations_grade_subject", "grade", "subject_id"),
        Index("ix_ceg_expectations_strand", "strand_id"),
        Index("ix_ceg_expectations_type", "expectation_type"),
        Index("ix_ceg_expectations_parent_oe", "parent_oe_id"),
        Index("ix_ceg_expectations_version_active", "curriculum_version_id", "active"),
        UniqueConstraint(
            "ministry_code",
            "curriculum_version_id",
            name="uq_ceg_expectations_ministry_version",
        ),
        CheckConstraint(
            "expectation_type IN ('overall', 'specific')",
            name="ck_ceg_expectations_type",
        ),
    )


class CurriculumVersion(Base):
    """Versioned snapshot of a subject/grade slice of the CEG.

    Each row pins one version of the curriculum for a given
    ``(subject_id, grade)`` pair. The ``change_severity`` column carries
    the D9=B classifier output: ``wording_only`` changes do not flag
    downstream artifacts; ``scope_substantive`` changes do (drives the
    ``ArtifactReClassified`` domain event in M3-G).
    """

    __tablename__ = "curriculum_versions"

    id = Column(Integer, primary_key=True)
    subject_id = Column(
        Integer,
        ForeignKey("ceg_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grade = Column(Integer, nullable=False)
    version = Column(String(40), nullable=False)  # e.g., "2020-rev1", "2005"
    effective_date = Column(DateTime(timezone=True), nullable=True)
    change_severity = Column(String(20), nullable=True)  # nullable for the seed version
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    expectations = relationship(
        "CEGExpectation", back_populates="curriculum_version"
    )

    __table_args__ = (
        UniqueConstraint(
            "subject_id", "grade", "version",
            name="uq_curriculum_versions_subject_grade_version",
        ),
        Index(
            "ix_curriculum_versions_subject_grade",
            "subject_id",
            "grade",
        ),
        CheckConstraint(
            "change_severity IS NULL OR change_severity IN "
            "('wording_only', 'scope_substantive')",
            name="ck_curriculum_versions_change_severity",
        ),
    )
