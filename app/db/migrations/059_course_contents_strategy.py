"""course_contents: document_type, study_goal, study_goal_text (#1973)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_cc = sa_inspect(conn.engine)
        if "course_contents" in inspector_cc.get_table_names():
            existing_cols = {c["name"] for c in inspector_cc.get_columns("course_contents")}
            if "document_type" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE course_contents ADD COLUMN document_type VARCHAR(30)"))
                    logger.info("Added 'document_type' column to course_contents (#1973)")
                except Exception:
                    conn.rollback()
                conn.commit()
            if "study_goal" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE course_contents ADD COLUMN study_goal VARCHAR(30)"))
                    logger.info("Added 'study_goal' column to course_contents (#1973)")
                except Exception:
                    conn.rollback()
                conn.commit()
            if "study_goal_text" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE course_contents ADD COLUMN study_goal_text VARCHAR(200)"))
                    logger.info("Added 'study_goal_text' column to course_contents (#1973)")
                except Exception:
                    conn.rollback()
                conn.commit()
    except Exception as e:
        logger.warning("course_contents strategy columns migration failed (#1973): %s", e)
