"""CASCADE/SET NULL FK rules and unique constraints (#145, #146, #187)."""

from sqlalchemy import text, inspect as sa_inspect
from app.core.config import settings as app_settings


def _apply_cascade_and_unique_migration(conn, inspector, logger):
    """Add CASCADE/SET NULL FK rules and unique constraints (idempotent)."""
    is_sqlite = "sqlite" in app_settings.database_url
    table_names = inspector.get_table_names()

    # Check if migration already applied by looking for our unique index
    if "parent_students" in table_names:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("parent_students") if idx.get("name")}
        if "uq_parent_students_pair" in existing_indexes:
            return  # Already migrated

    logger.info("Applying CASCADE/UNIQUE migration (#145, #146, #187)...")

    # --- Deduplicate + add UNIQUE CONSTRAINTS ---
    _dedup_and_add_unique = [
        ("parent_students", ["parent_id", "student_id"], "uq_parent_students_pair"),
        ("student_teachers", ["student_id", "teacher_email"], "uq_student_teachers_pair"),
        ("student_assignments", ["student_id", "assignment_id"], "uq_student_assignment_pair"),
    ]

    for table, cols, constraint_name in _dedup_and_add_unique:
        if table not in table_names:
            continue
        col_list = ", ".join(cols)
        # Remove duplicates, keeping the earliest row
        conn.execute(text(
            f"DELETE FROM {table} WHERE id NOT IN ("
            f"SELECT MIN(id) FROM {table} GROUP BY {col_list})"
        ))
        if is_sqlite:
            conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {constraint_name} ON {table}({col_list})"
            ))
        else:
            try:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} UNIQUE ({col_list})"
                ))
            except Exception:
                pass  # Already exists
        logger.info(f"Added unique constraint {constraint_name} on {table}")

    # --- CASCADE FK rules (PostgreSQL only) ---
    if not is_sqlite:
        fk_changes = [
            # (table, column, references, ondelete)
            ("assignments", "course_id", "courses(id)", "CASCADE"),
            ("course_contents", "course_id", "courses(id)", "CASCADE"),
            ("messages", "conversation_id", "conversations(id)", "CASCADE"),
            ("messages", "sender_id", "users(id)", "CASCADE"),
            ("notifications", "user_id", "users(id)", "CASCADE"),
            ("students", "user_id", "users(id)", "CASCADE"),
            ("teachers", "user_id", "users(id)", "CASCADE"),
            ("study_guides", "user_id", "users(id)", "CASCADE"),
            ("teacher_communications", "user_id", "users(id)", "CASCADE"),
            ("tasks", "created_by_user_id", "users(id)", "CASCADE"),
            ("parent_students", "parent_id", "users(id)", "CASCADE"),
            ("parent_students", "student_id", "students(id)", "CASCADE"),
            ("student_courses", "student_id", "students(id)", "CASCADE"),
            ("student_courses", "course_id", "courses(id)", "CASCADE"),
            ("student_assignments", "student_id", "students(id)", "CASCADE"),
            ("student_assignments", "assignment_id", "assignments(id)", "CASCADE"),
            ("student_teachers", "student_id", "students(id)", "CASCADE"),
            ("conversations", "participant_1_id", "users(id)", "CASCADE"),
            ("conversations", "participant_2_id", "users(id)", "CASCADE"),
            ("courses", "teacher_id", "teachers(id)", "SET NULL"),
            ("courses", "created_by_user_id", "users(id)", "SET NULL"),
            ("tasks", "assigned_to_user_id", "users(id)", "SET NULL"),
            ("tasks", "course_id", "courses(id)", "SET NULL"),
            ("tasks", "course_content_id", "course_contents(id)", "SET NULL"),
            ("tasks", "study_guide_id", "study_guides(id)", "SET NULL"),
            ("tasks", "parent_id", "users(id)", "SET NULL"),
            ("tasks", "student_id", "students(id)", "SET NULL"),
            ("study_guides", "assignment_id", "assignments(id)", "SET NULL"),
            ("study_guides", "course_id", "courses(id)", "SET NULL"),
            ("study_guides", "course_content_id", "course_contents(id)", "SET NULL"),
            ("study_guides", "parent_guide_id", "study_guides(id)", "SET NULL"),
            ("invites", "invited_by_user_id", "users(id)", "SET NULL"),
            ("audit_logs", "user_id", "users(id)", "SET NULL"),
            ("student_teachers", "teacher_user_id", "users(id)", "SET NULL"),
            ("student_teachers", "added_by_user_id", "users(id)", "SET NULL"),
            ("conversations", "student_id", "students(id)", "SET NULL"),
            ("course_contents", "created_by_user_id", "users(id)", "SET NULL"),
        ]

        for table, column, references, ondelete in fk_changes:
            if table not in table_names:
                continue
            try:
                fks = inspector.get_foreign_keys(table)
                for fk in fks:
                    if column in fk.get("constrained_columns", []):
                        fk_name = fk.get("name")
                        if fk_name:
                            conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {fk_name}"))
                        break
                constraint_name = f"fk_{table}_{column}"
                conn.execute(text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
                    f"FOREIGN KEY ({column}) REFERENCES {references} ON DELETE {ondelete}"
                ))
            except Exception as e:
                logger.warning(f"Failed to update FK {table}.{column}: {e}")

        # Nullability changes for SET NULL columns
        for table, column in [
            ("invites", "invited_by_user_id"),
            ("course_contents", "created_by_user_id"),
            ("student_teachers", "added_by_user_id"),
        ]:
            if table in table_names:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} DROP NOT NULL"))
                except Exception:
                    pass  # Already nullable

    logger.info("CASCADE/UNIQUE migration complete")


def up(conn, inspector, is_pg, settings, logger):
    _apply_cascade_and_unique_migration(conn, inspector, logger)
    conn.commit()
