"""courses: classroom_type column (Phase 1 New Workflow) + backfill."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "classroom_type" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE courses ADD COLUMN classroom_type VARCHAR(20)"))
                logger.info("Added 'classroom_type' column to courses")
            except Exception:
                conn.rollback()
        conn.commit()
        # Backfill NULL classroom_type rows (fix for courses added before column had a default)
        try:
            conn.execute(text("UPDATE courses SET classroom_type = 'manual' WHERE classroom_type IS NULL"))
            logger.info("Backfilled NULL classroom_type values to 'manual'")
        except Exception:
            conn.rollback()
        conn.commit()
