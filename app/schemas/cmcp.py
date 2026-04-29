"""
CB-CMCP-001 — Pydantic schemas for the Curriculum-Mapped Content Pipeline.

This stripe (M1-A 1A-1) ships the minimal ``GenerationRequest`` shape
needed by ``GuardrailEngine.build_prompt()``. Stripe M1-A 1A-2 will
extend this module with ``GenerationResult`` + ``AlignmentReport`` and
the ``/api/cmcp/generate`` route schemas.

Per the locked plan §7 M1-A:
- ``GenerationRequest`` carries the dimensions used to query the CEG
  (``grade``, ``subject_id``, ``strand_id``, optional ``topic``) plus
  the artifact-level knobs (``content_type``, ``difficulty``).
- The full request schema (with output formatting, length, source-doc
  pointers, etc.) is intentionally deferred to 1A-2 — keep this stripe
  self-contained per the issue body.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Locked content types (per plan §7 M1-A acceptance gate listing all five).
# The ``content_type`` is consumed by 1A-2's generation route to pick the
# template + length budget; for 1A-1 it's just embedded in the prompt.
ContentType = Literal[
    "quiz",
    "worksheet",
    "study_guide",
    "sample_test",
    "assignment",
]


# Difficulty band matches CB-TUTOR-001/002 conventions (easy/medium/hard).
Difficulty = Literal["easy", "medium", "hard"]


class GenerationRequest(BaseModel):
    """Minimal generation request shape consumed by ``GuardrailEngine``.

    Carries the dimensions needed to query the M0 ``CEGExpectation``
    table for the SE list that anchors the prompt. ``topic`` is an
    optional coarse string-match filter (semantic / pgvector lookup is
    deferred to M3 batch 3I per the locked plan).

    Stripe scope (1A-1):
    - Required dimensions: ``grade``, ``subject_id``, ``strand_id``,
      ``content_type``.
    - Optional: ``topic`` (string filter), ``difficulty``,
      ``curriculum_version_id`` (defaults to "active rows" when None —
      the GuardrailEngine query filters ``active=True``).
    """

    model_config = ConfigDict(extra="forbid")

    grade: int = Field(..., ge=1, le=12, description="Ontario grade level (1-12).")
    subject_id: int = Field(..., gt=0, description="FK -> ceg_subjects.id")
    strand_id: int = Field(..., gt=0, description="FK -> ceg_strands.id")
    content_type: ContentType = Field(
        ..., description="Artifact type (quiz, worksheet, etc.)."
    )
    topic: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Optional coarse topic string. When supplied, the GuardrailEngine "
            "filters CEG SEs by case-insensitive substring match on the "
            "expectation description. Semantic search is M3 territory."
        ),
    )
    difficulty: Difficulty = Field(
        default="medium", description="Difficulty band for the artifact."
    )
    curriculum_version_id: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Optional pin to a specific ``curriculum_versions.id``. When "
            "None, the engine targets the rows with ``active=True`` for the "
            "given (grade, subject_id) — i.e., the live curriculum slice."
        ),
    )
