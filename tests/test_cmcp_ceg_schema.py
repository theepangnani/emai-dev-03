"""
CB-CMCP-001 M0-A 0A-1 — CEG schema round-trip tests.

Covers the four core tables created by ``app/models/curriculum.py``:

- Round-trip insert/query for ``CEGSubject``, ``CEGStrand``,
  ``CEGExpectation``, ``CurriculumVersion`` on SQLite (always run).
- Round-trip insert/query gated by PG availability (skipped when the
  test DB is SQLite — matches the cross-dialect pattern used by
  ``test_demo_migrations_idempotent.py``).
- ``change_severity`` accepts both locked values (``wording_only`` and
  ``scope_substantive``) and rejects anything else via CHECK constraint.
- ``parent_oe_id`` self-FK works (SE references its OE).
- Embedding column accepts a ``list[float]`` on SQLite (JSON fallback).
- Index lookup by ``(grade, subject_id)`` returns expected rows.

The PG round-trip test is skipped automatically when conftest's session
fixture provisions a SQLite test DB. To exercise it, point the test run
at a Postgres DSN via the ``DATABASE_URL`` env var (the conftest reloads
``app.core.config`` to pick it up) — but keep the SQLite default for
local + CI runs since pgvector isn't required for the SQLite path.

Note: model imports happen inside test methods (not at module top) so
that conftest's session-fixture reload of ``app.db.database`` and
``app.models`` registers the curriculum classes on the *current*
``Base`` registry. This matches the pattern used by ``test_dci_models``.
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_postgres() -> bool:
    from app.core.config import settings

    return "sqlite" not in settings.database_url


def _seed_subject_strand_version(db_session, *, subject_code="MATH", grade=7):
    """Create a subject + strand + (initial) curriculum version triple.

    Returns (subject, strand, version).
    """
    from app.models.curriculum import CEGStrand, CEGSubject, CurriculumVersion

    subject = CEGSubject(code=subject_code, name=f"{subject_code} subject")
    db_session.add(subject)
    db_session.flush()

    strand = CEGStrand(subject_id=subject.id, code="B", name="Number Sense")
    version = CurriculumVersion(
        subject_id=subject.id,
        grade=grade,
        version="2020-rev1",
        change_severity=None,  # initial seed version — severity is null
        notes="initial seed",
    )
    db_session.add_all([strand, version])
    db_session.flush()
    return subject, strand, version


# ---------------------------------------------------------------------------
# SQLite round-trip (always runs)
# ---------------------------------------------------------------------------


class TestCEGSchemaSQLite:
    def test_round_trip_all_four_tables(self, db_session):
        from app.models.curriculum import (
            CEGExpectation,
            CEGStrand,
            CEGSubject,
            CurriculumVersion,
            EXPECTATION_TYPE_OVERALL,
        )

        subject, strand, version = _seed_subject_strand_version(db_session)

        # OE row
        oe = CEGExpectation(
            ministry_code="B2",
            cb_code="CB-G7-MATH-B2",
            subject_id=subject.id,
            strand_id=strand.id,
            grade=7,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="By the end of Grade 7, students will demonstrate ...",
            curriculum_version_id=version.id,
        )
        db_session.add(oe)
        db_session.commit()

        loaded_subject = (
            db_session.query(CEGSubject).filter_by(code="MATH").one()
        )
        assert loaded_subject.name == "MATH subject"

        loaded_strand = (
            db_session.query(CEGStrand)
            .filter_by(subject_id=loaded_subject.id, code="B")
            .one()
        )
        assert loaded_strand.name == "Number Sense"

        loaded_version = (
            db_session.query(CurriculumVersion)
            .filter_by(subject_id=loaded_subject.id, grade=7)
            .one()
        )
        assert loaded_version.version == "2020-rev1"

        loaded_oe = (
            db_session.query(CEGExpectation)
            .filter_by(ministry_code="B2", curriculum_version_id=version.id)
            .one()
        )
        assert loaded_oe.expectation_type == EXPECTATION_TYPE_OVERALL
        assert loaded_oe.parent_oe_id is None
        assert loaded_oe.active is True

    def test_change_severity_accepts_both_values(self, db_session):
        from app.models.curriculum import (
            CHANGE_SEVERITY_SCOPE_SUBSTANTIVE,
            CHANGE_SEVERITY_WORDING_ONLY,
            CurriculumVersion,
        )

        subject, _strand, _version = _seed_subject_strand_version(
            db_session, subject_code="LANG"
        )

        v_wording = CurriculumVersion(
            subject_id=subject.id,
            grade=4,
            version="2023-wording",
            change_severity=CHANGE_SEVERITY_WORDING_ONLY,
        )
        v_scope = CurriculumVersion(
            subject_id=subject.id,
            grade=4,
            version="2023-scope",
            change_severity=CHANGE_SEVERITY_SCOPE_SUBSTANTIVE,
        )
        db_session.add_all([v_wording, v_scope])
        db_session.commit()

        loaded = (
            db_session.query(CurriculumVersion)
            .filter_by(subject_id=subject.id, grade=4)
            .order_by(CurriculumVersion.version)
            .all()
        )
        assert [v.change_severity for v in loaded] == [
            CHANGE_SEVERITY_SCOPE_SUBSTANTIVE,
            CHANGE_SEVERITY_WORDING_ONLY,
        ]

    def test_change_severity_rejects_invalid_value(self, db_session):
        from app.models.curriculum import CurriculumVersion

        subject, _strand, _version = _seed_subject_strand_version(
            db_session, subject_code="SCI"
        )

        bad = CurriculumVersion(
            subject_id=subject.id,
            grade=5,
            version="2024-bad",
            change_severity="catastrophic",  # not in the locked enum
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_parent_oe_self_fk(self, db_session):
        from app.models.curriculum import (
            CEGExpectation,
            EXPECTATION_TYPE_OVERALL,
            EXPECTATION_TYPE_SPECIFIC,
        )

        subject, strand, version = _seed_subject_strand_version(
            db_session, subject_code="HIST"
        )

        oe = CEGExpectation(
            ministry_code="A1",
            subject_id=subject.id,
            strand_id=strand.id,
            grade=8,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="Overall expectation A1",
            curriculum_version_id=version.id,
        )
        db_session.add(oe)
        db_session.flush()

        se1 = CEGExpectation(
            ministry_code="A1.1",
            subject_id=subject.id,
            strand_id=strand.id,
            grade=8,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            parent_oe_id=oe.id,
            description="Specific expectation A1.1",
            curriculum_version_id=version.id,
        )
        se2 = CEGExpectation(
            ministry_code="A1.2",
            subject_id=subject.id,
            strand_id=strand.id,
            grade=8,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            parent_oe_id=oe.id,
            description="Specific expectation A1.2",
            curriculum_version_id=version.id,
        )
        db_session.add_all([se1, se2])
        db_session.commit()

        loaded_oe = (
            db_session.query(CEGExpectation)
            .filter_by(ministry_code="A1", curriculum_version_id=version.id)
            .one()
        )
        # Backref should expose both SEs.
        codes = sorted(s.ministry_code for s in loaded_oe.specific_expectations)
        assert codes == ["A1.1", "A1.2"]

        loaded_se = (
            db_session.query(CEGExpectation)
            .filter_by(ministry_code="A1.1", curriculum_version_id=version.id)
            .one()
        )
        assert loaded_se.parent_oe_id == loaded_oe.id
        assert loaded_se.parent_oe.ministry_code == "A1"

    def test_embedding_column_accepts_list_of_floats_on_sqlite(self, db_session):
        if _is_postgres():
            pytest.skip("Covered by the PG-gated round-trip test")

        from app.models.curriculum import (
            CEGExpectation,
            EXPECTATION_TYPE_OVERALL,
        )

        subject, strand, version = _seed_subject_strand_version(
            db_session, subject_code="GEO"
        )

        # Use a small list (the column is the JSON fallback on SQLite,
        # so dimensionality is not enforced — round-trip is what matters).
        sample_vec = [0.1, 0.2, -0.3, 0.4, 0.5]
        oe = CEGExpectation(
            ministry_code="C1",
            subject_id=subject.id,
            strand_id=strand.id,
            grade=6,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="C1 with embedding",
            curriculum_version_id=version.id,
            embedding=sample_vec,
        )
        db_session.add(oe)
        db_session.commit()

        loaded = (
            db_session.query(CEGExpectation)
            .filter_by(ministry_code="C1", curriculum_version_id=version.id)
            .one()
        )
        assert loaded.embedding == sample_vec

    def test_grade_subject_index_lookup(self, db_session):
        from app.models.curriculum import (
            CEGExpectation,
            EXPECTATION_TYPE_OVERALL,
        )

        subject, strand, version = _seed_subject_strand_version(
            db_session, subject_code="ART"
        )

        rows = [
            CEGExpectation(
                ministry_code=f"D{i}",
                subject_id=subject.id,
                strand_id=strand.id,
                grade=3,
                expectation_type=EXPECTATION_TYPE_OVERALL,
                description=f"D{i} description",
                curriculum_version_id=version.id,
            )
            for i in range(1, 4)
        ]
        # One row at a different grade — should be excluded by the lookup.
        rows.append(
            CEGExpectation(
                ministry_code="E1",
                subject_id=subject.id,
                strand_id=strand.id,
                grade=4,
                expectation_type=EXPECTATION_TYPE_OVERALL,
                description="E1 (different grade)",
                curriculum_version_id=version.id,
            )
        )
        db_session.add_all(rows)
        db_session.commit()

        results = (
            db_session.query(CEGExpectation)
            .filter_by(grade=3, subject_id=subject.id)
            .order_by(CEGExpectation.ministry_code)
            .all()
        )
        codes = [r.ministry_code for r in results]
        assert codes == ["D1", "D2", "D3"]


# ---------------------------------------------------------------------------
# PG round-trip (skipped when the test DB is SQLite)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _is_postgres(),
    reason="PG round-trip requires DATABASE_URL pointing at a Postgres DSN",
)
class TestCEGSchemaPostgres:
    def test_round_trip_with_pgvector_embedding(self, db_session):
        from app.models.curriculum import (
            CEGExpectation,
            EXPECTATION_TYPE_OVERALL,
        )

        subject, strand, version = _seed_subject_strand_version(
            db_session, subject_code="MATH-PG"
        )

        # On PG the column is vector(1536). Provide a 1536-d unit-ish vector.
        sample_vec = [0.0] * 1536
        sample_vec[0] = 1.0

        oe = CEGExpectation(
            ministry_code="B2",
            subject_id=subject.id,
            strand_id=strand.id,
            grade=7,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="B2 description",
            curriculum_version_id=version.id,
            embedding=sample_vec,
        )
        db_session.add(oe)
        db_session.commit()

        loaded = (
            db_session.query(CEGExpectation)
            .filter_by(ministry_code="B2", curriculum_version_id=version.id)
            .one()
        )
        # pgvector returns a numpy-like sequence; convert for comparison.
        assert list(loaded.embedding)[0] == pytest.approx(1.0)
        assert len(list(loaded.embedding)) == 1536
