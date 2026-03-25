"""is_master String->Boolean migration (#2025)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_b0 = sa_inspect(conn.engine)
        if "course_contents" in inspector_b0.get_table_names():
            col_info = {c["name"]: c for c in inspector_b0.get_columns("course_contents")}
            if "is_master" in col_info:
                col_type = str(col_info["is_master"]["type"])
                if "VARCHAR" in col_type.upper() or "CHAR" in col_type.upper():
                    try:
                        if "sqlite" not in settings.database_url:
                            # PostgreSQL: convert in-place
                            conn.execute(text(
                                "ALTER TABLE course_contents ALTER COLUMN is_master TYPE BOOLEAN "
                                "USING CASE WHEN is_master = 'true' THEN TRUE ELSE FALSE END"
                            ))
                            conn.execute(text(
                                "ALTER TABLE course_contents ALTER COLUMN is_master SET DEFAULT FALSE"
                            ))
                        else:
                            # SQLite: update any remaining string values to proper integers
                            conn.execute(text(
                                "UPDATE course_contents SET is_master = (is_master = 'true') "
                                "WHERE typeof(is_master) = 'text'"
                            ))
                        conn.commit()
                        logger.info("Migrated 'is_master' column from VARCHAR to BOOLEAN (#2025)")
                    except Exception:
                        conn.rollback()
            # Clean up temp column if previous partial migration left it
            if "is_master_bool" in col_info:
                try:
                    if "sqlite" not in settings.database_url:
                        conn.execute(text("ALTER TABLE course_contents DROP COLUMN is_master_bool"))
                    else:
                        conn.execute(text("ALTER TABLE course_contents DROP COLUMN is_master_bool"))
                    conn.commit()
                    logger.info("Dropped leftover 'is_master_bool' column (#2025)")
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.warning("is_master Boolean migration failed (#2025): %s", e)
