"""source_type column on course_contents and source_files (#2010)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_st = sa_inspect(conn.engine)
        if "course_contents" in inspector_st.get_table_names():
            existing_cols = {c["name"] for c in inspector_st.get_columns("course_contents")}
            if "source_type" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE course_contents ADD COLUMN source_type VARCHAR(20) DEFAULT 'local_upload'"))
                    conn.commit()
                    logger.info("Added 'source_type' column to course_contents (#2010)")
                except Exception:
                    conn.rollback()
        if "source_files" in inspector_st.get_table_names():
            existing_cols = {c["name"] for c in inspector_st.get_columns("source_files")}
            if "source_type" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE source_files ADD COLUMN source_type VARCHAR(20) DEFAULT 'local_upload'"))
                    conn.commit()
                    logger.info("Added 'source_type' column to source_files (#2010)")
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.warning("source_type column migration failed (#2010): %s", e)
