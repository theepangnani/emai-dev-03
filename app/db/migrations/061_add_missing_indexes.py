"""Add missing indexes on frequently-queried columns (#1961)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    _index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)",
        "CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active)",
        "CREATE INDEX IF NOT EXISTS ix_teachers_user_id ON teachers (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_teachers_is_shadow ON teachers (is_shadow)",
        "CREATE INDEX IF NOT EXISTS ix_calendar_feeds_user_id ON calendar_feeds (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_calendar_events_user_id ON calendar_events (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_calendar_events_feed_id ON calendar_events (feed_id)",
        "CREATE INDEX IF NOT EXISTS ix_calendar_events_feed_start ON calendar_events (feed_id, start_date)",
        "CREATE INDEX IF NOT EXISTS ix_ai_limit_requests_status ON ai_limit_requests (status)",
        "CREATE INDEX IF NOT EXISTS ix_student_assignments_status ON student_assignments (status)",
        "CREATE INDEX IF NOT EXISTS ix_broadcasts_sender_id ON broadcasts (sender_id)",
        "CREATE INDEX IF NOT EXISTS ix_package_tiers_is_active ON package_tiers (is_active)",
        "CREATE INDEX IF NOT EXISTS ix_credit_packages_is_active ON credit_packages (is_active)",
        "CREATE INDEX IF NOT EXISTS ix_token_blacklist_user_id ON token_blacklist (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_study_guides_guide_type ON study_guides (guide_type)",
        "CREATE INDEX IF NOT EXISTS ix_help_articles_role ON help_articles (role)",
    ]
    for stmt in _index_statements:
        try:
            conn.execute(text(stmt))
            conn.commit()
        except Exception:
            conn.rollback()
    logger.info("Applied missing database indexes (#1961)")
