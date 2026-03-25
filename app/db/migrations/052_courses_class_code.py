"""courses: class_code column + backfill + unique index."""

import random
import string

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "class_code" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE courses ADD COLUMN class_code VARCHAR(10)"))
                logger.info("Added 'class_code' column to courses")
            except Exception:
                conn.rollback()
            conn.commit()
            # Backfill existing courses with generated class codes
            try:
                rows = conn.execute(text("SELECT id FROM courses WHERE class_code IS NULL")).fetchall()
                existing_codes: set[str] = set()
                chars = string.ascii_uppercase + string.digits
                for row in rows:
                    for _ in range(100):
                        code = ''.join(random.choices(chars, k=6))
                        if code not in existing_codes:
                            break
                    existing_codes.add(code)
                    conn.execute(text("UPDATE courses SET class_code = :code WHERE id = :id"), {"code": code, "id": row[0]})
                conn.commit()
                logger.info("Backfilled class_code for %d existing courses", len(rows))
            except Exception:
                conn.rollback()
            # Create unique index
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_courses_class_code ON courses(class_code)"))
                conn.commit()
                logger.info("Created unique index on courses.class_code")
            except Exception:
                conn.rollback()
