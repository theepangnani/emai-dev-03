"""course_contents: text_content, archived_at, last_viewed_at, google_classroom_material_id, file storage, category, display_order, hierarchy columns, is_master type fix, material_group_id."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "course_contents" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "text_content" not in existing_cols:
            conn.execute(text("ALTER TABLE course_contents ADD COLUMN text_content TEXT"))
            logger.info("Added 'text_content' column to course_contents")
        if "archived_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE course_contents ADD COLUMN archived_at {col_type}"))
            logger.info("Added 'archived_at' column to course_contents")
        if "last_viewed_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE course_contents ADD COLUMN last_viewed_at {col_type}"))
            logger.info("Added 'last_viewed_at' column to course_contents")
        conn.commit()
        if "google_classroom_material_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN google_classroom_material_id VARCHAR(255)"))
                logger.info("Added 'google_classroom_material_id' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()
        # File storage columns (#572)
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        for col_name, col_type in [
            ("file_path", "VARCHAR(500)"),
            ("original_filename", "VARCHAR(500)"),
            ("file_size", "INTEGER"),
            ("mime_type", "VARCHAR(100)"),
        ]:
            if col_name not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE course_contents ADD COLUMN {col_name} {col_type}"))
                    logger.info("Added '%s' column to course_contents", col_name)
                except Exception:
                    conn.rollback()
        conn.commit()
        # Material grouping columns (#992)
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "category" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN category VARCHAR(100)"))
                logger.info("Added 'category' column to course_contents")
            except Exception:
                conn.rollback()
        if "display_order" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN display_order INTEGER DEFAULT 0"))
                logger.info("Added 'display_order' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()
        # Material hierarchy columns (#1740)
        existing_cols = {c["name"] for c in inspector.get_columns("course_contents")}
        if "parent_content_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN parent_content_id INTEGER REFERENCES course_contents(id)"))
                logger.info("Added 'parent_content_id' column to course_contents")
            except Exception:
                conn.rollback()
        if "is_master" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN is_master VARCHAR(5) DEFAULT 'false'"))
                logger.info("Added 'is_master' column to course_contents")
            except Exception:
                conn.rollback()
        # Fix is_master column type: BOOLEAN -> VARCHAR(5) for cross-DB compatibility (#1804)
        if "is_master" in existing_cols:
            try:
                if "sqlite" not in settings.database_url:
                    conn.execute(text(
                        "ALTER TABLE course_contents ALTER COLUMN is_master TYPE VARCHAR(5) "
                        "USING CASE WHEN is_master THEN 'true' ELSE 'false' END"
                    ))
                    conn.execute(text(
                        "ALTER TABLE course_contents ALTER COLUMN is_master SET DEFAULT 'false'"
                    ))
                    logger.info("Converted 'is_master' column from BOOLEAN to VARCHAR(5)")
            except Exception:
                conn.rollback()
        conn.commit()
        if "material_group_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE course_contents ADD COLUMN material_group_id INTEGER"))
                logger.info("Added 'material_group_id' column to course_contents")
            except Exception:
                conn.rollback()
        conn.commit()
