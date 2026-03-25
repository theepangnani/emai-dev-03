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
