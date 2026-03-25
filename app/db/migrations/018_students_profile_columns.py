"""students: profile detail columns (#267, #303)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "students" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        col_type_date = "DATE"
        col_type_ts = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
        new_student_cols = [
            ("date_of_birth", col_type_date),
            ("phone", "VARCHAR(30)"),
            ("address", "VARCHAR(255)"),
            ("city", "VARCHAR(100)"),
            ("province", "VARCHAR(100)"),
            ("postal_code", "VARCHAR(20)"),
            ("notes", "TEXT"),
            ("updated_at", col_type_ts),
        ]
        for col_name, col_type in new_student_cols:
            if col_name not in existing_cols:
                try:
                    if is_pg_flag:
                        conn.execute(text(f"ALTER TABLE students ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    else:
                        conn.execute(text(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"Added '{col_name}' column to students")
                except Exception:
                    conn.rollback()  # Column may already exist from concurrent instance
        conn.commit()
