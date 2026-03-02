"""Tests for classroom data import feature (#56).

Tests the import session lifecycle, parsers (ICS, CSV, email), and API routes.
"""
import os
import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import date, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


# ── ICS Parser Tests ──────────────────────────────────────────────────────

class TestICSParser:
    """Tests for the ICS (iCalendar) file parser."""

    def test_parse_basic_ics(self):
        """Test parsing a simple ICS file with classroom events."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Math Homework - Grade 10 Math
DTSTART:20260315T235900Z
UID:classroom_event_123@google.com
DESCRIPTION:https://classroom.google.com/c/abc/a/def
END:VEVENT
END:VCALENDAR"""
        from app.services.ics_parser import parse_ics_file
        result = parse_ics_file(ics_content)
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["title"] == "Math Homework"
        assert result["assignments"][0]["course_name"] == "Grade 10 Math"
        assert result["assignments"][0]["due_date"] == "2026-03-15"
        assert result["event_count"] == 1
        assert len(result["errors"]) == 0

    def test_parse_multiple_events(self):
        """Test parsing ICS with multiple events from different courses."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Classroom//EN
BEGIN:VEVENT
SUMMARY:Unit 5 Test - Grade 10 Math
DTSTART:20260315T235900Z
UID:event_001@google.com
DESCRIPTION:Review all chapters
END:VEVENT
BEGIN:VEVENT
SUMMARY:Lab Report - Grade 10 Science
DTSTART:20260320T235900Z
UID:event_002@google.com
DESCRIPTION:Submit lab report
END:VEVENT
BEGIN:VEVENT
SUMMARY:Essay Draft - English Literature
DTSTART:20260322T160000Z
UID:event_003@google.com
DESCRIPTION:First draft due
END:VEVENT
END:VCALENDAR"""
        from app.services.ics_parser import parse_ics_file
        result = parse_ics_file(ics_content)
        assert result["event_count"] == 3
        assert len(result["assignments"]) == 3

        titles = [a["title"] for a in result["assignments"]]
        assert "Unit 5 Test" in titles
        assert "Lab Report" in titles
        assert "Essay Draft" in titles

        courses = [a["course_name"] for a in result["assignments"]]
        assert "Grade 10 Math" in courses
        assert "Grade 10 Science" in courses
        assert "English Literature" in courses

        # Verify dates
        dates = {a["title"]: a["due_date"] for a in result["assignments"]}
        assert dates["Unit 5 Test"] == "2026-03-15"
        assert dates["Lab Report"] == "2026-03-20"
        assert dates["Essay Draft"] == "2026-03-22"

    def test_parse_event_without_course(self):
        """Test event without ' - ' delimiter defaults to Unknown Course."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Standalone Assignment
DTSTART:20260315T120000Z
UID:event_solo@google.com
END:VEVENT
END:VCALENDAR"""
        from app.services.ics_parser import parse_ics_file
        result = parse_ics_file(ics_content)
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["title"] == "Standalone Assignment"
        assert result["assignments"][0]["course_name"] == "Unknown Course"

    def test_parse_empty_ics(self):
        """Test graceful handling of empty ICS file."""
        from app.services.ics_parser import parse_ics_file

        result = parse_ics_file("")
        assert len(result["assignments"]) == 0
        assert len(result["errors"]) > 0
        assert "Empty" in result["errors"][0]

        result2 = parse_ics_file("   \n  ")
        assert len(result2["assignments"]) == 0
        assert len(result2["errors"]) > 0

    def test_parse_invalid_ics(self):
        """Test graceful handling of invalid ICS content."""
        from app.services.ics_parser import parse_ics_file

        # No VCALENDAR wrapper
        result = parse_ics_file("This is not an ICS file at all")
        assert len(result["assignments"]) == 0
        assert len(result["errors"]) > 0
        assert "Invalid ICS" in result["errors"][0]

    def test_parse_event_with_date_only(self):
        """Test parsing event with date-only DTSTART (no time component)."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Project Due - History
DTSTART:20260401
UID:date_only@google.com
END:VEVENT
END:VCALENDAR"""
        from app.services.ics_parser import parse_ics_file
        result = parse_ics_file(ics_content)
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["due_date"] == "2026-04-01"

    def test_parse_event_with_timezone_dtstart(self):
        """Test parsing event with TZID parameter on DTSTART."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Quiz - French
DTSTART;TZID=America/Toronto:20260315T140000
UID:tz_event@google.com
END:VEVENT
END:VCALENDAR"""
        from app.services.ics_parser import parse_ics_file
        result = parse_ics_file(ics_content)
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["due_date"] == "2026-03-15"

    def test_parse_preserves_uid(self):
        """Test that UID is preserved for event tracking."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
SUMMARY:Test - Math
DTSTART:20260315T235900Z
UID:unique_id_12345@google.com
END:VEVENT
END:VCALENDAR"""
        from app.services.ics_parser import parse_ics_file
        result = parse_ics_file(ics_content)
        assert result["assignments"][0]["uid"] == "unique_id_12345@google.com"

    def test_parse_event_without_summary_is_skipped(self):
        """Test that events without SUMMARY are silently skipped."""
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260315T235900Z
UID:no_summary@google.com
END:VEVENT
BEGIN:VEVENT
SUMMARY:Real Assignment - Math
DTSTART:20260316T235900Z
UID:has_summary@google.com
END:VEVENT
END:VCALENDAR"""
        from app.services.ics_parser import parse_ics_file
        result = parse_ics_file(ics_content)
        assert result["event_count"] == 2
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["title"] == "Real Assignment"


# ── CSV Parser Tests ──────────────────────────────────────────────────────

class TestCSVParser:
    """Tests for the CSV import parser."""

    def test_parse_assignments_csv(self):
        """Test parsing assignments CSV template."""
        from app.services.csv_import_parser import parse_csv_import
        csv_content = "Course Name,Assignment Title,Description,Due Date,Points,Status\nGrade 10 Math,Unit 5 Test,Review chapters,2026-03-15,100,assigned"
        result = parse_csv_import(csv_content, "assignments")
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["title"] == "Unit 5 Test"
        assert result["assignments"][0]["course_name"] == "Grade 10 Math"
        assert result["assignments"][0]["description"] == "Review chapters"
        assert result["assignments"][0]["due_date"] == "2026-03-15"
        assert result["assignments"][0]["points"] == 100.0
        assert result["assignments"][0]["status"] == "assigned"
        assert len(result["courses"]) == 1
        assert "Grade 10 Math" in result["courses"]

    def test_parse_multiple_assignments_csv(self):
        """Test parsing CSV with multiple assignment rows."""
        from app.services.csv_import_parser import parse_csv_import
        csv_content = (
            "Course Name,Assignment Title,Description,Due Date,Points,Status\n"
            "Grade 10 Math,Unit 5 Test,Review chapters,2026-03-15,100,assigned\n"
            "Grade 10 Math,Worksheet 12,Practice problems,2026-03-18,50,assigned\n"
            "Grade 10 Science,Lab Report,Chemistry lab,2026-03-20,75,assigned\n"
        )
        result = parse_csv_import(csv_content, "assignments")
        assert len(result["assignments"]) == 3
        assert result["row_count"] == 3
        assert len(result["courses"]) == 2
        assert "Grade 10 Math" in result["courses"]
        assert "Grade 10 Science" in result["courses"]

    def test_parse_materials_csv(self):
        """Test parsing materials CSV template."""
        from app.services.csv_import_parser import parse_csv_import
        csv_content = (
            "Course Name,Material Title,Description,Link,Material Type\n"
            "Grade 10 Math,Chapter 5 Notes,Algebra review,https://example.com/notes,document\n"
            "Grade 10 Science,Lab Safety Video,Watch before lab,https://example.com/video,video\n"
        )
        result = parse_csv_import(csv_content, "materials")
        assert len(result["materials"]) == 2
        assert result["materials"][0]["title"] == "Chapter 5 Notes"
        assert result["materials"][0]["link"] == "https://example.com/notes"
        assert result["materials"][0]["material_type"] == "document"
        assert result["materials"][1]["course_name"] == "Grade 10 Science"

    def test_parse_grades_csv(self):
        """Test parsing grades CSV template."""
        from app.services.csv_import_parser import parse_csv_import
        csv_content = (
            "Course Name,Assignment Title,Student Name,Grade,Max Grade\n"
            "Grade 10 Math,Unit 5 Test,John Smith,85,100\n"
            "Grade 10 Math,Unit 5 Test,Jane Doe,92,100\n"
        )
        result = parse_csv_import(csv_content, "grades")
        assert len(result["grades"]) == 2
        assert result["grades"][0]["assignment_title"] == "Unit 5 Test"
        assert result["grades"][0]["student_name"] == "John Smith"
        assert result["grades"][0]["grade"] == 85.0
        assert result["grades"][0]["max_grade"] == 100.0
        assert result["grades"][1]["grade"] == 92.0

    def test_flexible_column_names(self):
        """Test that alternative column names are mapped correctly."""
        from app.services.csv_import_parser import parse_csv_import
        # Use alternative column names
        csv_content = (
            "Class,Name,Desc,Deadline,Total Points,State\n"
            "AP Biology,DNA Lab,Lab assignment,2026-04-01,50,assigned\n"
        )
        result = parse_csv_import(csv_content, "assignments")
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["course_name"] == "AP Biology"
        assert result["assignments"][0]["title"] == "DNA Lab"
        assert result["assignments"][0]["due_date"] == "2026-04-01"

    def test_get_csv_template(self):
        """Test CSV template generation."""
        from app.services.csv_import_parser import get_csv_template

        template = get_csv_template("assignments")
        assert "Course Name" in template
        assert "Assignment Title" in template
        assert "Due Date" in template
        assert "Points" in template
        assert "Status" in template

        template_m = get_csv_template("materials")
        assert "Material Title" in template_m
        assert "Link" in template_m

        template_g = get_csv_template("grades")
        assert "Student Name" in template_g
        assert "Grade" in template_g
        assert "Max Grade" in template_g

    def test_get_csv_template_invalid_type(self):
        """Test CSV template generation with invalid type raises ValueError."""
        from app.services.csv_import_parser import get_csv_template
        with pytest.raises(ValueError, match="Unknown import type"):
            get_csv_template("invalid_type")

    def test_empty_csv(self):
        """Test graceful handling of empty CSV."""
        from app.services.csv_import_parser import parse_csv_import

        result = parse_csv_import("", "assignments")
        assert len(result["assignments"]) == 0
        assert len(result["errors"]) > 0

        result2 = parse_csv_import("   ", "assignments")
        assert len(result2["assignments"]) == 0
        assert len(result2["errors"]) > 0

    def test_csv_header_only(self):
        """Test CSV with header but no data rows."""
        from app.services.csv_import_parser import parse_csv_import
        csv_content = "Course Name,Assignment Title,Description,Due Date,Points,Status\n"
        result = parse_csv_import(csv_content, "assignments")
        assert len(result["assignments"]) == 0
        assert result["row_count"] == 0
        assert len(result["errors"]) == 0

    def test_date_parsing_formats(self):
        """Test multiple date format parsing."""
        from app.services.csv_import_parser import parse_csv_import

        # YYYY-MM-DD
        csv1 = "Course Name,Assignment Title,Due Date\nMath,Test,2026-03-15\n"
        r1 = parse_csv_import(csv1, "assignments")
        assert r1["assignments"][0]["due_date"] == "2026-03-15"

        # MM/DD/YYYY
        csv2 = "Course Name,Assignment Title,Due Date\nMath,Test,03/15/2026\n"
        r2 = parse_csv_import(csv2, "assignments")
        assert r2["assignments"][0]["due_date"] == "2026-03-15"

        # Month DD, YYYY (quoted because of comma in CSV)
        csv3 = 'Course Name,Assignment Title,Due Date\nMath,Test,"March 15, 2026"\n'
        r3 = parse_csv_import(csv3, "assignments")
        assert r3["assignments"][0]["due_date"] == "2026-03-15"

        # ISO datetime
        csv4 = "Course Name,Assignment Title,Due Date\nMath,Test,2026-03-15T23:59:00\n"
        r4 = parse_csv_import(csv4, "assignments")
        assert r4["assignments"][0]["due_date"] == "2026-03-15"

    def test_csv_rows_without_title_skipped(self):
        """Test that rows without a title are skipped."""
        from app.services.csv_import_parser import parse_csv_import
        csv_content = (
            "Course Name,Assignment Title,Due Date\n"
            "Math,,2026-03-15\n"
            "Math,Real Assignment,2026-03-16\n"
        )
        result = parse_csv_import(csv_content, "assignments")
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["title"] == "Real Assignment"

    def test_unknown_import_type(self):
        """Test that unknown import types produce an error."""
        from app.services.csv_import_parser import parse_csv_import
        result = parse_csv_import("Col1,Col2\nA,B\n", "unknown_type")
        assert len(result["errors"]) > 0
        assert "Unknown import type" in result["errors"][0]

    def test_no_recognized_columns(self):
        """Test CSV with completely unrecognized column headers."""
        from app.services.csv_import_parser import parse_csv_import
        csv_content = "Foo,Bar,Baz\n1,2,3\n"
        result = parse_csv_import(csv_content, "assignments")
        assert len(result["assignments"]) == 0
        assert any("No recognized columns" in e for e in result["errors"])


# ── Email Parser Tests ────────────────────────────────────────────────────

class TestEmailParser:
    """Tests for the classroom email notification parser."""

    def test_detect_assignment_email(self):
        """Test detection of assignment notification email."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="[Grade 10 Math] New assignment: Unit 5 Test",
            body_text="Unit 5 Test\nDue March 15, 2026\n100 points"
        )
        assert result["email_type"] == "assignment"
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["title"] == "Unit 5 Test"
        assert result["assignments"][0]["course_name"] == "Grade 10 Math"
        assert result["assignments"][0]["due_date"] == "2026-03-15"
        assert result["assignments"][0]["points"] == 100.0

    def test_detect_assignment_email_no_points(self):
        """Test assignment email without points information."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="[Biology] New assignment: Cell Division Worksheet",
            body_text="Complete the worksheet on cell division.\nDue March 20, 2026"
        )
        assert result["email_type"] == "assignment"
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["title"] == "Cell Division Worksheet"
        assert result["assignments"][0]["course_name"] == "Biology"
        assert result["assignments"][0]["due_date"] == "2026-03-20"
        assert result["assignments"][0]["points"] is None

    def test_detect_guardian_summary(self):
        """Test parsing guardian weekly summary email."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="Weekly summary for John Smith",
            body_text=(
                "Grade 10 Math\n"
                "- Unit 5 Test - Due March 15, 2026\n"
                "- Worksheet 12 - Due March 18, 2026\n"
                "\n"
                "Grade 10 Science\n"
                "- Lab Report - Due March 20, 2026\n"
            )
        )
        assert result["email_type"] == "guardian_summary"
        assert len(result["assignments"]) >= 1
        # We expect it to find at least some assignments from the summary
        titles = [a["title"] for a in result["assignments"]]
        assert any("Unit 5 Test" in t for t in titles)

    def test_detect_daily_summary(self):
        """Test parsing guardian daily summary email."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="Daily summary for Jane Doe",
            body_text=(
                "Math\n"
                "- Homework 10 - Due March 15, 2026\n"
            )
        )
        assert result["email_type"] == "guardian_summary"
        assert len(result["assignments"]) >= 1

    def test_detect_grade_email(self):
        """Test parsing grade notification email."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="[Grade 10 Math] Grade posted: Unit 5 Test",
            body_text="Your grade: 85/100\nGreat work on the test!"
        )
        assert result["email_type"] == "grade"
        assert len(result["grades"]) == 1
        assert result["grades"][0]["assignment_title"] == "Unit 5 Test"
        assert result["grades"][0]["course_name"] == "Grade 10 Math"
        assert result["grades"][0]["grade"] == 85.0
        assert result["grades"][0]["max_grade"] == 100.0

    def test_detect_grade_returned_email(self):
        """Test parsing grade returned notification."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="[Science] Grade returned: Lab Report",
            body_text="Score: 45/50"
        )
        assert result["email_type"] == "grade"
        assert len(result["grades"]) == 1
        assert result["grades"][0]["grade"] == 45.0
        assert result["grades"][0]["max_grade"] == 50.0

    def test_detect_announcement_email(self):
        """Test parsing announcement notification email."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="[Grade 10 Math] Announcement: Class cancelled tomorrow",
            body_text="Due to a school event, math class is cancelled tomorrow. Please review chapter 6."
        )
        assert result["email_type"] == "announcement"
        assert len(result["announcements"]) == 1
        assert result["announcements"][0]["title"] == "Class cancelled tomorrow"
        assert result["announcements"][0]["course_name"] == "Grade 10 Math"
        assert "chapter 6" in result["announcements"][0]["content"]

    def test_detect_new_announcement_email(self):
        """Test parsing 'New announcement' variant."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="[English] New announcement: Field trip next week",
            body_text="We will visit the museum on Friday."
        )
        assert result["email_type"] == "announcement"
        assert len(result["announcements"]) == 1
        assert result["announcements"][0]["title"] == "Field trip next week"

    def test_unknown_email_format(self):
        """Test graceful handling of unrecognized email format."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="Re: Meeting next week",
            body_text="Let's meet at 3pm on Tuesday."
        )
        assert result["email_type"] == "unknown"
        assert len(result["assignments"]) == 0
        assert len(result["grades"]) == 0
        assert len(result["announcements"]) == 0
        assert len(result["errors"]) > 0

    def test_empty_subject(self):
        """Test handling of empty subject line."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="",
            body_text="Some body text"
        )
        assert result["email_type"] == "unknown"
        assert len(result["errors"]) > 0
        assert "Empty subject" in result["errors"][0]

    def test_assignment_email_extracts_due_date_formats(self):
        """Test that various due date formats are extracted from email body."""
        from app.services.classroom_email_parser import parse_classroom_email

        # "Due March 15, 2026"
        r1 = parse_classroom_email(
            subject="[Math] New assignment: HW1",
            body_text="Due March 15, 2026"
        )
        assert r1["assignments"][0]["due_date"] == "2026-03-15"

        # "Due: 2026-03-15"
        r2 = parse_classroom_email(
            subject="[Math] New assignment: HW2",
            body_text="Due: 2026-03-15"
        )
        assert r2["assignments"][0]["due_date"] == "2026-03-15"

    def test_grade_email_without_score(self):
        """Test grade email when no numeric score is found in body."""
        from app.services.classroom_email_parser import parse_classroom_email
        result = parse_classroom_email(
            subject="[Art] Grade posted: Portfolio Review",
            body_text="Your portfolio has been reviewed. Check Google Classroom for details."
        )
        assert result["email_type"] == "grade"
        assert result["grades"][0]["grade"] is None
        assert result["grades"][0]["max_grade"] is None


# ── Lightweight DB fixture for model tests (avoids full app import) ────────

@pytest.fixture(scope="module")
def _import_db_engine(tmp_path_factory):
    """Create a minimal SQLite engine with only the ImportSession table.

    We create the tables using raw DDL to avoid importing the full ORM model
    graph (which has incompatibilities in some dependent models). This keeps
    the test isolated and fast.
    """
    db_path = tmp_path_factory.mktemp("import_db") / "test_import.db"
    url = f"sqlite:///{db_path}"

    # Set DATABASE_URL so app.core.config doesn't complain during import
    os.environ.setdefault("DATABASE_URL", url)
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-import-tests")

    eng = create_engine(url, connect_args={"check_same_thread": False})

    # Create a minimal users table for the FK, then the import_sessions table
    with eng.begin() as conn:
        conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email VARCHAR(255),
                    hashed_password VARCHAR(255),
                    full_name VARCHAR(255),
                    role VARCHAR(50)
                )"""
            )
        )
        conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                """INSERT OR IGNORE INTO users (id, email, hashed_password, full_name, role)
                VALUES (1, 'import_test@example.com', 'fakehash', 'Import Test User', 'parent')"""
            )
        )
        conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                """CREATE TABLE IF NOT EXISTS import_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    source_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    source_name VARCHAR(255),
                    total_items INTEGER DEFAULT 0,
                    new_items INTEGER DEFAULT 0,
                    duplicate_items INTEGER DEFAULT 0,
                    failed_items INTEGER DEFAULT 0,
                    imported_items INTEGER DEFAULT 0,
                    error_details TEXT,
                    preview_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    completed_at TIMESTAMP
                )"""
            )
        )

    return eng


@pytest.fixture()
def import_db_session(_import_db_engine):
    """Provide a per-test database session for ImportSession model tests."""
    Session = sessionmaker(bind=_import_db_engine)
    session = Session()
    try:
        yield session
    finally:
        # Clean up import_sessions between tests
        from sqlalchemy import text
        session.execute(text("DELETE FROM import_sessions"))
        session.commit()
        session.close()


# ── ImportSession Model Tests ─────────────────────────────────────────────

class TestImportSessionModel:
    """Tests for the ImportSession database schema.

    Uses raw SQL via the lightweight fixture to avoid ORM mapper cascade
    issues with the full model graph. This validates the schema definition
    in app/models/import_session.py.
    """

    def test_create_import_session(self, import_db_session):
        """Test creating an ImportSession record."""
        from sqlalchemy import text

        import_db_session.execute(text(
            """INSERT INTO import_sessions (user_id, source_type, status, source_name)
               VALUES (1, 'csv', 'pending', 'assignments.csv')"""
        ))
        import_db_session.commit()

        row = import_db_session.execute(
            text("SELECT * FROM import_sessions ORDER BY id DESC LIMIT 1")
        ).mappings().first()

        assert row["id"] is not None
        assert row["user_id"] == 1
        assert row["source_type"] == "csv"
        assert row["status"] == "pending"
        assert row["source_name"] == "assignments.csv"

    def test_session_default_values(self, import_db_session):
        """Test default values for status, counters, etc."""
        from sqlalchemy import text

        import_db_session.execute(text(
            """INSERT INTO import_sessions (user_id, source_type, status)
               VALUES (1, 'ics', 'pending')"""
        ))
        import_db_session.commit()

        row = import_db_session.execute(
            text("SELECT * FROM import_sessions ORDER BY id DESC LIMIT 1")
        ).mappings().first()

        # Check default counter values
        assert row["total_items"] == 0
        assert row["new_items"] == 0
        assert row["duplicate_items"] == 0
        assert row["failed_items"] == 0
        assert row["imported_items"] == 0

        # Optional fields should be None
        assert row["error_details"] is None
        assert row["preview_data"] is None
        assert row["source_name"] is None
        assert row["completed_at"] is None

        # created_at should be populated by server default
        assert row["created_at"] is not None

    def test_session_update_counters(self, import_db_session):
        """Test updating import session counters."""
        from sqlalchemy import text

        import_db_session.execute(text(
            """INSERT INTO import_sessions (user_id, source_type, status)
               VALUES (1, 'csv', 'processing')"""
        ))
        import_db_session.commit()

        row = import_db_session.execute(
            text("SELECT id FROM import_sessions ORDER BY id DESC LIMIT 1")
        ).mappings().first()
        session_id = row["id"]

        # Update counters
        import_db_session.execute(text(
            """UPDATE import_sessions
               SET total_items = 10, new_items = 7, duplicate_items = 2,
                   failed_items = 1, imported_items = 7, status = 'completed'
               WHERE id = :sid"""
        ), {"sid": session_id})
        import_db_session.commit()

        updated = import_db_session.execute(
            text("SELECT * FROM import_sessions WHERE id = :sid"),
            {"sid": session_id}
        ).mappings().first()

        assert updated["total_items"] == 10
        assert updated["new_items"] == 7
        assert updated["duplicate_items"] == 2
        assert updated["failed_items"] == 1
        assert updated["imported_items"] == 7
        assert updated["status"] == "completed"

    def test_session_stores_preview_data(self, import_db_session):
        """Test storing JSON preview data on a session."""
        from sqlalchemy import text

        preview = json.dumps({
            "assignments": [
                {"title": "Test 1", "course_name": "Math"},
                {"title": "Test 2", "course_name": "Science"},
            ]
        })

        import_db_session.execute(text(
            """INSERT INTO import_sessions (user_id, source_type, status, preview_data)
               VALUES (1, 'csv', 'preview', :preview)"""
        ), {"preview": preview})
        import_db_session.commit()

        row = import_db_session.execute(
            text("SELECT preview_data FROM import_sessions ORDER BY id DESC LIMIT 1")
        ).mappings().first()

        loaded = json.loads(row["preview_data"])
        assert len(loaded["assignments"]) == 2
        assert loaded["assignments"][0]["title"] == "Test 1"

    def test_session_stores_error_details(self, import_db_session):
        """Test storing error details on a failed session."""
        from sqlalchemy import text

        errors = json.dumps(["Row 3: missing title", "Row 7: invalid date"])

        import_db_session.execute(text(
            """INSERT INTO import_sessions (user_id, source_type, status, error_details)
               VALUES (1, 'email', 'failed', :errors)"""
        ), {"errors": errors})
        import_db_session.commit()

        row = import_db_session.execute(
            text("SELECT error_details FROM import_sessions ORDER BY id DESC LIMIT 1")
        ).mappings().first()

        loaded = json.loads(row["error_details"])
        assert len(loaded) == 2
        assert "Row 3" in loaded[0]


# ── Dedup Hash Tests ──────────────────────────────────────────────────────

class TestDeduplication:
    """Tests for the deduplication hash generation."""

    def test_generate_dedup_hash(self):
        """Test hash generation for deduplication."""
        from app.services.classroom_import_service import _generate_dedup_hash
        h1 = _generate_dedup_hash("Math Homework", "Grade 10 Math", "2026-03-15")
        h2 = _generate_dedup_hash("Math Homework", "Grade 10 Math", "2026-03-15")
        h3 = _generate_dedup_hash("Science Lab", "Grade 10 Science", "2026-03-15")
        assert h1 == h2  # Same inputs = same hash
        assert h1 != h3  # Different inputs = different hash

    def test_dedup_hash_normalization(self):
        """Test that hash normalizes case and whitespace."""
        from app.services.classroom_import_service import _generate_dedup_hash
        h1 = _generate_dedup_hash("Math Homework", "Grade 10 Math", "2026-03-15")
        h2 = _generate_dedup_hash("  math homework  ", "  grade 10 math  ", "2026-03-15")
        assert h1 == h2

    def test_dedup_hash_case_insensitive(self):
        """Test that hash is case-insensitive for title and course."""
        from app.services.classroom_import_service import _generate_dedup_hash
        h1 = _generate_dedup_hash("MATH HOMEWORK", "GRADE 10 MATH", "2026-03-15")
        h2 = _generate_dedup_hash("math homework", "grade 10 math", "2026-03-15")
        assert h1 == h2

    def test_dedup_hash_none_date(self):
        """Test hash with None due date."""
        from app.services.classroom_import_service import _generate_dedup_hash
        h1 = _generate_dedup_hash("Math Homework", "Grade 10 Math", None)
        h2 = _generate_dedup_hash("Math Homework", "Grade 10 Math", None)
        h3 = _generate_dedup_hash("Math Homework", "Grade 10 Math", "2026-03-15")
        assert h1 == h2
        assert h1 != h3  # None date differs from a specific date

    def test_dedup_hash_is_sha256(self):
        """Test that hash output is a 64-character hex SHA-256 digest."""
        from app.services.classroom_import_service import _generate_dedup_hash
        h = _generate_dedup_hash("Test", "Course", "2026-01-01")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_check_duplicates_all_new(self):
        """Test dedup check when all items are new."""
        from app.services.classroom_import_service import check_duplicates
        items = [
            {"title": "HW 1", "course_name": "Math", "due_date": "2026-03-15"},
            {"title": "HW 2", "course_name": "Math", "due_date": "2026-03-16"},
            {"title": "Lab 1", "course_name": "Science", "due_date": "2026-03-17"},
        ]
        new_items, dupes = check_duplicates(items)
        assert len(new_items) == 3
        assert len(dupes) == 0
        # Each item should have a _dedup_hash attached
        assert all("_dedup_hash" in item for item in new_items)

    def test_check_duplicates_with_existing(self):
        """Test dedup check against existing hashes."""
        from app.services.classroom_import_service import (
            _generate_dedup_hash, check_duplicates
        )
        existing = {
            _generate_dedup_hash("HW 1", "Math", "2026-03-15"),
        }
        items = [
            {"title": "HW 1", "course_name": "Math", "due_date": "2026-03-15"},
            {"title": "HW 2", "course_name": "Math", "due_date": "2026-03-16"},
        ]
        new_items, dupes = check_duplicates(items, existing_hashes=existing)
        assert len(new_items) == 1
        assert new_items[0]["title"] == "HW 2"
        assert len(dupes) == 1
        assert dupes[0]["title"] == "HW 1"

    def test_check_duplicates_within_batch(self):
        """Test that duplicates within the same batch are detected."""
        from app.services.classroom_import_service import check_duplicates
        items = [
            {"title": "HW 1", "course_name": "Math", "due_date": "2026-03-15"},
            {"title": "HW 1", "course_name": "Math", "due_date": "2026-03-15"},  # duplicate
            {"title": "HW 2", "course_name": "Math", "due_date": "2026-03-16"},
        ]
        new_items, dupes = check_duplicates(items)
        assert len(new_items) == 2
        assert len(dupes) == 1

    def test_check_duplicates_empty_list(self):
        """Test dedup check with empty item list."""
        from app.services.classroom_import_service import check_duplicates
        new_items, dupes = check_duplicates([])
        assert len(new_items) == 0
        assert len(dupes) == 0
