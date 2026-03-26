"""Tests for School Report Card Upload & AI Analysis (§6.121, #2286)."""
import json
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import patch, AsyncMock

import pytest
from conftest import PASSWORD, _auth

# ── Sample text from actual YRDSB report cards ──

ELEMENTARY_SAMPLE = """
Student: Kokulatheepan, Haashini 718798929 0 0
08 M Schmidt 1 1
York Region District School Board Franklin Street Public School
02/19/2026
"""

SECONDARY_SAMPLE = """
Semester Two Interim Progress Report
March 9, 2026
Report Issue date:
Bill Hogarth Secondary School
Student Name: Kokulatheepan, Thanushan
Student Number: 349017574
"""

SAMPLE_ANALYSIS = {
    "teacher_feedback_summary": "Strong overall performance.",
    "grade_analysis": [
        {"subject": "Mathematics", "grade": "71%", "median": "84%", "level": 2,
         "teacher_comment": "Solid understanding.", "feedback": "Below median."}
    ],
    "learning_skills": {
        "ratings": [{"skill": "Responsibility", "rating": "G"}],
        "summary": "Good work habits.",
    },
    "improvement_areas": [
        {"area": "Math", "detail": "Practice conversions", "priority": "high"}
    ],
    "parent_tips": [
        {"tip": "Use cooking for math practice", "related_subject": "Mathematics"}
    ],
    "overall_summary": "Good term overall.",
}

SAMPLE_CAREER = {
    "strengths": ["Visual Arts", "Music"],
    "grade_trends": [
        {"subject": "Math", "trajectory": "stable", "data": "71% → 71%", "note": ""}
    ],
    "career_suggestions": [
        {"career": "UX Design", "reasoning": "Strong visual arts.",
         "related_subjects": ["Visual Arts"], "next_steps": "Take TGJ1O."}
    ],
    "overall_assessment": "Creative strengths.",
}


# ── Fixtures ──

@pytest.fixture()
def src_users(client, db_session):
    """Create parent, student_user, student record, and link them."""
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from sqlalchemy import insert

    # Parent
    parent = db_session.query(User).filter(User.email == "src_parent@test.com").first()
    if not parent:
        resp = client.post("/api/auth/register", json={
            "email": "src_parent@test.com", "password": PASSWORD,
            "full_name": "SRC Parent", "role": "parent",
        })
        assert resp.status_code in (200, 201, 409), resp.text
        parent = db_session.query(User).filter(User.email == "src_parent@test.com").first()

    # Student user
    stu_user = db_session.query(User).filter(User.email == "src_student@test.com").first()
    if not stu_user:
        resp = client.post("/api/auth/register", json={
            "email": "src_student@test.com", "password": PASSWORD,
            "full_name": "SRC Student", "role": "student",
        })
        assert resp.status_code in (200, 201, 409), resp.text
        stu_user = db_session.query(User).filter(User.email == "src_student@test.com").first()

    # Student record
    student = db_session.query(Student).filter(Student.user_id == stu_user.id).first()
    if not student:
        student = Student(user_id=stu_user.id, grade_level="08", school_name="Test School")
        db_session.add(student)
        db_session.commit()

    # Link parent-child
    existing = db_session.execute(
        parent_students.select().where(
            parent_students.c.parent_id == parent.id,
            parent_students.c.student_id == student.id,
        )
    ).first()
    if not existing:
        db_session.execute(insert(parent_students).values(
            parent_id=parent.id, student_id=student.id,
            relationship_type="GUARDIAN",
        ))
        db_session.commit()

    # Outsider parent (no child link)
    outsider = db_session.query(User).filter(User.email == "src_outsider@test.com").first()
    if not outsider:
        resp = client.post("/api/auth/register", json={
            "email": "src_outsider@test.com", "password": PASSWORD,
            "full_name": "SRC Outsider", "role": "parent",
        })
        assert resp.status_code in (200, 201, 409), resp.text
        outsider = db_session.query(User).filter(User.email == "src_outsider@test.com").first()

    return {
        "parent": parent,
        "student_user": stu_user,
        "student": student,
        "outsider": outsider,
    }


# ── Metadata Extraction Tests ──

class TestMetadataExtraction:
    def test_extract_elementary_metadata(self):
        from app.services.school_report_card_service import extract_metadata
        result = extract_metadata(ELEMENTARY_SAMPLE)
        assert result["school_name"] is not None
        assert "Franklin" in result["school_name"]

    def test_extract_secondary_metadata(self):
        from app.services.school_report_card_service import extract_metadata
        result = extract_metadata(SECONDARY_SAMPLE)
        assert result["school_name"] is not None
        assert "Hogarth" in result["school_name"]

    def test_extract_no_metadata(self):
        from app.services.school_report_card_service import extract_metadata
        result = extract_metadata("")
        assert all(v is None for v in result.values())


# ── Upload Tests ──

class TestUploadEndpoint:
    def test_upload_single_pdf(self, client, db_session, src_users):
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]
        pdf_bytes = b"%PDF-1.4 fake content for testing"

        with patch("app.api.routes.school_report_cards.process_file", return_value="Extracted text content for testing purposes with enough length"), \
             patch("app.api.routes.school_report_cards.save_file", return_value="fake_path.pdf"), \
             patch("app.api.routes.school_report_cards.check_upload_allowed"), \
             patch("app.api.routes.school_report_cards.record_upload"):

            resp = client.post(
                "/api/school-report-cards/upload",
                headers=headers,
                data={"student_id": str(student.id)},
                files=[("files", ("test_card.pdf", BytesIO(pdf_bytes), "application/pdf"))],
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total_uploaded"] == 1
        assert data["total_uploaded"] == len(data["uploaded"])

    def test_upload_requires_parent_role(self, client, src_users):
        headers = _auth(client, "src_student@test.com")
        resp = client.post(
            "/api/school-report-cards/upload",
            headers=headers,
            data={"student_id": "1"},
            files=[("files", ("test.pdf", BytesIO(b"%PDF"), "application/pdf"))],
        )
        assert resp.status_code == 403

    def test_upload_unauthorized_parent(self, client, src_users):
        headers = _auth(client, "src_outsider@test.com")
        student = src_users["student"]
        resp = client.post(
            "/api/school-report-cards/upload",
            headers=headers,
            data={"student_id": str(student.id)},
            files=[("files", ("test.pdf", BytesIO(b"%PDF"), "application/pdf"))],
        )
        assert resp.status_code == 403


# ── List Tests ──

class TestListEndpoint:
    def test_list_report_cards(self, client, db_session, src_users):
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        # Create a report card directly in DB
        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="list_test.pdf",
            text_content="Some text",
            term="Winter 2026",
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        resp = client.get(
            f"/api/school-report-cards/{student.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        cards = resp.json()
        assert len(cards) >= 1
        assert any(c["original_filename"] == "list_test.pdf" for c in cards)

    def test_list_unauthorized(self, client, src_users):
        headers = _auth(client, "src_outsider@test.com")
        student = src_users["student"]
        resp = client.get(
            f"/api/school-report-cards/{student.id}",
            headers=headers,
        )
        assert resp.status_code == 403


# ── Analyze Tests ──

class TestAnalyzeEndpoint:
    def test_analyze_report_card(self, client, db_session, src_users):
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="analyze_test.pdf",
            text_content="A" * 100,  # sufficient text
            term="Winter 2026",
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        mock_result = (json.dumps(SAMPLE_ANALYSIS), "end_turn")

        with patch("app.services.school_report_card_service.generate_content", new_callable=AsyncMock, return_value=mock_result), \
             patch("app.api.routes.school_report_cards.check_ai_usage"), \
             patch("app.api.routes.school_report_cards.increment_ai_usage"):
            resp = client.post(
                f"/api/school-report-cards/{rc.id}/analyze",
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["analysis_type"] == "full"
        assert data["teacher_feedback_summary"] != ""

    def test_analyze_no_text(self, client, db_session, src_users):
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="empty_test.pdf",
            text_content="short",
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        resp = client.post(
            f"/api/school-report-cards/{rc.id}/analyze",
            headers=headers,
        )
        assert resp.status_code == 400


# ── Delete Tests ──

class TestDeleteEndpoint:
    def test_soft_delete(self, client, db_session, src_users):
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="delete_test.pdf",
            text_content="Some text",
        )
        db_session.add(rc)
        db_session.commit()

        resp = client.delete(
            f"/api/school-report-cards/{rc.id}",
            headers=headers,
        )
        assert resp.status_code == 200

        db_session.refresh(rc)
        assert rc.archived_at is not None

    def test_delete_not_found(self, client, src_users):
        headers = _auth(client, "src_parent@test.com")
        resp = client.delete(
            "/api/school-report-cards/99999",
            headers=headers,
        )
        assert resp.status_code == 404


# ── Career Path Tests ──

class TestCareerPathEndpoint:
    def test_career_path_requires_cards(self, client, db_session, src_users):
        """POST career-path with no cards returns 400."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        # Archive all existing cards for this student so none are available
        from app.models.school_report_card import SchoolReportCard
        existing = db_session.query(SchoolReportCard).filter(
            SchoolReportCard.student_id == student.id,
            SchoolReportCard.archived_at.is_(None),
        ).all()
        for card in existing:
            card.archived_at = datetime.now(timezone.utc)
        db_session.commit()

        resp = client.post(
            f"/api/school-report-cards/{student.id}/career-path",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "No report cards" in resp.json()["detail"]

        # Unarchive them again so other tests are not affected
        for card in existing:
            card.archived_at = None
        db_session.commit()

    def test_career_path_unauthorized(self, client, src_users):
        """Outsider parent gets 403."""
        headers = _auth(client, "src_outsider@test.com")
        student = src_users["student"]

        resp = client.post(
            f"/api/school-report-cards/{student.id}/career-path",
            headers=headers,
        )
        assert resp.status_code == 403

    def test_career_path_student_role_denied(self, client, src_users):
        """Student role cannot access career-path endpoint (PARENT only)."""
        headers = _auth(client, "src_student@test.com")
        student = src_users["student"]

        resp = client.post(
            f"/api/school-report-cards/{student.id}/career-path",
            headers=headers,
        )
        assert resp.status_code == 403

    def test_career_path_no_text_content(self, client, db_session, src_users):
        """Cards exist but none have text_content → 400."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        # Archive existing cards so they don't interfere
        from app.models.school_report_card import SchoolReportCard
        existing = db_session.query(SchoolReportCard).filter(
            SchoolReportCard.student_id == student.id,
            SchoolReportCard.archived_at.is_(None),
        ).all()
        for card in existing:
            card.archived_at = datetime.now(timezone.utc)
        db_session.flush()

        # Create a card with no text content
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="no_text_career.pdf",
            text_content=None,
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        try:
            resp = client.post(
                f"/api/school-report-cards/{student.id}/career-path",
                headers=headers,
            )
            assert resp.status_code == 400
            assert "No report cards" in resp.json()["detail"]
        finally:
            # Clean up: archive the no-text card, restore originals
            rc.archived_at = datetime.now(timezone.utc)
            for card in existing:
                card.archived_at = None
            db_session.commit()

    def test_career_path_success(self, client, db_session, src_users):
        """Mock generate_content, upload a card with text, trigger analyze, then career path."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        # Create a report card with sufficient text
        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="career_test.pdf",
            text_content="A" * 100,
            term="Winter 2026",
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        # First analyze the card
        mock_analysis = (json.dumps(SAMPLE_ANALYSIS), "end_turn")
        with patch("app.services.school_report_card_service.generate_content", new_callable=AsyncMock, return_value=mock_analysis), \
             patch("app.api.routes.school_report_cards.check_ai_usage"), \
             patch("app.api.routes.school_report_cards.increment_ai_usage"):
            resp = client.post(
                f"/api/school-report-cards/{rc.id}/analyze",
                headers=headers,
            )
        assert resp.status_code == 200, resp.text

        # Now trigger career path
        mock_career = (json.dumps(SAMPLE_CAREER), "end_turn")
        with patch("app.services.school_report_card_service.generate_content", new_callable=AsyncMock, return_value=mock_career), \
             patch("app.api.routes.school_report_cards.check_ai_usage"), \
             patch("app.api.routes.school_report_cards.increment_ai_usage"):
            resp = client.post(
                f"/api/school-report-cards/{student.id}/career-path",
                headers=headers,
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "strengths" in data
        assert "career_suggestions" in data
        assert "overall_assessment" in data
        assert data["report_cards_analyzed"] >= 1

    def test_career_path_cache_hit(self, client, db_session, src_users):
        """Second career-path call with same cards returns cached result without AI call."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        # Create a report card with text
        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="cache_career_test.pdf",
            text_content="C" * 100,
            term="Fall 2025",
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        mock_career = (json.dumps(SAMPLE_CAREER), "end_turn")
        mock_gen = AsyncMock(return_value=mock_career)

        try:
            # First call — should invoke generate_content
            with patch("app.services.school_report_card_service.generate_content", mock_gen), \
                 patch("app.api.routes.school_report_cards.check_ai_usage"), \
                 patch("app.api.routes.school_report_cards.increment_ai_usage"):
                resp1 = client.post(
                    f"/api/school-report-cards/{student.id}/career-path",
                    headers=headers,
                )
            assert resp1.status_code == 200, resp1.text
            assert mock_gen.call_count == 1

            # Second call — should return cached, generate_content NOT called again
            mock_gen2 = AsyncMock(return_value=mock_career)
            with patch("app.services.school_report_card_service.generate_content", mock_gen2), \
                 patch("app.api.routes.school_report_cards.check_ai_usage"), \
                 patch("app.api.routes.school_report_cards.increment_ai_usage"):
                resp2 = client.post(
                    f"/api/school-report-cards/{student.id}/career-path",
                    headers=headers,
                )
            assert resp2.status_code == 200, resp2.text
            assert mock_gen2.call_count == 0

            # Verify both responses have the same data
            data1 = resp1.json()
            data2 = resp2.json()
            assert data1["strengths"] == data2["strengths"]
            assert data1["career_suggestions"] == data2["career_suggestions"]
        finally:
            rc.archived_at = datetime.now(timezone.utc)
            db_session.commit()

    def test_career_path_unauthenticated(self, client):
        """No auth token → 401."""
        resp = client.post("/api/school-report-cards/1/career-path")
        assert resp.status_code in (401, 403)


# ── Cache Behavior Tests ──

class TestCacheBehavior:
    def test_analyze_returns_cached(self, client, db_session, src_users):
        """Analyze twice; second call should not call generate_content again."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="cache_test.pdf",
            text_content="B" * 100,
            term="Spring 2026",
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        mock_result = (json.dumps(SAMPLE_ANALYSIS), "end_turn")
        mock_gen = AsyncMock(return_value=mock_result)

        # First call — should invoke generate_content
        with patch("app.services.school_report_card_service.generate_content", mock_gen), \
             patch("app.api.routes.school_report_cards.check_ai_usage"), \
             patch("app.api.routes.school_report_cards.increment_ai_usage"):
            resp1 = client.post(
                f"/api/school-report-cards/{rc.id}/analyze",
                headers=headers,
            )
        assert resp1.status_code == 200
        assert mock_gen.call_count == 1

        # Second call — should return cached, generate_content NOT called again
        mock_gen2 = AsyncMock(return_value=mock_result)
        with patch("app.services.school_report_card_service.generate_content", mock_gen2), \
             patch("app.api.routes.school_report_cards.check_ai_usage"), \
             patch("app.api.routes.school_report_cards.increment_ai_usage"):
            resp2 = client.post(
                f"/api/school-report-cards/{rc.id}/analyze",
                headers=headers,
            )
        assert resp2.status_code == 200
        assert mock_gen2.call_count == 0

    def test_get_analysis_not_yet_analyzed(self, client, db_session, src_users):
        """GET analysis endpoint returns {"analysis": null} for unanalyzed card."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        from app.models.school_report_card import SchoolReportCard
        rc = SchoolReportCard(
            student_id=student.id,
            uploaded_by_user_id=src_users["parent"].id,
            original_filename="no_analysis_test.pdf",
            text_content="Some text content",
            grade_level="08",
        )
        db_session.add(rc)
        db_session.commit()

        resp = client.get(
            f"/api/school-report-cards/{rc.id}/analysis",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {"analysis": None}


# ── File Validation Tests ──

class TestFileValidation:
    def test_reject_invalid_extension(self, client, db_session, src_users):
        """Upload .docx file, expect it in failures list."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        with patch("app.api.routes.school_report_cards.check_upload_allowed"), \
             patch("app.api.routes.school_report_cards.record_upload"):
            resp = client.post(
                "/api/school-report-cards/upload",
                headers=headers,
                data={"student_id": str(student.id)},
                files=[("files", ("bad_file.docx", BytesIO(b"fake content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_uploaded"] == 0
        # The .docx file is rejected — it does not appear in the uploaded list
        assert len(data["uploaded"]) == 0

    def test_reject_more_than_10_files(self, client, db_session, src_users):
        """Upload 11 files, expect 400."""
        headers = _auth(client, "src_parent@test.com")
        student = src_users["student"]

        files = [
            ("files", (f"file_{i}.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf"))
            for i in range(11)
        ]

        resp = client.post(
            "/api/school-report-cards/upload",
            headers=headers,
            data={"student_id": str(student.id)},
            files=files,
        )
        assert resp.status_code == 400
        assert "Maximum 10 files" in resp.json()["detail"]


# ── _parse_report_date unit tests ──

from datetime import date


class TestParseReportDate:
    """Unit tests for _parse_report_date helper."""

    @staticmethod
    def _fn():
        from app.api.routes.school_report_cards import _parse_report_date
        return _parse_report_date

    def test_iso_date_format(self):
        assert self._fn()("2024-01-15") == date(2024, 1, 15)

    def test_iso_datetime_format(self):
        assert self._fn()("2024-01-15T10:30:00") == date(2024, 1, 15)

    def test_iso_date_with_whitespace(self):
        assert self._fn()("  2024-06-30  ") == date(2024, 6, 30)

    def test_mm_dd_yyyy(self):
        assert self._fn()("02/19/2026") == date(2026, 2, 19)

    def test_long_month_format(self):
        assert self._fn()("March 9, 2026") == date(2026, 3, 9)

    def test_short_month_format(self):
        assert self._fn()("Mar 9, 2026") == date(2026, 3, 9)

    def test_none_input(self):
        assert self._fn()(None) is None

    def test_empty_string(self):
        assert self._fn()("") is None

    def test_invalid_string(self):
        assert self._fn()("not-a-date") is None


# ── extract_date_from_filename unit tests ──


class TestExtractDateFromFilename:
    """Unit tests for extract_date_from_filename helper (#2368)."""

    @staticmethod
    def _fn():
        from app.services.school_report_card_service import extract_date_from_filename
        return extract_date_from_filename

    def test_month_year_at_start(self):
        assert self._fn()("March 2026 YRDSB Report Card.pdf") == "March 1, 2026"

    def test_month_year_with_dash_separator(self):
        assert self._fn()("February 2026 - Progress Report.pdf") == "February 1, 2026"

    def test_month_year_anywhere(self):
        assert self._fn()("Report Card January 2025.pdf") == "January 1, 2025"

    def test_no_date_in_filename(self):
        assert self._fn()("report_card_final.pdf") is None

    def test_none_input(self):
        assert self._fn()(None) is None

    def test_empty_string(self):
        assert self._fn()("") is None

    def test_month_year_no_extension(self):
        assert self._fn()("June 2024 Report") == "June 1, 2024"

    def test_case_insensitive(self):
        result = self._fn()("NOVEMBER 2025 report.pdf")
        assert result is not None
        assert "2025" in result


# ── extract_metadata broadened date fallback tests ──


class TestMetadataDateFallback:
    """Tests for the broadened OCR date extraction fallback (#2368)."""

    def test_standalone_month_year_in_text(self):
        from app.services.school_report_card_service import extract_metadata
        text = "Semester Two Interim Progress Report\nMarch 2026\nBill Hogarth Secondary School"
        result = extract_metadata(text)
        assert result["report_date"] == "March 1, 2026"

    def test_labeled_date_takes_priority(self):
        from app.services.school_report_card_service import extract_metadata
        text = "Date: 02/19/2026\nSome text about January 2025"
        result = extract_metadata(text)
        assert result["report_date"] == "02/19/2026"
