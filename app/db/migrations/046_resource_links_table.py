"""Resource links table safety migration (#1319)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        if "sqlite" not in settings.database_url:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resource_links (
                    id SERIAL PRIMARY KEY,
                    course_content_id INTEGER NOT NULL REFERENCES course_contents(id) ON DELETE CASCADE,
                    url VARCHAR(2048) NOT NULL,
                    resource_type VARCHAR(20) NOT NULL,
                    title VARCHAR(500),
                    topic_heading VARCHAR(500),
                    description TEXT,
                    thumbnail_url VARCHAR(2048),
                    youtube_video_id VARCHAR(20),
                    display_order INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resource_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_content_id INTEGER NOT NULL REFERENCES course_contents(id) ON DELETE CASCADE,
                    url VARCHAR(2048) NOT NULL,
                    resource_type VARCHAR(20) NOT NULL,
                    title VARCHAR(500),
                    topic_heading VARCHAR(500),
                    description TEXT,
                    thumbnail_url VARCHAR(2048),
                    youtube_video_id VARCHAR(20),
                    display_order INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
        conn.commit()
        logger.info("resource_links table ensured")
    except Exception:
        conn.rollback()
