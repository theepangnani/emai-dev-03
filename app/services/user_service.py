"""User service for profile management and user-related business logic."""

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.teacher import Teacher
from app.models.student import Student


def ensure_profile_records(db: Session, user: User) -> None:
    """
    Ensure all required profile records exist for user's roles.
    Creates missing Teacher/Student records, never deletes existing ones.
    Idempotent - safe to call multiple times.

    Args:
        db: Database session
        user: User object with roles populated
    """
    roles = user.get_roles_list()

    # Create Teacher profile if user has teacher role
    if UserRole.TEACHER in roles:
        existing = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not existing:
            db.add(Teacher(user_id=user.id))

    # Create Student profile if user has student role
    if UserRole.STUDENT in roles:
        existing = db.query(Student).filter(Student.user_id == user.id).first()
        if not existing:
            db.add(Student(user_id=user.id))

    # Parent role has no dedicated profile table, no action needed

    # Flush to ensure records are created
    db.flush()
