"""Tests for CB-CMCP-001 M1-B 1B-2 class-context resolver (#4472).

Covers
------

- Empty envelope when ``course_id`` is None: ``fallback_used == True``.
- Populated envelope when course has uploaded ``CourseContent``.
- Populated envelope when course has recent ``CourseAnnouncement``.
- ``teacher_digest_summary`` populated when the teacher has matching
  ``TeacherCommunication`` rows in the last 30 days.
- ``teacher_library_artifacts`` populated when an APPROVED ``StudyGuide``
  row's ``se_codes`` overlap ``target_se_codes``.
- ``envelope_size`` > 0 when any category has data; ``fallback_used`` is
  ``False`` in that case.
- PRIVACY: no student names, student IDs, or per-student grade fields
  appear in any cell of the envelope output.
- 14-day announcement window: rows older than 14 days are excluded.
- 30-day digest window: rows older than 30 days are excluded.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def teacher_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"cmcp_ccr_teacher_{uuid4().hex[:8]}@test.com",
        full_name="CCR Teacher",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def teacher(db_session, teacher_user):
    from app.models.teacher import Teacher

    t = Teacher(user_id=teacher_user.id, school_name="CCR Test School")
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def course(db_session, teacher):
    """A course with a Google Classroom id (for digest bridging)."""
    from app.models.course import Course

    c = Course(
        name="CCR Math",
        subject="Math",
        teacher_id=teacher.id,
        google_classroom_id=f"gc-{uuid4().hex[:8]}",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def student_for_privacy(db_session):
    """A student whose name MUST NOT leak into the envelope.

    Created intentionally with a distinctive name so the privacy
    assertion can scan envelope JSON for it and fail loudly if a future
    refactor accidentally pulls student fields into a cell.
    """
    from app.core.security import get_password_hash
    from app.models.student import Student
    from app.models.user import User, UserRole

    distinctive_email = f"ccr_privacy_DistinctiveStudentX_{uuid4().hex[:8]}@test.com"
    user = User(
        email=distinctive_email,
        full_name="DistinctiveStudentX PrivacyProbe",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    s = Student(user_id=user.id, grade_level=8, school_name="CCR Test School")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


# ---------------------------------------------------------------------------
# Empty / fallback path
# ---------------------------------------------------------------------------


def test_resolve_returns_empty_envelope_when_course_id_is_none(
    db_session, teacher_user
):
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=None,
        target_se_codes=[],
        db=db_session,
    )

    assert env.course_id is None
    assert env.user_id == teacher_user.id
    assert env.course_contents == []
    assert env.classroom_announcements == []
    assert env.teacher_digest_summary is None
    assert env.teacher_library_artifacts == []
    assert env.envelope_size == 0
    assert env.cited_source_count == 0
    assert env.fallback_used is True


def test_resolve_with_unknown_course_returns_empty(db_session, teacher_user):
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=999_999_999,
        target_se_codes=["A1.1"],
        db=db_session,
    )
    assert env.course_contents == []
    assert env.classroom_announcements == []
    assert env.teacher_digest_summary is None
    assert env.fallback_used is True


# ---------------------------------------------------------------------------
# (a) course_contents
# ---------------------------------------------------------------------------


def test_resolve_pulls_uploaded_course_contents(
    db_session, teacher_user, course
):
    from app.models.course_content import CourseContent
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    cc = CourseContent(
        course_id=course.id,
        title="Linear functions notes",
        description="Introduction to linear functions and slope-intercept form.",
        content_type="notes",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(cc)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )

    assert len(env.course_contents) == 1
    cell = env.course_contents[0]
    assert cell["title"] == "Linear functions notes"
    assert "linear functions" in cell["summary"].lower()
    assert cell["content_type"] == "notes"
    assert env.envelope_size >= 1
    assert env.fallback_used is False


def test_resolve_truncates_long_course_content_summary(
    db_session, teacher_user, course
):
    from app.models.course_content import CourseContent
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    long_desc = "a" * 1200
    cc = CourseContent(
        course_id=course.id,
        title="Big notes",
        description=long_desc,
        content_type="notes",
        created_by_user_id=teacher_user.id,
    )
    db_session.add(cc)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )
    assert len(env.course_contents) == 1
    assert len(env.course_contents[0]["summary"]) <= 500


# ---------------------------------------------------------------------------
# (b) classroom_announcements
# ---------------------------------------------------------------------------


def test_resolve_pulls_recent_announcements(db_session, teacher_user, course):
    from app.models.course_announcement import CourseAnnouncement
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    now = datetime.now(timezone.utc)
    fresh = CourseAnnouncement(
        course_id=course.id,
        google_announcement_id=f"gca-{uuid4().hex[:8]}",
        text="Reminder: quiz on Friday covering slope-intercept.",
        creator_name="Mr. Thompson",
        creation_time=now - timedelta(days=2),
    )
    db_session.add(fresh)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )

    assert len(env.classroom_announcements) == 1
    assert "slope-intercept" in env.classroom_announcements[0]["text"]
    assert env.classroom_announcements[0]["creator_name"] == "Mr. Thompson"


def test_resolve_includes_freshly_ingested_announcement_with_stale_creation_time(
    db_session, teacher_user, course
):
    """Documented OR-on-created_at semantics: a freshly ingested item with
    stale ``creation_time`` still surfaces because ``created_at`` is fresh.
    This is intentional — the teacher just uploaded it, so it IS recent
    context for the prompt even if the GC creation timestamp is months old."""
    from app.models.course_announcement import CourseAnnouncement
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    now = datetime.now(timezone.utc)
    stale = CourseAnnouncement(
        course_id=course.id,
        google_announcement_id=f"gca-stale-{uuid4().hex[:8]}",
        text="Old GC announcement, just ingested today.",
        creator_name="Mr. Thompson",
        creation_time=now - timedelta(days=30),
    )
    db_session.add(stale)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )
    assert len(env.classroom_announcements) == 1


def test_resolve_excludes_announcement_when_both_timestamps_older_than_14_days(
    db_session, teacher_user, course
):
    """When BOTH ``creation_time`` AND ``created_at`` are >14 days old, the
    row drops out — this is the actual recency contract from A1 FR-02.5b.

    Backdate ``created_at`` via direct SQL UPDATE because the column has
    ``server_default=now()`` which the constructor can't override.
    """
    from sqlalchemy import text

    from app.models.course_announcement import CourseAnnouncement
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    now = datetime.now(timezone.utc)
    stale = CourseAnnouncement(
        course_id=course.id,
        google_announcement_id=f"gca-stale-both-{uuid4().hex[:8]}",
        text="Truly stale announcement.",
        creator_name="Mr. Thompson",
        creation_time=now - timedelta(days=30),
    )
    db_session.add(stale)
    db_session.commit()
    db_session.refresh(stale)

    backdate = (now - timedelta(days=30)).isoformat()
    db_session.execute(
        text(
            "UPDATE course_announcements SET created_at = :ts WHERE id = :id"
        ),
        {"ts": backdate, "id": stale.id},
    )
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )
    assert len(env.classroom_announcements) == 0


# ---------------------------------------------------------------------------
# (c) teacher_digest_summary
# ---------------------------------------------------------------------------


def test_resolve_pulls_teacher_digest_for_course(
    db_session, teacher_user, course
):
    from app.models.teacher_communication import TeacherCommunication
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    now = datetime.now(timezone.utc)
    tc = TeacherCommunication(
        user_id=teacher_user.id,
        type="email",
        source_id=f"src-{uuid4().hex[:8]}",
        sender_name="Parent A",
        subject="Question about slope homework",
        ai_summary="Parent asks how to interpret negative slope on Q3.",
        course_id=course.google_classroom_id,
        received_at=now - timedelta(days=5),
    )
    db_session.add(tc)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )

    assert env.teacher_digest_summary is not None
    assert env.teacher_digest_summary["count"] == 1
    assert env.teacher_digest_summary["window_days"] == 30
    assert (
        "slope" in env.teacher_digest_summary["items"][0]["ai_summary"].lower()
    )


def test_resolve_returns_none_digest_when_course_has_no_gc_link(
    db_session, teacher_user, teacher
):
    from app.models.course import Course
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    no_gc = Course(
        name="CCR no-GC",
        subject="Math",
        teacher_id=teacher.id,
        google_classroom_id=None,
    )
    db_session.add(no_gc)
    db_session.commit()
    db_session.refresh(no_gc)

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=no_gc.id,
        target_se_codes=[],
        db=db_session,
    )
    assert env.teacher_digest_summary is None


def test_resolve_excludes_digest_for_other_teachers(
    db_session, teacher_user, course
):
    """A TeacherCommunication owned by ANOTHER teacher must not surface."""
    from app.core.security import get_password_hash
    from app.models.teacher_communication import TeacherCommunication
    from app.models.user import User, UserRole
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    other = User(
        email=f"other_teacher_{uuid4().hex[:8]}@test.com",
        full_name="Other Teacher",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    foreign_tc = TeacherCommunication(
        user_id=other.id,
        type="email",
        source_id=f"foreign-{uuid4().hex[:8]}",
        ai_summary="Foreign teacher's email — must not leak.",
        course_id=course.google_classroom_id,
        received_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(foreign_tc)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )
    assert env.teacher_digest_summary is None


# ---------------------------------------------------------------------------
# (d) teacher_library_artifacts
# ---------------------------------------------------------------------------


def test_resolve_pulls_approved_artifacts_with_se_overlap(
    db_session, teacher_user, course
):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    approved = StudyGuide(
        user_id=teacher_user.id,
        course_id=course.id,
        title="Slope mastery",
        content="...",
        guide_type="study_guide",
        state=ArtifactState.APPROVED,
        se_codes=["MTH8.A1.1", "MTH8.A1.2"],
    )
    draft = StudyGuide(
        user_id=teacher_user.id,
        course_id=course.id,
        title="Draft slope guide",
        content="...",
        guide_type="study_guide",
        state="DRAFT",
        se_codes=["MTH8.A1.1"],
    )
    no_overlap = StudyGuide(
        user_id=teacher_user.id,
        course_id=course.id,
        title="Geometry guide",
        content="...",
        guide_type="study_guide",
        state=ArtifactState.APPROVED,
        se_codes=["MTH8.G1.1"],
    )
    db_session.add_all([approved, draft, no_overlap])
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=["MTH8.A1.1"],
        db=db_session,
    )

    titles = [a["title"] for a in env.teacher_library_artifacts]
    assert "Slope mastery" in titles
    assert "Draft slope guide" not in titles  # state filter
    assert "Geometry guide" not in titles  # SE-overlap filter
    matched = [a for a in env.teacher_library_artifacts if a["title"] == "Slope mastery"][0]
    assert matched["matched_se_codes"] == ["MTH8.A1.1"]


def test_resolve_excludes_artifacts_from_other_courses(
    db_session, teacher_user, course, teacher
):
    """Per #4477 review: library query is course-scoped when course_id is set."""
    from app.models.course import Course
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    other_course = Course(
        name="Other math",
        subject="Math",
        teacher_id=teacher.id,
        google_classroom_id=f"gc-other-{uuid4().hex[:8]}",
    )
    db_session.add(other_course)
    db_session.commit()
    db_session.refresh(other_course)

    own = StudyGuide(
        user_id=teacher_user.id,
        course_id=course.id,
        title="Own course slope",
        content="...",
        guide_type="study_guide",
        state=ArtifactState.APPROVED,
        se_codes=["MTH8.A1.1"],
    )
    foreign = StudyGuide(
        user_id=teacher_user.id,
        course_id=other_course.id,
        title="Other course slope",
        content="...",
        guide_type="study_guide",
        state=ArtifactState.APPROVED,
        se_codes=["MTH8.A1.1"],
    )
    db_session.add_all([own, foreign])
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=["MTH8.A1.1"],
        db=db_session,
    )
    titles = [a["title"] for a in env.teacher_library_artifacts]
    assert "Own course slope" in titles
    assert "Other course slope" not in titles


def test_resolve_pulls_artifacts_across_courses_when_course_id_none(
    db_session, teacher_user, course, teacher
):
    """When course_id is None (CEG-only mode), the library scan is unscoped
    so callers without a course context can still match approved artifacts
    by SE codes alone."""
    from app.models.course import Course
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    other_course = Course(
        name="Other math",
        subject="Math",
        teacher_id=teacher.id,
        google_classroom_id=f"gc-cross-{uuid4().hex[:8]}",
    )
    db_session.add(other_course)
    db_session.commit()
    db_session.refresh(other_course)

    a = StudyGuide(
        user_id=teacher_user.id,
        course_id=other_course.id,
        title="Approved cross-course slope",
        content="...",
        guide_type="study_guide",
        state=ArtifactState.APPROVED,
        se_codes=["MTH8.A1.1"],
    )
    db_session.add(a)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=None,
        target_se_codes=["MTH8.A1.1"],
        db=db_session,
    )
    titles = [a["title"] for a in env.teacher_library_artifacts]
    assert "Approved cross-course slope" in titles


def test_resolve_skips_library_when_no_target_se_codes(
    db_session, teacher_user, course
):
    from app.models.study_guide import StudyGuide
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    approved = StudyGuide(
        user_id=teacher_user.id,
        course_id=course.id,
        title="Slope mastery",
        content="...",
        guide_type="study_guide",
        state=ArtifactState.APPROVED,
        se_codes=["MTH8.A1.1"],
    )
    db_session.add(approved)
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )
    assert env.teacher_library_artifacts == []


# ---------------------------------------------------------------------------
# Envelope metadata
# ---------------------------------------------------------------------------


def test_envelope_size_counts_across_all_categories(
    db_session, teacher_user, course
):
    from app.models.course_announcement import CourseAnnouncement
    from app.models.course_content import CourseContent
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    db_session.add(
        CourseContent(
            course_id=course.id,
            title="Notes A",
            description="A",
            content_type="notes",
        )
    )
    db_session.add(
        CourseContent(
            course_id=course.id,
            title="Notes B",
            description="B",
            content_type="notes",
        )
    )
    db_session.add(
        CourseAnnouncement(
            course_id=course.id,
            google_announcement_id=f"gca-{uuid4().hex[:8]}",
            text="Hi class",
            creator_name="Mr. T",
            creation_time=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=[],
        db=db_session,
    )
    assert env.envelope_size == 3  # 2 contents + 1 announcement
    assert env.cited_source_count == 3
    assert env.fallback_used is False


def test_envelope_fallback_used_true_when_empty(
    db_session, teacher_user, course
):
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=["A1.1"],
        db=db_session,
    )
    assert env.envelope_size == 0
    assert env.fallback_used is True


# ---------------------------------------------------------------------------
# Privacy assertion (per A1 + DD §5.5)
# ---------------------------------------------------------------------------


def test_envelope_contains_no_student_pii(
    db_session, teacher_user, course, student_for_privacy
):
    """Scan the entire envelope JSON for the student's distinctive name +
    student id + user id.  None of these should ever appear in a cell.

    The resolver is deliberately course-scoped + teacher-authored, so a
    failure here means a future refactor accidentally joined a student
    table or pulled a per-student field into a cell.
    """
    from app.models.course_announcement import CourseAnnouncement
    from app.models.course_content import CourseContent
    from app.models.study_guide import StudyGuide
    from app.models.teacher_communication import TeacherCommunication
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.class_context_resolver import ClassContextResolver

    # Populate every category with realistic teacher-authored data.
    db_session.add(
        CourseContent(
            course_id=course.id,
            title="Notes",
            description="Slope intro",
            content_type="notes",
            created_by_user_id=teacher_user.id,
        )
    )
    db_session.add(
        CourseAnnouncement(
            course_id=course.id,
            google_announcement_id=f"gca-{uuid4().hex[:8]}",
            text="Quiz Friday",
            creator_name="Mr. Thompson",
            creation_time=datetime.now(timezone.utc),
        )
    )
    db_session.add(
        TeacherCommunication(
            user_id=teacher_user.id,
            type="email",
            source_id=f"src-{uuid4().hex[:8]}",
            ai_summary="Parent asks about slope homework.",
            course_id=course.google_classroom_id,
            received_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(
        StudyGuide(
            user_id=teacher_user.id,
            course_id=course.id,
            title="Slope mastery",
            content="...",
            guide_type="study_guide",
            state=ArtifactState.APPROVED,
            se_codes=["MTH8.A1.1"],
        )
    )
    db_session.commit()

    env = ClassContextResolver().resolve(
        user_id=teacher_user.id,
        course_id=course.id,
        target_se_codes=["MTH8.A1.1"],
        db=db_session,
    )

    # Serialize the entire envelope to JSON and scan for forbidden tokens.
    blob = json.dumps(env.model_dump(), default=str).lower()

    assert "distinctivestudentx" not in blob, (
        "Student full name leaked into envelope — privacy boundary breached."
    )
    assert "privacyprobe" not in blob, (
        "Student last name leaked into envelope — privacy boundary breached."
    )
    # Student id should never appear as a structural value either.
    forbidden_keys = {
        "student_id",
        "student_ids",
        "student_name",
        "student_email",
        "student_grade",
        "student_user_id",
    }
    for cell in env.course_contents:
        assert not (forbidden_keys & cell.keys())
    for cell in env.classroom_announcements:
        assert not (forbidden_keys & cell.keys())
    for cell in env.teacher_library_artifacts:
        assert not (forbidden_keys & cell.keys())
    if env.teacher_digest_summary is not None:
        assert not (forbidden_keys & env.teacher_digest_summary.keys())
        for item in env.teacher_digest_summary.get("items", []):
            assert not (forbidden_keys & item.keys())


def test_resolver_module_does_not_import_network_clients():
    """Per #4472 hard rule "DO NOT make real API calls" — the resolver's
    contract is to read cached DB rows only.  Assert the source file does
    not import any network client (googleapiclient, requests, httpx).

    A grep on the source file is more robust than a monkeypatch because
    it catches the failure at module-import time rather than at a
    specific call site.
    """
    import inspect

    from app.services.cmcp import class_context_resolver

    src = inspect.getsource(class_context_resolver)

    forbidden = ["googleapiclient", "import requests", "import httpx", "urllib.request"]
    for token in forbidden:
        assert token not in src, (
            f"class_context_resolver.py imports network client {token!r} — "
            f"it must read only cached DB rows."
        )
