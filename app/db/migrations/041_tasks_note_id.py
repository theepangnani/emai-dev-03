"""tasks: note_id column (#1087)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "tasks" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "note_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN note_id INTEGER REFERENCES notes(id) ON DELETE SET NULL"))
                logger.info("Added 'note_id' column to tasks (#1087)")
            except Exception:
                conn.rollback()
        conn.commit()
