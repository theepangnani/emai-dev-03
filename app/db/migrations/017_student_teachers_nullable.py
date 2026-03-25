"""student_teachers: make teacher_user_id nullable."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "student_teachers" in inspector.get_table_names():
        if "sqlite" not in settings.database_url:
            try:
                conn.execute(text("ALTER TABLE student_teachers ALTER COLUMN teacher_user_id DROP NOT NULL"))
                logger.info("Made 'teacher_user_id' nullable on student_teachers table")
            except Exception:
                conn.rollback()  # Required: clear aborted transaction state
        conn.commit()
