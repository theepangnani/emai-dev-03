"""bug_reports: widen screenshot_url from VARCHAR(500) to TEXT (#2101)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_local = sa_inspect(conn.engine)
        if "bug_reports" in inspector_local.get_table_names():
            if "sqlite" not in settings.database_url:
                try:
                    conn.execute(text("ALTER TABLE bug_reports ALTER COLUMN screenshot_url TYPE TEXT"))
                    conn.commit()
                    logger.info("Widened bug_reports.screenshot_url to TEXT (#2101)")
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.warning("bug_reports screenshot_url migration failed (#2101): %s", e)
