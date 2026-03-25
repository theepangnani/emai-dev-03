"""study_guides: parent_summary, curriculum_codes (#1973)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_sg = sa_inspect(conn.engine)
        if "study_guides" in inspector_sg.get_table_names():
            existing_cols = {c["name"] for c in inspector_sg.get_columns("study_guides")}
            if "parent_summary" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE study_guides ADD COLUMN parent_summary TEXT"))
                    logger.info("Added 'parent_summary' column to study_guides (#1973)")
                except Exception:
                    conn.rollback()
                conn.commit()
            if "curriculum_codes" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE study_guides ADD COLUMN curriculum_codes TEXT"))
                    logger.info("Added 'curriculum_codes' column to study_guides (#1973)")
                except Exception:
                    conn.rollback()
                conn.commit()
    except Exception as e:
        logger.warning("study_guides strategy columns migration failed (#1973): %s", e)
