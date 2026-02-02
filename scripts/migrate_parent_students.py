"""Optional migration script: copy parent_id data from students table into parent_students join table.

Run this if you have existing data and don't want to delete the database.
Usage: python -m scripts.migrate_parent_students
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.database import SessionLocal, engine, Base

# Ensure all models are imported so tables are created
from app.models import *  # noqa: F401, F403


def migrate():
    # Create any new tables (parent_students)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if old parent_id column exists
        result = db.execute(text("PRAGMA table_info(students)")).fetchall()
        columns = [row[1] for row in result]

        if "parent_id" not in columns:
            print("No parent_id column found in students table. Nothing to migrate.")
            return

        # Copy parent_id links into parent_students
        rows = db.execute(
            text("SELECT id, parent_id FROM students WHERE parent_id IS NOT NULL")
        ).fetchall()

        migrated = 0
        for student_id, parent_id in rows:
            # Check if link already exists
            existing = db.execute(
                text(
                    "SELECT 1 FROM parent_students WHERE parent_id = :pid AND student_id = :sid"
                ),
                {"pid": parent_id, "sid": student_id},
            ).first()

            if not existing:
                db.execute(
                    text(
                        "INSERT INTO parent_students (parent_id, student_id, relationship_type) "
                        "VALUES (:pid, :sid, 'guardian')"
                    ),
                    {"pid": parent_id, "sid": student_id},
                )
                migrated += 1

        db.commit()
        print(f"Migrated {migrated} parent-student links to join table.")
        print("You can now safely drop the parent_id column from the students table.")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
