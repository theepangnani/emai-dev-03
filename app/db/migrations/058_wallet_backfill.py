"""Backfill wallets for existing users without one (#1387)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_local = sa_inspect(conn.engine)
        if "wallets" in inspector_local.get_table_names():
            result = conn.execute(text(
                "INSERT INTO wallets (user_id, package, package_credits, purchased_credits, "
                "auto_refill_enabled, auto_refill_threshold_cents, auto_refill_amount_cents) "
                "SELECT id, 'free', 0, 0, FALSE, 0, 500 FROM users "
                "WHERE id NOT IN (SELECT user_id FROM wallets)"
            ))
            if result.rowcount:
                logger.info("Backfilled %d wallets for existing users", result.rowcount)
            conn.commit()
    except Exception as e:
        logger.warning("Wallet backfill migration: %s", e)
