"""CB-CMCP-001 M1-C 1C-3 — Voice consistency audit job (#4493).

Periodic audit that samples student-facing artifacts and flags any whose
stored ``voice_module_hash`` no longer matches the currently-active Arc
voice (or the active voice for the configured persona). Output is a JSON
report with ``consistent_count`` / ``drift_count`` / ``drift_examples`` so
operators can spot when a voice swap (FR-02.7 hot-swap) left old
artifacts speaking the wrong voice.

Usage (from repo root)::

    # Default: sample 50 artifacts, persona=student.
    python cli/audit_voice_consistency.py

    # Sample 10 artifacts.
    python cli/audit_voice_consistency.py --sample 10

    # Audit a specific persona.
    python cli/audit_voice_consistency.py --persona teacher

Exit codes:
    0  audit completed (regardless of drift_count)
    1  generic / unexpected error
    2  argparse error (handled by argparse itself)

Stub artifact source (M1 only)
------------------------------
Per the locked plan, ``voice_module_hash`` isn't yet *persisted* on the
``study_guides`` table — wave 2 (1C-2, #4480) only stamps it on the API
response object. The real persistence column lands in M3.

To unblock the audit job's interface + tests now, this CLI ships with a
small in-memory stub artifact set (see :func:`_default_stub_artifacts`)
and an injectable ``artifact_source`` callable seam (see
:func:`run_audit`). When persistence lands in M3, only that one source
function needs to be swapped to a real ``db_session.query(StudyGuide)``
selector — the JSON-output contract, drift comparison logic, CLI flags,
and tests stay unchanged.

The stub deliberately includes ONE artifact whose hash doesn't match
the active voice, so a default run produces a non-trivial report
(operators eyeballing the JSON immediately see the drift_examples shape).

Issue: #4493
Epic: #4351
Plan: docs/design/CB-CMCP-001-batch-implementation-plan.md §7 M1-C 1C-3
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

# Ensure the repo root is on ``sys.path`` so ``app.*`` imports resolve
# when the CLI is invoked directly (``python cli/audit_voice_consistency.py``).
# Mirrors the pattern in cli/embed_ceg.py (0B-4) — keep them in sync.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("cli.audit_voice_consistency")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Acceptance criterion in #4493 specifies a default sample of 50 artifacts.
DEFAULT_SAMPLE_SIZE = 50

# Personas the CMCP voice registry knows about (mirrors VoiceRegistry's
# documented set). Surfaced here so argparse can validate the ``--persona``
# flag before importing the registry.
SUPPORTED_PERSONAS: tuple[str, ...] = ("student", "teacher", "parent")

# Exit codes (mirror cli/embed_ceg.py for operator consistency).
EXIT_OK = 0
EXIT_GENERIC_ERROR = 1
EXIT_ARGPARSE_ERROR = 2


# ---------------------------------------------------------------------------
# Stub artifact dataclass + source
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class StubArtifact:
    """Minimal artifact shape the audit job needs.

    Frozen so the in-memory stub set can't be mutated mid-run by a typo.
    Real ``study_guides`` rows in M3 will expose the same three fields
    (``id``, ``persona``, ``voice_module_hash``) — the auditor only ever
    reads those — so the M3 swap is "replace the source callable" with
    no signature change.
    """

    id: str
    persona: str
    voice_module_hash: str


def _default_stub_artifacts() -> list[StubArtifact]:
    """Return the canned in-memory artifact set used until M3 persistence.

    Composition (deliberately mixed so a default run shows both consistent
    and drifted rows):

    - Several STUDENT artifacts whose ``voice_module_hash`` matches the
      currently-active ``arc_voice_v1`` module (consistent).
    - One STUDENT artifact stamped with a *known-old* hash that no longer
      matches any active module (drifted) — sentinel value
      ``"deadbeef" * 8`` so the drift example is visually obvious in the
      JSON output.
    - One TEACHER artifact whose hash matches ``professional_v1``
      (consistent on a teacher-persona run, ignored on a student run).
    - One PARENT artifact whose hash matches ``parent_coach_v1``
      (consistent on a parent-persona run, ignored otherwise).

    The stub is intentionally tiny — the real value of this CLI is the
    interface contract + report shape, not the dataset. Operators should
    never see this dataset in production once M3 ships.
    """
    # Lazy import: keeps argparse-error / --help path off the registry
    # (which touches the filesystem in module_hash). Mirrors the embed_ceg
    # pattern of pushing model imports past the CLI entry point.
    from app.services.cmcp.voice_registry import VoiceRegistry

    student_hash = VoiceRegistry.module_hash("arc_voice_v1")
    teacher_hash = VoiceRegistry.module_hash("professional_v1")
    parent_hash = VoiceRegistry.module_hash("parent_coach_v1")

    # 64-char sentinel that resembles a SHA-256 but matches no real module.
    # Chosen so a human reading the report can spot it instantly.
    drifted_sentinel = "deadbeef" * 8
    assert len(drifted_sentinel) == 64

    return [
        StubArtifact(id="stub-student-001", persona="student", voice_module_hash=student_hash),
        StubArtifact(id="stub-student-002", persona="student", voice_module_hash=student_hash),
        StubArtifact(id="stub-student-003", persona="student", voice_module_hash=student_hash),
        StubArtifact(id="stub-student-004", persona="student", voice_module_hash=student_hash),
        # Drifted: stamped against a voice version that's no longer active.
        StubArtifact(
            id="stub-student-drift-001",
            persona="student",
            voice_module_hash=drifted_sentinel,
        ),
        StubArtifact(id="stub-teacher-001", persona="teacher", voice_module_hash=teacher_hash),
        StubArtifact(id="stub-parent-001", persona="parent", voice_module_hash=parent_hash),
    ]


# Type alias for any callable that yields artifact-shaped objects with the
# three fields the auditor needs. Real M3 implementation will be a
# ``db_session.query(StudyGuide).filter(state.in_(APPROVED, APPROVED_VERIFIED))``
# wrapper that returns rows with ``.id``, ``.persona``, ``.voice_module_hash``.
ArtifactSource = Callable[[], Iterable[Any]]


# ---------------------------------------------------------------------------
# Audit core
# ---------------------------------------------------------------------------


def _filter_by_persona(artifacts: Iterable[Any], persona: str) -> list[Any]:
    """Return only the artifacts whose ``persona`` matches.

    Pulled out of :func:`run_audit` so tests can validate the persona
    filter independently of the sampling + comparison pipeline.
    """
    return [a for a in artifacts if getattr(a, "persona", None) == persona]


def _sample(
    artifacts: list[Any],
    sample_size: int,
    *,
    rng: random.Random | None = None,
) -> list[Any]:
    """Pick up to ``sample_size`` artifacts without replacement.

    If the population is smaller than ``sample_size`` we return everything
    (rather than padding with duplicates) — the audit is "what fraction of
    available artifacts have drifted", not "give me exactly N rows".

    ``rng`` is injectable so tests can pin the sample to be deterministic
    (``random.Random(0)``) without monkeypatching the global RNG.
    """
    if sample_size <= 0:
        return []
    if len(artifacts) <= sample_size:
        # ``random.sample`` raises ValueError when k > len(population), so
        # short-circuit here. Order doesn't matter — the report aggregates.
        return list(artifacts)
    # ``random.sample`` is without-replacement, which is the right semantic
    # for "audit N distinct artifacts".
    chooser = rng if rng is not None else random
    return chooser.sample(artifacts, sample_size)


def run_audit(
    *,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    persona: str = "student",
    artifact_source: ArtifactSource | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Run the audit and return the JSON-shaped report dict.

    The function returns the dict (instead of writing JSON to stdout) so
    callers — the CLI entry point AND the test suite — can decide what to
    do with it. The CLI does ``json.dumps(...)`` on the return value; the
    tests assert on the dict keys + counts directly.

    Args:
        sample_size: Maximum number of artifacts to audit (default 50).
        persona: Voice persona to audit against ("student" / "teacher" /
            "parent"). Determines both the artifacts kept (filtered by
            ``persona``) and the active module ID we compare hashes
            against.
        artifact_source: Callable returning the candidate artifact set.
            Defaults to :func:`_default_stub_artifacts`. M3 will pass a
            real ``study_guides`` query callable.
        rng: Optional ``random.Random`` for deterministic sampling in
            tests. Defaults to the shared ``random`` module.

    Returns:
        A dict shaped::

            {
                "persona": "student",
                "expected_module_id": "arc_voice_v1",
                "expected_module_hash": "<64-char sha256>",
                "sample_size_requested": 50,
                "sample_size_actual": 5,
                "consistent_count": 4,
                "drift_count": 1,
                "drift_examples": [
                    {
                        "artifact_id": "stub-student-drift-001",
                        "stored_hash": "deadbeef...",
                        "expected_hash": "<64-char sha256>",
                    }
                ],
            }

    Raises:
        ValueError: if ``persona`` is not in :data:`SUPPORTED_PERSONAS`.
    """
    if persona not in SUPPORTED_PERSONAS:
        raise ValueError(
            f"Unsupported persona {persona!r}; "
            f"expected one of {SUPPORTED_PERSONAS}"
        )

    # Lazy import — see :func:`_default_stub_artifacts` rationale.
    from app.services.cmcp.voice_registry import VoiceRegistry

    expected_module_id = VoiceRegistry.active_module_id(persona)
    expected_hash = VoiceRegistry.module_hash(expected_module_id)

    source = artifact_source if artifact_source is not None else _default_stub_artifacts
    raw_artifacts = list(source())
    persona_artifacts = _filter_by_persona(raw_artifacts, persona)
    sampled = _sample(persona_artifacts, sample_size, rng=rng)

    consistent_count = 0
    drift_examples: list[dict[str, str]] = []
    for artifact in sampled:
        stored_hash = getattr(artifact, "voice_module_hash", None)
        artifact_id = getattr(artifact, "id", "<unknown>")
        # Compare by string equality. We *don't* re-hash anything here —
        # the artifact's ``voice_module_hash`` is the source-of-truth
        # stamp that 1C-2 wrote at generation time. If it equals the
        # current active module's hash, the voice is consistent.
        if stored_hash == expected_hash:
            consistent_count += 1
        else:
            drift_examples.append(
                {
                    "artifact_id": str(artifact_id),
                    "stored_hash": str(stored_hash),
                    "expected_hash": expected_hash,
                }
            )

    return {
        "persona": persona,
        "expected_module_id": expected_module_id,
        "expected_module_hash": expected_hash,
        "sample_size_requested": sample_size,
        "sample_size_actual": len(sampled),
        "consistent_count": consistent_count,
        "drift_count": len(drift_examples),
        "drift_examples": drift_examples,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_voice_consistency",
        description=(
            "Audit student-facing CMCP artifacts for voice-module drift "
            "(CB-CMCP-001 M1-C 1C-3 / #4493). Outputs a JSON report on stdout."
        ),
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
        help=f"Number of artifacts to sample (default: {DEFAULT_SAMPLE_SIZE}).",
    )
    parser.add_argument(
        "--persona",
        choices=SUPPORTED_PERSONAS,
        default="student",
        help="Voice persona to audit (default: student).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the integer exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.sample < 0:
        # argparse type=int already rejects non-integers; we just guard
        # against negatives so the JSON report never lies about a "sampled"
        # negative count.
        print(
            json.dumps({"error": "--sample must be non-negative"}),
            file=sys.stderr,
        )
        return EXIT_GENERIC_ERROR

    try:
        report = run_audit(sample_size=args.sample, persona=args.persona)
    except Exception as exc:  # noqa: BLE001 — surface any failure to the operator
        logger.exception("Voice consistency audit failed")
        print(
            json.dumps({"error": f"{type(exc).__name__}: {exc}"}),
            file=sys.stderr,
        )
        return EXIT_GENERIC_ERROR

    print(json.dumps(report, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover — exercised via test_main
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Re-exports for tests
# ---------------------------------------------------------------------------

# Keep these symbols importable so the test module can validate the
# stub-source shape, the persona filter, and the sample helper directly
# (rather than only end-to-end via ``run_audit``). The leading underscore
# is preserved to signal "internal — but stable enough for test use".
__all__ = [
    "ArtifactSource",
    "DEFAULT_SAMPLE_SIZE",
    "EXIT_GENERIC_ERROR",
    "EXIT_OK",
    "StubArtifact",
    "SUPPORTED_PERSONAS",
    "_default_stub_artifacts",
    "_filter_by_persona",
    "_sample",
    "main",
    "run_audit",
]


# ``hashlib`` import is required indirectly via the stub's documented hash
# format guarantees. Kept explicit so editors / linters don't strip it if
# the stub is later updated to compute a hash inline.
_ = hashlib
