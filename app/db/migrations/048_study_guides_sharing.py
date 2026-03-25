"""study_guides: sharing columns (#1414)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "shared_with_user_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN shared_with_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
                logger.info("Added 'shared_with_user_id' column to study_guides (#1414)")
            except Exception:
                conn.rollback()
            conn.commit()

        if "shared_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE study_guides ADD COLUMN shared_at {col_type}"))
                logger.info("Added 'shared_at' column to study_guides (#1414)")
            except Exception:
                conn.rollback()
            conn.commit()

        if "viewed_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE study_guides ADD COLUMN viewed_at {col_type}"))
                logger.info("Added 'viewed_at' column to study_guides (#1414)")
            except Exception:
                conn.rollback()
            conn.commit()

        if "viewed_count" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN viewed_count INTEGER DEFAULT 0"))
                logger.info("Added 'viewed_count' column to study_guides (#1414)")
            except Exception:
                conn.rollback()
            conn.commit()
