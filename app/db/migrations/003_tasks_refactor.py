"""tasks: created_by_user_id, assigned_to_user_id, priority, category, archived_at, linked entity FKs, nullable parent_id."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "tasks" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "created_by_user_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN created_by_user_id INTEGER REFERENCES users(id)"))
            # Migrate existing parent_id data
            conn.execute(text("UPDATE tasks SET created_by_user_id = parent_id WHERE created_by_user_id IS NULL AND parent_id IS NOT NULL"))
            logger.info("Added 'created_by_user_id' column to tasks (migrated from parent_id)")
        if "assigned_to_user_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN assigned_to_user_id INTEGER REFERENCES users(id)"))
            # Migrate existing student_id data: resolve student.user_id
            conn.execute(text("UPDATE tasks SET assigned_to_user_id = (SELECT s.user_id FROM students s WHERE s.id = tasks.student_id) WHERE assigned_to_user_id IS NULL AND student_id IS NOT NULL"))
            logger.info("Added 'assigned_to_user_id' column to tasks (migrated from student_id)")
        if "priority" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN priority VARCHAR(10) DEFAULT 'medium'"))
            logger.info("Added 'priority' column to tasks")
        if "category" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN category VARCHAR(50)"))
            logger.info("Added 'category' column to tasks")
        if "archived_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE tasks ADD COLUMN archived_at {col_type}"))
            logger.info("Added 'archived_at' column to tasks")
        # Linked entity FK columns
        if "course_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN course_id INTEGER REFERENCES courses(id)"))
            logger.info("Added 'course_id' column to tasks")
        if "course_content_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN course_content_id INTEGER REFERENCES course_contents(id)"))
            logger.info("Added 'course_content_id' column to tasks")
        if "study_guide_id" not in existing_cols:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN study_guide_id INTEGER REFERENCES study_guides(id)"))
            logger.info("Added 'study_guide_id' column to tasks")
        # Make parent_id nullable (was NOT NULL in original schema) — PostgreSQL only
        if "sqlite" not in settings.database_url:
            try:
                conn.execute(text("ALTER TABLE tasks ALTER COLUMN parent_id DROP NOT NULL"))
                logger.info("Made 'parent_id' nullable on tasks table")
            except Exception:
                pass  # Already nullable or not applicable
        conn.commit()
