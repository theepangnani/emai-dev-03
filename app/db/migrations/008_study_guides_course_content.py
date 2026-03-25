"""study_guides: course_content_id column."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "study_guides" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("study_guides")}
        if "course_content_id" not in existing_cols:
            conn.execute(text("ALTER TABLE study_guides ADD COLUMN course_content_id INTEGER REFERENCES course_contents(id)"))
            logger.info("Added 'course_content_id' column to study_guides")
        conn.commit()
