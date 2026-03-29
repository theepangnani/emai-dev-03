"""CSV import service for manual classroom data entry (#2167)."""

import csv
import io
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.assignment import Assignment
from app.models.course import Course, student_courses
from app.models.student import Student
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# Template definitions: column name -> (required, description)
TEMPLATES: dict[str, dict[str, tuple[bool, str]]] = {
    "students": {
        "name": (True, "Student full name"),
        "email": (True, "Student email address"),
        "grade": (False, "Grade level (5-12)"),
    },
    "courses": {
        "name": (True, "Course name"),
        "description": (False, "Course description"),
        "subject": (False, "Subject area (e.g. Math, Science)"),
    },
    "assignments": {
        "title": (True, "Assignment title"),
        "course": (True, "Course name (must match existing course)"),
        "due_date": (False, "Due date (YYYY-MM-DD)"),
        "description": (False, "Assignment description"),
    },
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_ROWS = 500


def get_template_headers(template_type: str) -> list[str]:
    """Return ordered column headers for a template type."""
    if template_type not in TEMPLATES:
        raise ValueError(f"Unknown template type: {template_type}")
    return list(TEMPLATES[template_type].keys())


def generate_template_csv(template_type: str) -> str:
    """Generate a blank CSV with headers for the given template."""
    headers = get_template_headers(template_type)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    return output.getvalue()


def _validate_row(template_type: str, row: dict[str, str], row_num: int) -> list[str]:
    """Validate a single row, returning a list of error messages."""
    errors: list[str] = []
    template = TEMPLATES[template_type]

    for col, (required, _desc) in template.items():
        value = row.get(col, "").strip()
        if required and not value:
            errors.append(f"Row {row_num}: '{col}' is required")

    if template_type == "students":
        email = row.get("email", "").strip()
        if email and not EMAIL_RE.match(email):
            errors.append(f"Row {row_num}: '{email}' is not a valid email")
        grade = row.get("grade", "").strip()
        if grade:
            try:
                g = int(grade)
                if g < 1 or g > 12:
                    errors.append(f"Row {row_num}: grade must be between 1 and 12")
            except ValueError:
                errors.append(f"Row {row_num}: grade must be a number")

    if template_type == "assignments":
        due_date = row.get("due_date", "").strip()
        if due_date:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                errors.append(f"Row {row_num}: due_date must be YYYY-MM-DD format")

    return errors


def parse_csv(template_type: str, file_content: str) -> dict[str, Any]:
    """Parse and validate CSV content.

    Returns dict with:
      - rows: list of parsed row dicts
      - errors: list of error strings (per-row)
      - total: total rows found
      - valid: number of valid rows
    """
    if template_type not in TEMPLATES:
        return {"rows": [], "errors": [f"Unknown template type: {template_type}"], "total": 0, "valid": 0}

    expected_headers = set(TEMPLATES[template_type].keys())

    try:
        reader = csv.DictReader(io.StringIO(file_content))
    except Exception as exc:
        return {"rows": [], "errors": [f"Failed to parse CSV: {exc}"], "total": 0, "valid": 0}

    if reader.fieldnames is None:
        return {"rows": [], "errors": ["CSV file is empty or has no headers"], "total": 0, "valid": 0}

    # Normalize headers (strip whitespace, lowercase)
    normalized_fields = [f.strip().lower() for f in reader.fieldnames]
    missing = expected_headers - set(normalized_fields)
    if missing:
        return {
            "rows": [],
            "errors": [f"Missing required columns: {', '.join(sorted(missing))}"],
            "total": 0,
            "valid": 0,
        }

    rows: list[dict[str, str]] = []
    errors: list[str] = []

    for i, raw_row in enumerate(reader, start=2):  # row 1 is header
        if i - 1 > MAX_ROWS:
            errors.append(f"CSV exceeds maximum of {MAX_ROWS} rows")
            break

        # Normalize keys
        row = {k.strip().lower(): (v or "").strip() for k, v in raw_row.items()}

        # Skip completely empty rows
        if not any(row.get(h) for h in expected_headers):
            continue

        row_errors = _validate_row(template_type, row, i)
        if row_errors:
            errors.extend(row_errors)
        else:
            rows.append({h: row.get(h, "") for h in expected_headers})

    return {
        "rows": rows,
        "errors": errors,
        "total": len(rows) + len([e for e in errors if e.startswith("Row")]),
        "valid": len(rows),
    }


def import_students(db: Session, rows: list[dict[str, str]], created_by_user: User) -> dict[str, Any]:
    """Import student rows into the database."""
    created = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(rows, start=1):
        name = row["name"].strip()
        email = row["email"].strip().lower()
        grade = row.get("grade", "").strip()

        # Check if user already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            skipped += 1
            continue

        try:
            with db.begin_nested():
                temp_password = secrets.token_urlsafe(16)
                user = User(
                    email=email,
                    full_name=name,
                    role=UserRole.STUDENT,
                    roles="student",
                    hashed_password=get_password_hash(temp_password),
                    is_active=True,
                    needs_onboarding=True,
                )
                db.add(user)
                db.flush()

                student = Student(
                    user_id=user.id,
                    grade_level=int(grade) if grade else None,
                )
                db.add(student)
            created += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    db.commit()

    return {"created": created, "skipped": skipped, "errors": errors}


def import_courses(db: Session, rows: list[dict[str, str]], created_by_user: User) -> dict[str, Any]:
    """Import course rows into the database."""
    created = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(rows, start=1):
        name = row["name"].strip()
        description = row.get("description", "").strip() or None
        subject = row.get("subject", "").strip() or None

        # Check for duplicate by name + creator
        existing = db.query(Course).filter(
            Course.name == name,
            Course.created_by_user_id == created_by_user.id,
        ).first()
        if existing:
            skipped += 1
            continue

        try:
            with db.begin_nested():
                course = Course(
                    name=name,
                    description=description,
                    subject=subject,
                    created_by_user_id=created_by_user.id,
                    classroom_type="manual",
                    is_private=True,
                )
                db.add(course)
            created += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    db.commit()

    return {"created": created, "skipped": skipped, "errors": errors}


def import_assignments(db: Session, rows: list[dict[str, str]], created_by_user: User) -> dict[str, Any]:
    """Import assignment rows into the database."""
    created = 0
    skipped = 0
    errors: list[str] = []

    # Pre-fetch courses by name for this user
    user_courses = db.query(Course).filter(
        Course.created_by_user_id == created_by_user.id,
    ).all()
    course_map = {c.name.lower(): c for c in user_courses}

    for i, row in enumerate(rows, start=1):
        title = row["title"].strip()
        course_name = row["course"].strip().lower()
        due_date_str = row.get("due_date", "").strip()
        description = row.get("description", "").strip() or None

        course = course_map.get(course_name)
        if not course:
            errors.append(f"Row {i}: course '{row['course']}' not found")
            continue

        # Parse due date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                errors.append(f"Row {i}: invalid due_date format")
                continue

        try:
            with db.begin_nested():
                assignment = Assignment(
                    title=title,
                    description=description,
                    course_id=course.id,
                    due_date=due_date,
                )
                db.add(assignment)
            created += 1
        except Exception as exc:
            errors.append(f"Row {i}: {exc}")

    db.commit()

    return {"created": created, "skipped": skipped, "errors": errors}
