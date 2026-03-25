"""study_guides: is_truncated (#1645), relationship_type + generation_context (#1594)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "is_truncated" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN is_truncated BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'is_truncated' column to study_guides (#1645)")
            except Exception:
                conn.rollback()
            conn.commit()

    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "relationship_type" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN relationship_type VARCHAR(20) DEFAULT 'version' NOT NULL"))
                logger.info("Added 'relationship_type' column to study_guides (#1594)")
            except Exception:
                conn.rollback()
            conn.commit()
        if "generation_context" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE study_guides ADD COLUMN generation_context TEXT"))
                logger.info("Added 'generation_context' column to study_guides (#1594)")
            except Exception:
                conn.rollback()
            conn.commit()
