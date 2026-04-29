"""CB-CMCP-001 M1-C 1C-3 — Voice consistency audit job tests (#4493).

Covers ``cli/audit_voice_consistency.py``:

- :func:`run_audit` returns a dict with the documented JSON shape
  (``consistent_count`` / ``drift_count`` / ``drift_examples`` etc.).
- The default stub artifact set produces at least one drift example
  (so a default CLI run shows non-trivial output to operators).
- An all-consistent artifact set produces ``drift_count == 0`` and an
  empty ``drift_examples`` list.
- An all-drifted artifact set lists every artifact in ``drift_examples``
  with the correct ``stored_hash`` / ``expected_hash`` pair.
- Persona filtering excludes artifacts whose persona doesn't match
  ``--persona``.
- Sampling is bounded by ``--sample`` and never exceeds population size.
- An unsupported persona raises ValueError (defence against typos in
  cron jobs that would otherwise audit against the wrong voice).
- ``main()`` writes JSON to stdout and exits 0 on a happy-path run.
- ``main()`` exits non-zero with an error blob on stderr if the audit
  raises (e.g., a missing voice module file).

No real Claude/OpenAI calls — the auditor is a pure file-read +
SHA-256 comparison, so this stripe never crosses an external API.

Issue: #4493
"""
from __future__ import annotations

import json
import random

import pytest

from cli import audit_voice_consistency as audit_cli
from cli.audit_voice_consistency import (
    DEFAULT_SAMPLE_SIZE,
    EXIT_GENERIC_ERROR,
    EXIT_OK,
    StubArtifact,
    SUPPORTED_PERSONAS,
    _default_stub_artifacts,
    _filter_by_persona,
    _sample,
    main,
    run_audit,
)
from app.services.cmcp.voice_registry import VoiceRegistry


# ---------------------------------------------------------------------------
# Helpers — local mocked artifact factories
# ---------------------------------------------------------------------------


def _matching_student_artifact(idx: int) -> StubArtifact:
    """Build a stub student artifact stamped with the active arc voice hash."""
    return StubArtifact(
        id=f"match-student-{idx:03d}",
        persona="student",
        voice_module_hash=VoiceRegistry.module_hash("arc_voice_v1"),
    )


def _drifted_student_artifact(idx: int) -> StubArtifact:
    """Build a stub student artifact stamped with a known-bad hash."""
    return StubArtifact(
        id=f"drift-student-{idx:03d}",
        persona="student",
        voice_module_hash=("cafef00d" * 8),  # 64-char SHA-256-shaped sentinel
    )


# ---------------------------------------------------------------------------
# Stub artifact source
# ---------------------------------------------------------------------------


def test_default_stub_artifacts_has_one_drifted_student() -> None:
    """The shipped stub deliberately seeds at least one drift case.

    Operators eyeballing a default CLI run should always see a non-empty
    ``drift_examples`` list — that's the single best signal that the
    audit is wired correctly. If a future commit accidentally aligns
    every stub's hash with the active module, the operator gets a
    silently-clean report and would mis-conclude "no drift in prod".
    """
    artifacts = _default_stub_artifacts()
    student_artifacts = [a for a in artifacts if a.persona == "student"]
    expected_hash = VoiceRegistry.module_hash("arc_voice_v1")
    drifted = [a for a in student_artifacts if a.voice_module_hash != expected_hash]
    assert drifted, (
        "Default stub set must include at least one drifted student artifact "
        "so the audit demo run shows a non-empty drift_examples list."
    )


def test_default_stub_artifacts_includes_all_three_personas() -> None:
    """Stub set must cover student/teacher/parent so every --persona run produces output."""
    personas = {a.persona for a in _default_stub_artifacts()}
    assert personas == set(SUPPORTED_PERSONAS), (
        f"Stub set personas {personas} must cover all supported personas {SUPPORTED_PERSONAS}"
    )


# ---------------------------------------------------------------------------
# Persona filter
# ---------------------------------------------------------------------------


def test_filter_by_persona_excludes_non_matching() -> None:
    """Artifacts whose persona doesn't match are dropped before sampling."""
    artifacts = [
        StubArtifact(id="a1", persona="student", voice_module_hash="x"),
        StubArtifact(id="a2", persona="teacher", voice_module_hash="x"),
        StubArtifact(id="a3", persona="student", voice_module_hash="y"),
        StubArtifact(id="a4", persona="parent", voice_module_hash="z"),
    ]
    filtered = _filter_by_persona(artifacts, "student")
    assert {a.id for a in filtered} == {"a1", "a3"}


def test_filter_by_persona_returns_empty_for_no_matches() -> None:
    """Filtering against a persona with no artifacts returns an empty list (not an error)."""
    artifacts = [
        StubArtifact(id="a1", persona="teacher", voice_module_hash="x"),
    ]
    assert _filter_by_persona(artifacts, "student") == []


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def test_sample_returns_full_population_when_sample_exceeds_size() -> None:
    """If population < sample_size, return everything (no padding)."""
    artifacts = [_matching_student_artifact(i) for i in range(3)]
    sampled = _sample(artifacts, sample_size=10)
    assert len(sampled) == 3


def test_sample_caps_at_sample_size() -> None:
    """Sampling never returns more than sample_size, even from a large population."""
    artifacts = [_matching_student_artifact(i) for i in range(100)]
    rng = random.Random(0)  # deterministic for this assertion
    sampled = _sample(artifacts, sample_size=10, rng=rng)
    assert len(sampled) == 10
    # All sampled IDs are unique — without-replacement sampling.
    assert len({a.id for a in sampled}) == 10


def test_sample_zero_returns_empty_list() -> None:
    """sample_size=0 short-circuits to empty (rather than raising on random.sample(k=0))."""
    artifacts = [_matching_student_artifact(i) for i in range(5)]
    assert _sample(artifacts, sample_size=0) == []


def test_sample_negative_returns_empty_list() -> None:
    """Negative sample_size is treated as 0, not as a Python negative-index quirk."""
    artifacts = [_matching_student_artifact(i) for i in range(5)]
    assert _sample(artifacts, sample_size=-3) == []


# ---------------------------------------------------------------------------
# run_audit — happy paths
# ---------------------------------------------------------------------------


def test_run_audit_all_consistent() -> None:
    """An artifact set whose hashes all match the active module reports zero drift."""
    artifacts = [_matching_student_artifact(i) for i in range(7)]
    report = run_audit(
        sample_size=50,
        persona="student",
        artifact_source=lambda: artifacts,
    )
    assert report["persona"] == "student"
    assert report["expected_module_id"] == "arc_voice_v1"
    assert report["expected_module_hash"] == VoiceRegistry.module_hash("arc_voice_v1")
    assert report["consistent_count"] == 7
    assert report["drift_count"] == 0
    assert report["drift_examples"] == []
    assert report["sample_size_requested"] == 50
    assert report["sample_size_actual"] == 7


def test_run_audit_all_drifted() -> None:
    """An artifact set with no matching hashes reports every artifact as drifted."""
    artifacts = [_drifted_student_artifact(i) for i in range(5)]
    report = run_audit(
        sample_size=50,
        persona="student",
        artifact_source=lambda: artifacts,
    )
    assert report["consistent_count"] == 0
    assert report["drift_count"] == 5
    assert len(report["drift_examples"]) == 5
    # Each drift example has the documented shape.
    for example in report["drift_examples"]:
        assert set(example.keys()) == {"artifact_id", "stored_hash", "expected_hash"}
        assert example["expected_hash"] == VoiceRegistry.module_hash("arc_voice_v1")
        assert example["stored_hash"] == ("cafef00d" * 8)
        assert example["artifact_id"].startswith("drift-student-")


def test_run_audit_mixed_consistent_and_drift() -> None:
    """A mixed artifact set splits cleanly into consistent + drift counts."""
    artifacts = [
        _matching_student_artifact(0),
        _matching_student_artifact(1),
        _drifted_student_artifact(0),
        _matching_student_artifact(2),
        _drifted_student_artifact(1),
    ]
    report = run_audit(
        sample_size=50,
        persona="student",
        artifact_source=lambda: artifacts,
    )
    assert report["consistent_count"] == 3
    assert report["drift_count"] == 2
    assert {ex["artifact_id"] for ex in report["drift_examples"]} == {
        "drift-student-000",
        "drift-student-001",
    }


def test_run_audit_filters_by_persona() -> None:
    """Artifacts from other personas are excluded — only the requested persona is audited."""
    artifacts = [
        _matching_student_artifact(0),
        _matching_student_artifact(1),
        # A teacher artifact shouldn't show up in a student-persona audit.
        StubArtifact(
            id="teacher-1",
            persona="teacher",
            voice_module_hash=VoiceRegistry.module_hash("professional_v1"),
        ),
        # A parent artifact shouldn't either.
        StubArtifact(
            id="parent-1",
            persona="parent",
            voice_module_hash=VoiceRegistry.module_hash("parent_coach_v1"),
        ),
    ]
    report = run_audit(
        sample_size=50,
        persona="student",
        artifact_source=lambda: artifacts,
    )
    # Only the 2 student artifacts were audited.
    assert report["sample_size_actual"] == 2
    assert report["consistent_count"] == 2
    assert report["drift_count"] == 0


def test_run_audit_caps_at_sample_size() -> None:
    """``--sample N`` never returns more than N rows, even when population is larger."""
    artifacts = [_matching_student_artifact(i) for i in range(100)]
    rng = random.Random(42)
    report = run_audit(
        sample_size=10,
        persona="student",
        artifact_source=lambda: artifacts,
        rng=rng,
    )
    assert report["sample_size_requested"] == 10
    assert report["sample_size_actual"] == 10
    # consistent + drift sums to actual sample size — no rows lost.
    assert report["consistent_count"] + report["drift_count"] == 10


def test_run_audit_default_sample_size_constant() -> None:
    """The default sample size is the documented 50 (matches issue #4493)."""
    assert DEFAULT_SAMPLE_SIZE == 50


def test_run_audit_persona_teacher() -> None:
    """A teacher-persona run compares against ``professional_v1``."""
    artifacts = [
        StubArtifact(
            id="t1",
            persona="teacher",
            voice_module_hash=VoiceRegistry.module_hash("professional_v1"),
        ),
        StubArtifact(
            id="t2",
            persona="teacher",
            voice_module_hash="0" * 64,  # drifted
        ),
    ]
    report = run_audit(
        sample_size=50,
        persona="teacher",
        artifact_source=lambda: artifacts,
    )
    assert report["persona"] == "teacher"
    assert report["expected_module_id"] == "professional_v1"
    assert report["consistent_count"] == 1
    assert report["drift_count"] == 1
    assert report["drift_examples"][0]["artifact_id"] == "t2"


def test_run_audit_persona_parent() -> None:
    """A parent-persona run compares against ``parent_coach_v1``."""
    artifacts = [
        StubArtifact(
            id="p1",
            persona="parent",
            voice_module_hash=VoiceRegistry.module_hash("parent_coach_v1"),
        ),
    ]
    report = run_audit(
        sample_size=50,
        persona="parent",
        artifact_source=lambda: artifacts,
    )
    assert report["persona"] == "parent"
    assert report["expected_module_id"] == "parent_coach_v1"
    assert report["consistent_count"] == 1
    assert report["drift_count"] == 0


def test_run_audit_default_source_produces_drift() -> None:
    """A default run (no injected source) shows the seeded drift example.

    Mutation-test guard: this test would also pass if the auditor never
    actually compared hashes (always classifying everything as drifted).
    The all-consistent / all-drifted tests above pin the comparison logic
    in both directions; this test specifically validates the demo run.
    """
    report = run_audit(sample_size=50, persona="student")
    assert report["drift_count"] >= 1
    assert any(
        ex["artifact_id"].startswith("stub-student-drift-")
        for ex in report["drift_examples"]
    )


# ---------------------------------------------------------------------------
# run_audit — error paths
# ---------------------------------------------------------------------------


def test_run_audit_unsupported_persona_raises() -> None:
    """Audit against an unknown persona fails fast (defence vs typoed cron job)."""
    with pytest.raises(ValueError, match="Unsupported persona"):
        run_audit(persona="admin", artifact_source=lambda: [])


# ---------------------------------------------------------------------------
# Output schema guard
# ---------------------------------------------------------------------------


def test_run_audit_report_has_documented_schema() -> None:
    """Report dict includes every key the docstring promises.

    Catches a future refactor that drops or renames a key (e.g.,
    ``drift_examples`` -> ``drifted``) — downstream operators depend on
    this exact shape for dashboards / alerting.
    """
    report = run_audit(
        sample_size=5,
        persona="student",
        artifact_source=lambda: [_matching_student_artifact(0)],
    )
    expected_keys = {
        "persona",
        "expected_module_id",
        "expected_module_hash",
        "sample_size_requested",
        "sample_size_actual",
        "consistent_count",
        "drift_count",
        "drift_examples",
    }
    assert set(report.keys()) == expected_keys


def test_run_audit_report_is_json_serialisable() -> None:
    """The report dict must round-trip through json.dumps (it's the CLI's output)."""
    report = run_audit(
        sample_size=5,
        persona="student",
        artifact_source=lambda: [
            _matching_student_artifact(0),
            _drifted_student_artifact(0),
        ],
    )
    # If a future change adds a non-serialisable value (e.g., a datetime
    # without isoformat()), this raises TypeError loudly.
    serialised = json.dumps(report)
    parsed = json.loads(serialised)
    assert parsed["consistent_count"] == 1
    assert parsed["drift_count"] == 1


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_main_writes_json_to_stdout(capsys, monkeypatch) -> None:
    """``main()`` prints the report JSON to stdout and exits 0."""
    # Pin the artifact source to a known set so the assertion is stable.
    artifacts = [_matching_student_artifact(0), _drifted_student_artifact(0)]
    monkeypatch.setattr(
        audit_cli, "_default_stub_artifacts", lambda: artifacts
    )

    code = main(["--sample", "10", "--persona", "student"])
    captured = capsys.readouterr()

    assert code == EXIT_OK
    payload = json.loads(captured.out)
    assert payload["persona"] == "student"
    assert payload["consistent_count"] == 1
    assert payload["drift_count"] == 1


def test_main_default_args(capsys, monkeypatch) -> None:
    """Calling ``main([])`` uses the documented defaults (sample=50, persona=student)."""
    artifacts = [_matching_student_artifact(i) for i in range(3)]
    monkeypatch.setattr(
        audit_cli, "_default_stub_artifacts", lambda: artifacts
    )

    code = main([])
    captured = capsys.readouterr()

    assert code == EXIT_OK
    payload = json.loads(captured.out)
    assert payload["sample_size_requested"] == DEFAULT_SAMPLE_SIZE
    assert payload["persona"] == "student"


def test_main_negative_sample_returns_error_exit_code(capsys) -> None:
    """``--sample -1`` exits non-zero with an error blob on stderr."""
    code = main(["--sample", "-1"])
    captured = capsys.readouterr()
    assert code == EXIT_GENERIC_ERROR
    err_payload = json.loads(captured.err)
    assert "error" in err_payload


def test_main_audit_failure_returns_error_exit_code(capsys, monkeypatch) -> None:
    """If the audit raises (e.g., a missing voice module), main() exits 1."""

    def boom() -> list[StubArtifact]:
        raise RuntimeError("simulated voice-module load failure")

    monkeypatch.setattr(audit_cli, "_default_stub_artifacts", boom)

    code = main(["--sample", "5", "--persona", "student"])
    captured = capsys.readouterr()

    assert code == EXIT_GENERIC_ERROR
    err_payload = json.loads(captured.err)
    assert "RuntimeError" in err_payload["error"]
    assert "simulated voice-module load failure" in err_payload["error"]


def test_main_rejects_invalid_persona(capsys) -> None:
    """argparse rejects ``--persona admin`` before run_audit is invoked."""
    # argparse calls sys.exit(2) on a parse error — wrap in pytest.raises.
    with pytest.raises(SystemExit) as excinfo:
        main(["--persona", "admin"])
    assert excinfo.value.code == 2  # argparse error code
