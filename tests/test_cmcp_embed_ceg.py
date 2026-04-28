"""Unit tests for cli/embed_ceg.py — the CB-CMCP-001 0B-4 backfill CLI.

Per acceptance criteria:
- Happy path: embed N rows
- Idempotent: re-running skips already-embedded rows
- Dry-run: no API calls, no writes
- Rate-limit honoured (mock verifies call timing >= min interval)
- Error handling for malformed expectation_text (str/empty)
- Scope filters work (--grade --subject)

OpenAI API is fully mocked at the single ``_create_embedding`` seam — no
real API calls happen during testing.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure repo root is importable so `cli.embed_ceg` resolves regardless of
# how pytest is invoked.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cli import embed_ceg as ec  # noqa: E402


# ---------------------------------------------------------------------------
# Per-test CEG cleanup
# ---------------------------------------------------------------------------
#
# The conftest fixture is session-scoped, so committed CEG rows (subjects,
# strands, versions, expectations) leak across tests in this file. Each
# test below seeds its own subject/strand/version + a small set of rows
# and asserts on counts — without an explicit cleanup, later tests see
# rows from earlier tests in the same run and the count assertions break.
#
# This autouse fixture wipes the four CEG tables after each test in this
# module so every test starts with empty CEG state.


@pytest.fixture(autouse=True)
def _wipe_ceg_tables(db_session):
    # Reset the module-level OpenAI client cache so it never leaks state
    # between tests. Tests mock ``_create_embedding`` directly (the cache
    # is only touched by the un-mocked path), but resetting is cheap
    # defence-in-depth.
    ec._async_openai_client = None
    yield
    ec._async_openai_client = None
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
    )
    # Order matters: expectations FK -> strand/subject/version; strand FK
    # -> subject; version FK -> subject. Delete leaves first.
    db_session.query(CEGExpectation).delete()
    db_session.query(CEGStrand).delete()
    db_session.query(CurriculumVersion).delete()
    db_session.query(CEGSubject).delete()
    db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_subject_strand_version(db_session, *, subject_code="MATH", grade=7):
    """Create a subject + strand + curriculum version triple. Returns the trio."""
    from app.models.curriculum import CEGStrand, CEGSubject, CurriculumVersion

    subject = CEGSubject(code=subject_code, name=f"{subject_code} subject")
    db_session.add(subject)
    db_session.flush()

    strand = CEGStrand(subject_id=subject.id, code="B", name="Number Sense")
    version = CurriculumVersion(
        subject_id=subject.id,
        grade=grade,
        version="2020-rev1",
        change_severity=None,
        notes="initial seed",
    )
    db_session.add_all([strand, version])
    db_session.flush()
    return subject, strand, version


def _make_expectation(
    db_session,
    *,
    subject,
    strand,
    version,
    grade=7,
    ministry_code="B2.1",
    description="Demonstrate fluency with multi-digit operations.",
    embedding=None,
):
    """Insert a CEGExpectation row and return it."""
    from app.models.curriculum import CEGExpectation, EXPECTATION_TYPE_SPECIFIC

    row = CEGExpectation(
        ministry_code=ministry_code,
        cb_code=f"CB-G{grade}-{subject.code}-{ministry_code}",
        subject_id=subject.id,
        strand_id=strand.id,
        grade=grade,
        expectation_type=EXPECTATION_TYPE_SPECIFIC,
        description=description,
        curriculum_version_id=version.id,
        embedding=embedding,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _fake_vector(seed: int = 0) -> list[float]:
    """Deterministic 1536-dim vector for tests."""
    return [float((seed + i) % 100) / 100.0 for i in range(ec.EMBEDDING_DIM)]


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestArgValidation:
    def test_grade_out_of_range_raises(self):
        ns = ec.build_parser().parse_args(["--grade", "0"])
        with pytest.raises(ValueError, match="--grade"):
            ec._validate_args(ns)

    def test_grade_above_12_raises(self):
        ns = ec.build_parser().parse_args(["--grade", "13"])
        with pytest.raises(ValueError, match="--grade"):
            ec._validate_args(ns)

    def test_negative_limit_raises(self):
        ns = ec.build_parser().parse_args(["--limit", "-1"])
        with pytest.raises(ValueError, match="--limit"):
            ec._validate_args(ns)

    def test_zero_limit_raises(self):
        ns = ec.build_parser().parse_args(["--limit", "0"])
        with pytest.raises(ValueError, match="--limit"):
            ec._validate_args(ns)

    def test_negative_interval_raises(self):
        ns = ec.build_parser().parse_args(["--min-interval-ms", "-5"])
        with pytest.raises(ValueError, match="--min-interval-ms"):
            ec._validate_args(ns)

    def test_zero_batch_size_raises(self):
        ns = ec.build_parser().parse_args(["--batch-size", "0"])
        with pytest.raises(ValueError, match="--batch-size"):
            ec._validate_args(ns)

    def test_negative_batch_size_raises(self):
        ns = ec.build_parser().parse_args(["--batch-size", "-3"])
        with pytest.raises(ValueError, match="--batch-size"):
            ec._validate_args(ns)

    def test_valid_args_pass(self):
        ns = ec.build_parser().parse_args(
            ["--grade", "7", "--subject", "MATH", "--limit", "5", "--batch-size", "10"]
        )
        ec._validate_args(ns)  # no raise


# ---------------------------------------------------------------------------
# Embedding helper — input validation
# ---------------------------------------------------------------------------


class TestCreateEmbeddingInputValidation:
    def test_empty_string_raises_malformed(self):
        with pytest.raises(ec.MalformedExpectationError):
            asyncio.run(ec._create_embedding(""))

    def test_whitespace_string_raises_malformed(self):
        with pytest.raises(ec.MalformedExpectationError):
            asyncio.run(ec._create_embedding("   \n\t  "))

    def test_non_string_raises_malformed(self):
        with pytest.raises(ec.MalformedExpectationError):
            asyncio.run(ec._create_embedding(None))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


class TestEmbedWithRetry:
    def test_succeeds_on_first_attempt(self):
        fake = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake):
            result = asyncio.run(ec._embed_with_retry("hello"))
        assert len(result) == ec.EMBEDDING_DIM
        assert fake.await_count == 1

    def test_retries_on_transient_error_then_succeeds(self):
        fake = AsyncMock(
            side_effect=[
                RuntimeError("transient 1"),
                RuntimeError("transient 2"),
                _fake_vector(0),
            ]
        )
        with patch.object(ec, "_create_embedding", fake):
            with patch("cli.embed_ceg.asyncio.sleep", new=AsyncMock()):
                result = asyncio.run(ec._embed_with_retry("hello"))
        assert len(result) == ec.EMBEDDING_DIM
        assert fake.await_count == 3

    def test_raises_embedding_api_error_after_max_retries(self):
        fake = AsyncMock(side_effect=RuntimeError("persistent"))
        with patch.object(ec, "_create_embedding", fake):
            with patch("cli.embed_ceg.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(ec.EmbeddingAPIError):
                    asyncio.run(ec._embed_with_retry("hello"))
        assert fake.await_count == ec.MAX_API_RETRIES

    def test_malformed_error_not_retried(self):
        fake = AsyncMock(side_effect=ec.MalformedExpectationError("bad text"))
        with patch.object(ec, "_create_embedding", fake):
            with pytest.raises(ec.MalformedExpectationError):
                asyncio.run(ec._embed_with_retry("hello"))
        assert fake.await_count == 1


# ---------------------------------------------------------------------------
# Persistence helper — vector length guard
# ---------------------------------------------------------------------------


class TestPersistEmbedding:
    def test_wrong_length_vector_rejected(self):
        class _Row:
            embedding = None

        row = _Row()
        with pytest.raises(ec.EmbeddingAPIError, match="length"):
            ec._persist_embedding(row, [0.0, 0.1, 0.2])

    def test_correct_length_vector_assigned(self):
        class _Row:
            embedding = None

        row = _Row()
        vec = _fake_vector(7)
        ec._persist_embedding(row, vec)
        assert row.embedding == vec


# ---------------------------------------------------------------------------
# Backfill — DB-backed integration with mocked OpenAI
# ---------------------------------------------------------------------------


class TestBackfillHappyPath:
    def test_embeds_all_pending_rows(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        rows = [
            _make_expectation(
                db_session,
                subject=subject,
                strand=strand,
                version=version,
                ministry_code=f"B2.{i}",
                description=f"Expectation number {i}.",
            )
            for i in range(3)
        ]
        db_session.commit()
        row_ids = [r.id for r in rows]

        fake_create = AsyncMock(side_effect=lambda text: _fake_vector(hash(text) % 1000))
        with patch.object(ec, "_create_embedding", fake_create):
            stats = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject=None,
                    limit=None,
                    dry_run=False,
                    min_interval_s=0.0,
                )
            )

        assert stats == {
            "found": 3,
            "embedded": 3,
            "skipped_malformed": 0,
            "failed": 0,
        }
        assert fake_create.await_count == 3

        # All rows now have a populated embedding.
        from app.models.curriculum import CEGExpectation

        for row_id in row_ids:
            persisted = (
                db_session.query(CEGExpectation).filter_by(id=row_id).one()
            )
            assert persisted.embedding is not None
            assert len(persisted.embedding) == ec.EMBEDDING_DIM


class TestBackfillBatchedCommit:
    """Verify that ``--batch-size`` controls how often we commit."""

    def test_commits_in_batches_then_flushes_trailing(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        for i in range(5):
            _make_expectation(
                db_session,
                subject=subject,
                strand=strand,
                version=version,
                ministry_code=f"B2.{i}",
                description=f"Expectation {i}.",
            )
        db_session.commit()

        commit_calls = []
        original_commit = db_session.commit

        def _spy_commit():
            commit_calls.append(len(commit_calls))
            return original_commit()

        fake_create = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake_create):
            with patch.object(db_session, "commit", side_effect=_spy_commit):
                stats = asyncio.run(
                    ec.backfill_embeddings(
                        db_session,
                        grade=None,
                        subject=None,
                        limit=None,
                        dry_run=False,
                        min_interval_s=0.0,
                        batch_size=2,  # 2 + 2 + 1-trailing = 3 commits
                    )
                )

        assert stats["embedded"] == 5
        # batch_size=2 with 5 successful embeddings: rows 1,2 -> commit;
        # rows 3,4 -> commit; row 5 -> trailing flush. So 3 commits.
        assert len(commit_calls) == 3, (
            f"expected 3 commits with batch_size=2 over 5 rows, got {len(commit_calls)}"
        )

    def test_default_batch_size_emits_single_trailing_commit_for_small_run(
        self, db_session
    ):
        # 3 rows + default batch_size 50 -> single trailing flush.
        subject, strand, version = _seed_subject_strand_version(db_session)
        for i in range(3):
            _make_expectation(
                db_session,
                subject=subject,
                strand=strand,
                version=version,
                ministry_code=f"B2.{i}",
                description=f"Expectation {i}.",
            )
        db_session.commit()

        commit_calls = []
        original_commit = db_session.commit

        def _spy_commit():
            commit_calls.append(len(commit_calls))
            return original_commit()

        fake_create = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake_create):
            with patch.object(db_session, "commit", side_effect=_spy_commit):
                stats = asyncio.run(
                    ec.backfill_embeddings(
                        db_session,
                        grade=None,
                        subject=None,
                        limit=None,
                        dry_run=False,
                        min_interval_s=0.0,
                        # batch_size defaults to 50 — 3 rows fit in one batch
                    )
                )
        assert stats["embedded"] == 3
        assert len(commit_calls) == 1


class TestBackfillIdempotent:
    def test_re_running_skips_already_embedded_rows(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        # Pre-seed one with an existing embedding, one without.
        already = _make_expectation(
            db_session,
            subject=subject,
            strand=strand,
            version=version,
            ministry_code="B2.1",
            description="Already embedded.",
            embedding=_fake_vector(99),
        )
        pending = _make_expectation(
            db_session,
            subject=subject,
            strand=strand,
            version=version,
            ministry_code="B2.2",
            description="Needs embedding.",
            embedding=None,
        )
        db_session.commit()

        already_id = already.id
        pending_id = pending.id
        already_vec_before = list(already.embedding)

        fake_create = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake_create):
            stats = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject=None,
                    limit=None,
                    dry_run=False,
                    min_interval_s=0.0,
                )
            )

        assert stats["found"] == 1
        assert stats["embedded"] == 1
        # Only the pending row triggered an API call.
        assert fake_create.await_count == 1

        # Already-embedded row's vector is untouched.
        from app.models.curriculum import CEGExpectation

        already_after = (
            db_session.query(CEGExpectation).filter_by(id=already_id).one()
        )
        assert already_after.embedding == already_vec_before

        pending_after = (
            db_session.query(CEGExpectation).filter_by(id=pending_id).one()
        )
        assert pending_after.embedding is not None

        # Re-run: nothing pending now.
        fake_create.reset_mock()
        with patch.object(ec, "_create_embedding", fake_create):
            stats2 = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject=None,
                    limit=None,
                    dry_run=False,
                    min_interval_s=0.0,
                )
            )
        assert stats2 == {
            "found": 0,
            "embedded": 0,
            "skipped_malformed": 0,
            "failed": 0,
        }
        assert fake_create.await_count == 0


class TestBackfillDryRun:
    def test_dry_run_makes_no_api_calls_and_no_writes(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        rows = [
            _make_expectation(
                db_session,
                subject=subject,
                strand=strand,
                version=version,
                ministry_code=f"B2.{i}",
                description=f"Expectation {i}.",
            )
            for i in range(2)
        ]
        db_session.commit()
        row_ids = [r.id for r in rows]

        fake_create = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake_create):
            stats = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject=None,
                    limit=None,
                    dry_run=True,
                    min_interval_s=0.0,
                )
            )

        assert stats == {
            "found": 2,
            "embedded": 0,
            "skipped_malformed": 0,
            "failed": 0,
        }
        # No API calls in dry-run.
        assert fake_create.await_count == 0

        # No writes.
        from app.models.curriculum import CEGExpectation

        for row_id in row_ids:
            persisted = (
                db_session.query(CEGExpectation).filter_by(id=row_id).one()
            )
            assert persisted.embedding is None


class TestBackfillRateLimit:
    def test_min_interval_honoured_between_calls(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        for i in range(3):
            _make_expectation(
                db_session,
                subject=subject,
                strand=strand,
                version=version,
                ministry_code=f"B2.{i}",
                description=f"Expectation {i}.",
            )
        db_session.commit()

        call_timestamps: list[float] = []

        async def _record_time(text: str) -> list[float]:
            call_timestamps.append(time.monotonic())
            return _fake_vector(0)

        with patch.object(ec, "_create_embedding", side_effect=_record_time):
            min_interval_s = 0.05  # 50ms — keeps the test fast but observable
            asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject=None,
                    limit=None,
                    dry_run=False,
                    min_interval_s=min_interval_s,
                )
            )

        assert len(call_timestamps) == 3
        # Each interval (call N -> call N+1) must be >= min_interval_s
        # (allow a small floating-point slack: -2ms).
        slack = 0.002
        for i in range(1, len(call_timestamps)):
            elapsed = call_timestamps[i] - call_timestamps[i - 1]
            assert elapsed >= min_interval_s - slack, (
                f"Call {i} fired {elapsed:.4f}s after previous, "
                f"expected >= {min_interval_s}s"
            )


class TestBackfillMalformedText:
    def test_malformed_row_skipped_others_embedded(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        good = _make_expectation(
            db_session,
            subject=subject,
            strand=strand,
            version=version,
            ministry_code="B2.1",
            description="Good description.",
        )
        # Force-bypass the model's NOT NULL constraint by patching after insert.
        bad = _make_expectation(
            db_session,
            subject=subject,
            strand=strand,
            version=version,
            ministry_code="B2.2",
            description="placeholder",
        )
        db_session.commit()

        # Make `_create_embedding` raise MalformedExpectationError for one
        # specific text — simulates a bad row escaping description-text checks.
        async def _fake(text: str) -> list[float]:
            if "placeholder" in text:
                raise ec.MalformedExpectationError("simulated bad text")
            return _fake_vector(0)

        with patch.object(ec, "_create_embedding", side_effect=_fake):
            stats = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject=None,
                    limit=None,
                    dry_run=False,
                    min_interval_s=0.0,
                )
            )

        assert stats["found"] == 2
        assert stats["embedded"] == 1
        assert stats["skipped_malformed"] == 1

        from app.models.curriculum import CEGExpectation

        good_after = (
            db_session.query(CEGExpectation).filter_by(id=good.id).one()
        )
        bad_after = (
            db_session.query(CEGExpectation).filter_by(id=bad.id).one()
        )
        assert good_after.embedding is not None
        assert bad_after.embedding is None


class TestBackfillScopeFilters:
    def test_grade_filter(self, db_session):
        subject, strand, version_g7 = _seed_subject_strand_version(
            db_session, subject_code="MATH", grade=7
        )

        # Add a Grade-5 version + row for the same subject.
        from app.models.curriculum import CurriculumVersion

        version_g5 = CurriculumVersion(
            subject_id=subject.id,
            grade=5,
            version="2020-rev1",
            change_severity=None,
            notes="grade 5 seed",
        )
        db_session.add(version_g5)
        db_session.flush()

        g7_row = _make_expectation(
            db_session,
            subject=subject,
            strand=strand,
            version=version_g7,
            grade=7,
            ministry_code="B2.1",
            description="Grade 7 expectation.",
        )
        g5_row = _make_expectation(
            db_session,
            subject=subject,
            strand=strand,
            version=version_g5,
            grade=5,
            ministry_code="B2.1",  # ok — different version, unique constraint is per version
            description="Grade 5 expectation.",
        )
        db_session.commit()

        fake_create = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake_create):
            stats = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=7,
                    subject=None,
                    limit=None,
                    dry_run=False,
                    min_interval_s=0.0,
                )
            )

        assert stats["found"] == 1
        assert stats["embedded"] == 1
        # Only the grade-7 row was embedded.
        from app.models.curriculum import CEGExpectation

        assert (
            db_session.query(CEGExpectation).filter_by(id=g7_row.id).one().embedding
            is not None
        )
        assert (
            db_session.query(CEGExpectation).filter_by(id=g5_row.id).one().embedding
            is None
        )

    def test_subject_filter(self, db_session):
        from app.models.curriculum import (
            CEGStrand,
            CEGSubject,
            CurriculumVersion,
        )

        # MATH subject + row.
        math = CEGSubject(code="MATH", name="Math")
        # LANG subject + row.
        lang = CEGSubject(code="LANG", name="Language")
        db_session.add_all([math, lang])
        db_session.flush()

        math_strand = CEGStrand(subject_id=math.id, code="B", name="Number Sense")
        lang_strand = CEGStrand(subject_id=lang.id, code="A", name="Reading")
        math_version = CurriculumVersion(
            subject_id=math.id, grade=7, version="2020", change_severity=None
        )
        lang_version = CurriculumVersion(
            subject_id=lang.id, grade=7, version="2020", change_severity=None
        )
        db_session.add_all([math_strand, lang_strand, math_version, lang_version])
        db_session.flush()

        math_row = _make_expectation(
            db_session,
            subject=math,
            strand=math_strand,
            version=math_version,
            ministry_code="B2.1",
            description="Math expectation.",
        )
        lang_row = _make_expectation(
            db_session,
            subject=lang,
            strand=lang_strand,
            version=lang_version,
            ministry_code="A1.1",
            description="Language expectation.",
        )
        db_session.commit()

        fake_create = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake_create):
            stats = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject="MATH",
                    limit=None,
                    dry_run=False,
                    min_interval_s=0.0,
                )
            )

        assert stats["found"] == 1
        assert stats["embedded"] == 1

        from app.models.curriculum import CEGExpectation

        assert (
            db_session.query(CEGExpectation).filter_by(id=math_row.id).one().embedding
            is not None
        )
        assert (
            db_session.query(CEGExpectation).filter_by(id=lang_row.id).one().embedding
            is None
        )

    def test_limit_caps_rows_processed(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        for i in range(5):
            _make_expectation(
                db_session,
                subject=subject,
                strand=strand,
                version=version,
                ministry_code=f"B2.{i}",
                description=f"Expectation {i}.",
            )
        db_session.commit()

        fake_create = AsyncMock(return_value=_fake_vector(0))
        with patch.object(ec, "_create_embedding", fake_create):
            stats = asyncio.run(
                ec.backfill_embeddings(
                    db_session,
                    grade=None,
                    subject=None,
                    limit=2,
                    dry_run=False,
                    min_interval_s=0.0,
                )
            )
        assert stats["found"] == 2
        assert stats["embedded"] == 2
        assert fake_create.await_count == 2


class TestBackfillAPIErrorPropagates:
    def test_persistent_api_failure_raises_embedding_api_error(self, db_session):
        subject, strand, version = _seed_subject_strand_version(db_session)
        _make_expectation(
            db_session,
            subject=subject,
            strand=strand,
            version=version,
            ministry_code="B2.1",
            description="Will fail.",
        )
        db_session.commit()

        fake_create = AsyncMock(side_effect=RuntimeError("OpenAI down"))
        with patch.object(ec, "_create_embedding", fake_create):
            with patch("cli.embed_ceg.asyncio.sleep", new=AsyncMock()):
                with pytest.raises(ec.EmbeddingAPIError):
                    asyncio.run(
                        ec.backfill_embeddings(
                            db_session,
                            grade=None,
                            subject=None,
                            limit=None,
                            dry_run=False,
                            min_interval_s=0.0,
                        )
                    )
