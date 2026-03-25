"""student_assignments: submission fields (#839)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "student_assignments" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("student_assignments")}
        if "submission_file_path" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN submission_file_path VARCHAR(500)"))
                logger.info("Added 'submission_file_path' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()

        if "submission_file_name" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN submission_file_name VARCHAR(255)"))
                logger.info("Added 'submission_file_name' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()

        if "submission_notes" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN submission_notes TEXT"))
                logger.info("Added 'submission_notes' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()

        if "is_late" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE student_assignments ADD COLUMN is_late BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'is_late' column to student_assignments")
            except Exception:
                conn.rollback()
        conn.commit()
