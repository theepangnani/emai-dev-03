"""holiday_dates: rename columns from old schema (#2024)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_hd = sa_inspect(conn.engine)
        if "holiday_dates" in inspector_hd.get_table_names():
            existing_cols = {c["name"] for c in inspector_hd.get_columns("holiday_dates")}
            if "board_name" in existing_cols and "board" not in existing_cols:
                conn.execute(text("ALTER TABLE holiday_dates RENAME COLUMN board_name TO board"))
                conn.commit()
                logger.info("Renamed holiday_dates.board_name -> board (#2024)")
            if "description" in existing_cols and "name" not in existing_cols:
                conn.execute(text("ALTER TABLE holiday_dates RENAME COLUMN description TO name"))
                conn.commit()
                logger.info("Renamed holiday_dates.description -> name (#2024)")
    except Exception as e:
        logger.warning("holiday_dates column rename migration failed (#2024): %s", e)
