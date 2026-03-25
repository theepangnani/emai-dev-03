"""study_guides: version, parent_guide_id, content_hash columns."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "version" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))
            logger.info("Added 'version' column to study_guides")
        if "parent_guide_id" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN parent_guide_id INTEGER REFERENCES study_guides(id)"))
            logger.info("Added 'parent_guide_id' column to study_guides")
        if "content_hash" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN content_hash VARCHAR(64)"))
            logger.info("Added 'content_hash' column to study_guides")
        conn.commit()
