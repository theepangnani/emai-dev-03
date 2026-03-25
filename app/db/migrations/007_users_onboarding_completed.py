"""users: onboarding_completed column (#413/#414)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "onboarding_completed" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE"))
                # Backfill: users who already completed onboarding (needs_onboarding=0 AND have a role)
                conn.execute(text(
                    "UPDATE users SET onboarding_completed = TRUE "
                    "WHERE needs_onboarding = FALSE AND role IS NOT NULL"
                ))
                logger.info("Added 'onboarding_completed' column to users and backfilled")
            except Exception:
                conn.rollback()
            conn.commit()
