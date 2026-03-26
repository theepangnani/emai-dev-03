"""CSV import service for manual classroom data entry (#2167)."""

import csv
import io
import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.course import Course, CLASSROOM_TYPE_MANUAL
from app.models.assignment import Assignment
from app.models.user import User, UserRole
from app.models.student import Student

# Template definitions: column headers for each template type
TEMPLATES = {
    "students": ["name", "email", "grade"],
    "courses": ["name", "description", "subject"],
    "assignments": ["title", "course_name", "due_date", "description"],
}


def get_template_csv(template_type: str) -> str:
    """Return a blank CSV string with headers for the given template type."""
    if template_type not in TEMPLATES:
        raise ValueError(f"Unknown template type: {template_type}")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(TEMPLATES[template_type])
    return output.getvalue()


def _validate_student_row(row: dict, row_num: int) -> list[str]:
    errors = []
    name = (row.get("name") or "").strip()
    email = (row.get("email") or "").strip()
    grade = (row.get("grade") or "").strip()
    if not name:
        errors.append(f"Row {row_num}: name is required")
    if not email:
        errors.append(f"Row {row_num}: email is required")
    elif "@" not in email:
        errors.append(f"Row {row_num}: invalid email format")
    if grade:
        try:
            g = int(grade)
            if g < 1 or g > 12:
                errors.append(f"Row {row_num}: grade must be between 1 and 12")
        except ValueError:
            errors.append(f"Row {row_num}: grade must be a number")
    return errors


def _validate_course_row(row: dict, row_num: int) -> list[str]:
    errors = []
    name = (row.get("name") or "").strip()
    if not name:
        errors.append(f"Row {row_num}: name is required")
    if len(name) > 200:
        errors.append(f"Row {row_num}: name must be 200 characters or less")
    desc = (row.get("description") or "").strip()
    if len(desc) > 2000:
        errors.append(f"Row {row_num}: description must be 2000 characters or less")
    return errors


def _validate_assignment_row(row: dict, row_num: int) -> list[str]:
    errors = []
    title = (row.get("title") or "").strip()
    course_name = (row.get("course_name") or "").strip()
    due_date = (row.get("due_date") or "").strip()
    if not title:
        errors.append(f"Row {row_num}: title is required")
    if not course_name:
        errors.append(f"Row {row_num}: course_name is required")
    if due_date:
        try:
            datetime.fromisoformat(due_date)
        except ValueError:
            errors.append(f"Row {row_num}: due_date must be ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    return errors


def _import_students(db: Session, rows: list[dict], user: User) -> dict:
    """Import student rows. Creates User + Student records for each valid row."""
    from app.core.security import get_password_hash

    errors: list[str] = []
    imported = 0

    for i, row in enumerate(rows, start=2):  # Row 2 = first data row (after header)
        row_errors = _validate_student_row(row, i)
        if row_errors:
            errors.extend(row_errors)
            continue

        name = row["name"].strip()
        email = row["email"].strip().lower()
        grade = (row.get("grade") or "").strip()

        # Check if user with this email already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            errors.append(f"Row {i}: user with email {email} already exists")
            continue

        # Create user with student role and unique random password
        temp_password = secrets.token_urlsafe(16)
        new_user = User(
            email=email,
            full_name=name,
            role=UserRole.STUDENT,
            hashed_password=get_password_hash(temp_password),
            needs_onboarding=True,
        )
        db.add(new_user)
        db.flush()

        student = Student(
            user_id=new_user.id,
            grade_level=int(grade) if grade else None,
        )
        db.add(student)
        imported += 1

    if imported > 0:
        db.commit()

    return {"imported": imported, "errors": errors}


def _import_courses(db: Session, rows: list[dict], user: User) -> dict:
    """Import course rows. Creates Course records owned by the current user."""
    errors: list[str] = []
    imported = 0

    for i, row in enumerate(rows, start=2):
        row_errors = _validate_course_row(row, i)
        if row_errors:
            errors.extend(row_errors)
            continue

        name = row["name"].strip()
        description = (row.get("description") or "").strip() or None
        subject = (row.get("subject") or "").strip() or None

        course = Course(
            name=name,
            description=description,
            subject=subject,
            classroom_type=CLASSROOM_TYPE_MANUAL,
            created_by_user_id=user.id,
            is_private=True,
        )
        db.add(course)
        imported += 1

    if imported > 0:
        db.commit()

    return {"imported": imported, "errors": errors}


def _import_assignments(db: Session, rows: list[dict], user: User) -> dict:
    """Import assignment rows. Looks up course by name (owned by user)."""
    errors: list[str] = []
    imported = 0

    for i, row in enumerate(rows, start=2):
        row_errors = _validate_assignment_row(row, i)
        if row_errors:
            errors.extend(row_errors)
            continue

        title = row["title"].strip()
        course_name = row["course_name"].strip()
        due_date_str = (row.get("due_date") or "").strip()
        description = (row.get("description") or "").strip() or None

        # Find course by name owned by user
        course = (
            db.query(Course)
            .filter(Course.name == course_name, Course.created_by_user_id == user.id)
            .first()
        )
        if not course:
            errors.append(f"Row {i}: course '{course_name}' not found (must be a course you created)")
            continue

        due_date = None
        if due_date_str:
            due_date = datetime.fromisoformat(due_date_str)

        assignment = Assignment(
            title=title,
            description=description,
            course_id=course.id,
            due_date=due_date,
        )
        db.add(assignment)
        imported += 1

    if imported > 0:
        db.commit()

    return {"imported": imported, "errors": errors}


def import_csv(db: Session, template_type: str, file_content: bytes, user: User) -> dict:
    """Parse and import a CSV file of the given template type.

    Returns {"imported": int, "errors": list[str]}.
    """
    if template_type not in TEMPLATES:
        return {"imported": 0, "errors": [f"Unknown template type: {template_type}"]}

    expected_headers = TEMPLATES[template_type]

    try:
        text = file_content.decode("utf-8-sig")  # Handle BOM from Excel
    except UnicodeDecodeError:
        return {"imported": 0, "errors": ["File must be UTF-8 encoded"]}

    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        return {"imported": 0, "errors": ["CSV file is empty"]}

    # Normalize headers (strip whitespace, lowercase)
    actual_headers = [h.strip().lower() for h in reader.fieldnames]
    missing = [h for h in expected_headers if h not in actual_headers]
    if missing:
        return {"imported": 0, "errors": [f"Missing required columns: {', '.join(missing)}"]}

    # Normalize row keys
    rows = []
    for row in reader:
        normalized = {k.strip().lower(): v for k, v in row.items()}
        # Skip completely empty rows
        if all(not (v or "").strip() for v in normalized.values()):
            continue
        rows.append(normalized)

    if not rows:
        return {"imported": 0, "errors": ["CSV file has no data rows"]}

    importers = {
        "students": _import_students,
        "courses": _import_courses,
        "assignments": _import_assignments,
    }

    return importers[template_type](db, rows, user)
