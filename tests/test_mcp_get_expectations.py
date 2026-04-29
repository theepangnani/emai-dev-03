"""CB-CMCP-001 M2-B 2B-1 (#4552) — ``get_expectations`` MCP tool tests.

Covers:

- Direct-handler happy path: PARENT receives the SE list for a
  ``(subject_code, grade)`` slice, ordered by ``(strand_code,
  ministry_code)``.
- Strand filter narrows the result.
- Unknown ``(subject_code, grade)`` combo returns ``{"expectations": []}``
  rather than 404 (catalog semantics — see handler module docstring).
- Missing / invalid ``subject_code`` (and similar mis-typed args)
  collapses to an empty list at the handler; the route surface itself
  rejects with 422 only when Pydantic body validation fails.
- Unauthenticated route call → 401.
- All four roles (PARENT, STUDENT, TEACHER, ADMIN) round-trip through
  the route and reach the handler — no role from the allowlist is
  silently dropped.
- Registry: ``TOOLS["get_expectations"].handler`` is the concrete
  function (no stub) and the role allowlist is exactly the documented
  set.

The handler-level tests use the real SQLite session from ``conftest.py``
+ a per-test seed fixture (unique subject codes + version slug) so the
session-scoped DB doesn't leak between tests in this file. Pure unit
tests on the registry don't need DB access at all.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Flag fixture — ``mcp.enabled`` ON for every route-level test in the module
# ---------------------------------------------------------------------------


@pytest.fixture()
def mcp_flag_on(db_session):
    """Force ``mcp.enabled`` ON for the test, OFF after."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "mcp.enabled")
        .first()
    )
    assert flag is not None, "mcp.enabled flag must be seeded"
    flag.enabled = True
    db_session.commit()
    yield flag
    db_session.refresh(flag)
    flag.enabled = False
    db_session.commit()


# ---------------------------------------------------------------------------
# User fixtures — one per role we exercise
# ---------------------------------------------------------------------------


def _make_user(db_session, role, *, email_prefix=None):
    from app.core.security import get_password_hash
    from app.models.user import User

    prefix = email_prefix or f"mcp_ge_{role.value.lower()}"
    user = User(
        email=f"{prefix}_{uuid4().hex[:8]}@test.com",
        full_name=f"GetExpectations Test {role.value}",
        role=role,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def parent_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.PARENT)


@pytest.fixture()
def student_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.STUDENT)


@pytest.fixture()
def teacher_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.TEACHER)


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import UserRole

    return _make_user(db_session, UserRole.ADMIN)


# ---------------------------------------------------------------------------
# CEG seed fixture — per-test unique subject + 4 SE rows + 1 OE row
# ---------------------------------------------------------------------------


@pytest.fixture()
def ceg_seed(db_session):
    """Seed a deterministic CEG slice for the tool to query.

    Layout:
    - 1 unique subject (random suffix to avoid collisions across tests
      under the session-scoped DB).
    - 2 strands: ``B`` (Number Sense), ``C`` (Algebra).
    - 1 OE row in strand B (must NOT show up in the SE-only response).
    - 2 SE rows in strand B + 1 SE row in strand C (all grade 9).
    - 1 SE row in a different grade (10) to verify grade-filter
      narrowing.

    Cleanup tears the slice down in FK order. The yielded dict carries
    the resolved codes + ids the tests assert against.
    """
    from app.models.curriculum import (
        EXPECTATION_TYPE_OVERALL,
        EXPECTATION_TYPE_SPECIFIC,
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
    )

    suffix = uuid4().hex[:6].upper()
    subject_code = f"M{suffix}"  # short — column is String(20)
    version_slug = f"test-{uuid4().hex[:6]}"

    subject = CEGSubject(code=subject_code, name="Mathematics")
    db_session.add(subject)
    db_session.flush()

    strand_b = CEGStrand(subject_id=subject.id, code="B", name="Number Sense")
    strand_c = CEGStrand(subject_id=subject.id, code="C", name="Algebra")
    db_session.add_all([strand_b, strand_c])
    db_session.flush()

    version = CurriculumVersion(
        subject_id=subject.id,
        grade=9,
        version=version_slug,
        change_severity=None,
        notes="get_expectations test seed",
    )
    db_session.add(version)
    db_session.flush()

    # Distinct version row for the grade-10 sibling so the unique
    # constraint on (subject_id, grade, version) still holds.
    version_g10 = CurriculumVersion(
        subject_id=subject.id,
        grade=10,
        version=version_slug,
        change_severity=None,
        notes="get_expectations test seed g10",
    )
    db_session.add(version_g10)
    db_session.flush()

    rows = [
        # OE — must NOT appear in the SE-only handler output.
        CEGExpectation(
            ministry_code="B1.0",
            cb_code=f"CB-G9-{subject_code}-B1-OE0",
            subject_id=subject.id,
            strand_id=strand_b.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_OVERALL,
            description="Overall Number Sense expectation",
            curriculum_version_id=version.id,
        ),
        # SE rows in strand B.
        CEGExpectation(
            ministry_code="B1.1",
            cb_code=f"CB-G9-{subject_code}-B1-SE1",
            subject_id=subject.id,
            strand_id=strand_b.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            description="Apply integer operations",
            curriculum_version_id=version.id,
        ),
        CEGExpectation(
            ministry_code="B1.2",
            cb_code=f"CB-G9-{subject_code}-B1-SE2",
            subject_id=subject.id,
            strand_id=strand_b.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            description="Compare rational numbers",
            curriculum_version_id=version.id,
        ),
        # SE row in strand C.
        CEGExpectation(
            ministry_code="C1.1",
            cb_code=f"CB-G9-{subject_code}-C1-SE1",
            subject_id=subject.id,
            strand_id=strand_c.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            description="Solve linear equations",
            curriculum_version_id=version.id,
        ),
        # SE row in a different grade.
        CEGExpectation(
            ministry_code="B2.1",
            cb_code=f"CB-G10-{subject_code}-B2-SE1",
            subject_id=subject.id,
            strand_id=strand_b.id,
            grade=10,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            description="Solve quadratic equations",
            curriculum_version_id=version_g10.id,
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()

    expectation_ids = [r.id for r in rows]
    strand_ids = [strand_b.id, strand_c.id]
    version_ids = [version.id, version_g10.id]
    subject_id = subject.id

    yield {
        "subject_code": subject_code,
        "subject_id": subject_id,
        "strand_b_code": "B",
        "strand_c_code": "C",
    }

    # Cleanup. FK chain order: expectations → versions → strands → subject.
    db_session.query(CEGExpectation).filter(
        CEGExpectation.id.in_(expectation_ids)
    ).delete(synchronize_session=False)
    db_session.query(CurriculumVersion).filter(
        CurriculumVersion.id.in_(version_ids)
    ).delete(synchronize_session=False)
    db_session.query(CEGStrand).filter(
        CEGStrand.id.in_(strand_ids)
    ).delete(synchronize_session=False)
    db_session.query(CEGSubject).filter(
        CEGSubject.id == subject_id
    ).delete(synchronize_session=False)
    db_session.commit()


# ---------------------------------------------------------------------------
# Direct-handler tests — exercise the SE filter without the route
# ---------------------------------------------------------------------------


class TestGetExpectationsHandler:
    """Direct handler invocation — focuses on filter semantics."""

    def test_parent_happy_path_returns_filtered_ses(
        self, db_session, parent_user, ceg_seed
    ):
        """Subject + grade filter returns SE rows only, ordered by strand."""
        from app.mcp.tools.get_expectations import get_expectations_handler

        result = get_expectations_handler(
            {"subject_code": ceg_seed["subject_code"], "grade": 9},
            parent_user,
            db_session,
        )
        ses = result["expectations"]
        # 3 SE rows seeded for this subject at grade 9 (1 in C, 2 in B).
        assert len(ses) == 3
        # OE row must not leak into the SE-only response.
        codes = [e["se_code"] for e in ses]
        assert "B1.0" not in codes
        # Ordered by (strand_code ASC, ministry_code ASC).
        assert codes == ["B1.1", "B1.2", "C1.1"]
        # Response shape carries every documented field.
        first = ses[0]
        assert set(first.keys()) == {
            "se_code",
            "expectation_text",
            "topic",
            "strand_code",
            "strand_name",
        }
        assert first["se_code"] == "B1.1"
        assert first["expectation_text"] == "Apply integer operations"
        assert first["strand_code"] == "B"
        assert first["strand_name"] == "Number Sense"

    def test_strand_filter_narrows_result(
        self, db_session, parent_user, ceg_seed
    ):
        """Adding ``strand_code`` filters down to the matching strand only."""
        from app.mcp.tools.get_expectations import get_expectations_handler

        result = get_expectations_handler(
            {
                "subject_code": ceg_seed["subject_code"],
                "grade": 9,
                "strand_code": "C",
            },
            parent_user,
            db_session,
        )
        ses = result["expectations"]
        assert len(ses) == 1
        assert ses[0]["se_code"] == "C1.1"
        assert ses[0]["strand_code"] == "C"

    def test_unknown_subject_returns_empty_list(
        self, db_session, parent_user, ceg_seed
    ):
        """Catalog semantics — unknown subject is an empty list, not 404."""
        from app.mcp.tools.get_expectations import get_expectations_handler

        result = get_expectations_handler(
            {"subject_code": "DOES_NOT_EXIST", "grade": 9},
            parent_user,
            db_session,
        )
        assert result == {"expectations": []}

    def test_unknown_grade_returns_empty_list(
        self, db_session, parent_user, ceg_seed
    ):
        """Subject exists but no rows at the requested grade → empty list."""
        from app.mcp.tools.get_expectations import get_expectations_handler

        result = get_expectations_handler(
            # Grade 12 has no seeded rows in this fixture.
            {"subject_code": ceg_seed["subject_code"], "grade": 12},
            parent_user,
            db_session,
        )
        assert result == {"expectations": []}

    def test_grade_10_isolated_from_grade_9(
        self, db_session, parent_user, ceg_seed
    ):
        """Grade filter is exact — grade 10 returns only the one G10 SE."""
        from app.mcp.tools.get_expectations import get_expectations_handler

        result = get_expectations_handler(
            {"subject_code": ceg_seed["subject_code"], "grade": 10},
            parent_user,
            db_session,
        )
        ses = result["expectations"]
        assert len(ses) == 1
        assert ses[0]["se_code"] == "B2.1"

    def test_missing_subject_code_returns_empty(
        self, db_session, parent_user
    ):
        """Direct-call with missing arg degrades to empty list, not crash.

        The route layer's Pydantic + JSON Schema validation is the
        primary defence; the handler still tolerates direct misuse from
        another stripe so it never bubbles up as a 500.
        """
        from app.mcp.tools.get_expectations import get_expectations_handler

        result = get_expectations_handler({}, parent_user, db_session)
        assert result == {"expectations": []}

    def test_bool_grade_rejected(
        self, db_session, parent_user, ceg_seed
    ):
        """``True``/``False`` aren't accepted as a grade (bool is int).

        Without the explicit guard, ``True``/``False`` would coerce to
        grade-1/0 row lookups via ``isinstance(x, int)``.
        """
        from app.mcp.tools.get_expectations import get_expectations_handler

        result = get_expectations_handler(
            {"subject_code": ceg_seed["subject_code"], "grade": True},
            parent_user,
            db_session,
        )
        assert result == {"expectations": []}

    def test_pending_expectation_excluded(
        self, db_session, parent_user, ceg_seed
    ):
        """Rows with ``review_state != 'accepted'`` must never leak through."""
        from app.mcp.tools.get_expectations import get_expectations_handler
        from app.models.curriculum import (
            EXPECTATION_TYPE_SPECIFIC,
            CEGExpectation,
            CEGStrand,
            CurriculumVersion,
        )

        # Find the strand B id for the seed subject + an existing version.
        strand_b = (
            db_session.query(CEGStrand)
            .filter(
                CEGStrand.subject_id == ceg_seed["subject_id"],
                CEGStrand.code == "B",
            )
            .first()
        )
        version = (
            db_session.query(CurriculumVersion)
            .filter(
                CurriculumVersion.subject_id == ceg_seed["subject_id"],
                CurriculumVersion.grade == 9,
            )
            .first()
        )

        pending = CEGExpectation(
            ministry_code="B1.9",
            cb_code=f"CB-pending-{uuid4().hex[:6]}",
            subject_id=ceg_seed["subject_id"],
            strand_id=strand_b.id,
            grade=9,
            expectation_type=EXPECTATION_TYPE_SPECIFIC,
            description="Pending row — must be filtered out",
            curriculum_version_id=version.id,
            review_state="pending",
            active=False,
        )
        db_session.add(pending)
        db_session.commit()

        try:
            result = get_expectations_handler(
                {"subject_code": ceg_seed["subject_code"], "grade": 9},
                parent_user,
                db_session,
            )
            codes = [e["se_code"] for e in result["expectations"]]
            assert "B1.9" not in codes
        finally:
            db_session.delete(pending)
            db_session.commit()


# ---------------------------------------------------------------------------
# Route-level tests — full /mcp/call_tool surface, role allowlist
# ---------------------------------------------------------------------------


class TestGetExpectationsRoute:
    """End-to-end tests via ``POST /mcp/call_tool``.

    Verifies auth, flag gating, role allowlist round-trip, and Pydantic
    body validation (422 on a malformed request body).
    """

    def test_unauthenticated_returns_401(self, client, mcp_flag_on):
        """Missing ``Authorization`` → 401 even when the flag is ON."""
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_expectations",
                "arguments": {"subject_code": "MATH", "grade": 9},
            },
        )
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "user_fixture",
        ["parent_user", "student_user", "teacher_user", "admin_user"],
    )
    def test_all_allowlisted_roles_reach_handler(
        self, request, client, mcp_flag_on, ceg_seed, user_fixture
    ):
        """Every role in the catalog allowlist round-trips through the route.

        Asserts the dispatcher reaches the handler (200 with a real SE
        list) for PARENT / STUDENT / TEACHER / ADMIN — none is silently
        gated by the catalog filter or the dispatch-time role re-check.
        """
        user = request.getfixturevalue(user_fixture)
        headers = _auth(client, user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_expectations",
                "arguments": {
                    "subject_code": ceg_seed["subject_code"],
                    "grade": 9,
                },
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["name"] == "get_expectations"
        assert len(body["content"]["expectations"]) == 3

    def test_route_strand_filter(
        self, client, mcp_flag_on, parent_user, ceg_seed
    ):
        """Strand filter narrows the route response too."""
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_expectations",
                "arguments": {
                    "subject_code": ceg_seed["subject_code"],
                    "grade": 9,
                    "strand_code": "C",
                },
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        ses = resp.json()["content"]["expectations"]
        assert len(ses) == 1
        assert ses[0]["se_code"] == "C1.1"

    def test_route_unknown_subject_returns_empty_200(
        self, client, mcp_flag_on, parent_user
    ):
        """Unknown subject is 200 + empty list, NOT 404 (catalog semantics)."""
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "get_expectations",
                "arguments": {"subject_code": "ZZZNONE", "grade": 9},
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["content"] == {"expectations": []}

    def test_route_missing_name_returns_422(
        self, client, mcp_flag_on, parent_user
    ):
        """Pydantic rejects an empty ``name`` field with 422.

        Captures the route-layer body-validation surface for malformed
        ``call_tool`` requests; per-tool argument validation lives in the
        handler (and degrades to ``{"expectations": []}`` for this tool).
        """
        headers = _auth(client, parent_user.email)
        resp = client.post(
            "/mcp/call_tool",
            json={
                "name": "",
                "arguments": {"subject_code": "MATH", "grade": 9},
            },
            headers=headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Registry tests — concrete handler + role allowlist
# ---------------------------------------------------------------------------


class TestGetExpectationsRegistry:
    """Lightweight checks on the ``TOOLS`` registry entry itself."""

    def test_registered_with_concrete_handler(self):
        """``TOOLS["get_expectations"].handler`` is no longer the stub."""
        from app.mcp.tools import TOOLS
        from app.mcp.tools.get_expectations import get_expectations_handler

        descriptor = TOOLS["get_expectations"]
        assert descriptor.handler is get_expectations_handler

    @pytest.mark.parametrize(
        "role", ["PARENT", "STUDENT", "TEACHER", "ADMIN"]
    )
    def test_role_in_allowlist(self, role):
        from app.mcp.tools import TOOLS

        descriptor = TOOLS["get_expectations"]
        assert descriptor.is_role_allowed(role)

    @pytest.mark.parametrize("role", ["BOARD_ADMIN", "CURRICULUM_ADMIN"])
    def test_role_not_extended(self, role):
        """2B-1 issue scope keeps the original 4-role allowlist.

        BOARD_ADMIN / CURRICULUM_ADMIN read access via MCP is a separate
        decision (different stripe); this test pins the current scope so
        a future inadvertent extension surfaces in review.
        """
        from app.mcp.tools import TOOLS

        descriptor = TOOLS["get_expectations"]
        assert not descriptor.is_role_allowed(role)
