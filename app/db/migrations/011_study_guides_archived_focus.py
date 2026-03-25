"""study_guides: archived_at and focus_prompt columns."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "archived_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE study_guides ADD COLUMN archived_at {col_type}"))
            logger.info("Added 'archived_at' column to study_guides")
        conn.commit()

    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "focus_prompt" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN focus_prompt VARCHAR(2000)"))
                logger.info("Added 'focus_prompt' column to study_guides")
            except Exception:
                conn.rollback()
        conn.commit()
