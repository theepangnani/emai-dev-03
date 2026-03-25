"""Create waitlist table (#1107) + rename email_validated -> invite_link_clicked (#1126)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        if "waitlist" not in inspector.get_table_names():
            is_sqlite = "sqlite" in settings.database_url
            datetime_type = "DATETIME" if is_sqlite else "TIMESTAMPTZ"
            bool_default = "DEFAULT 0" if is_sqlite else "DEFAULT FALSE"
            conn.execute(text(f"""
                CREATE TABLE waitlist (
                    id INTEGER PRIMARY KEY {'AUTOINCREMENT' if is_sqlite else 'GENERATED ALWAYS AS IDENTITY'},
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    roles JSON,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    admin_notes TEXT,
                    invite_token VARCHAR(255) UNIQUE,
                    invite_token_expires_at {datetime_type},
                    invite_link_clicked BOOLEAN {bool_default},
                    approved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    approved_at {datetime_type},
                    registered_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    reminder_sent_at {datetime_type},
                    created_at {datetime_type} DEFAULT CURRENT_TIMESTAMP,
                    updated_at {datetime_type} DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX ix_waitlist_email ON waitlist (email)"))
            conn.execute(text("CREATE INDEX ix_waitlist_invite_token ON waitlist (invite_token)"))
            conn.execute(text("CREATE INDEX ix_waitlist_status ON waitlist (status)"))
            logger.info("Created 'waitlist' table (#1107)")
        conn.commit()
    except Exception:
        conn.rollback()

    # Rename email_validated -> invite_link_clicked (#1126)
    if "waitlist" in inspector.get_table_names():
        waitlist_cols = {c["name"] for c in inspector.get_columns("waitlist")}
        if "email_validated" in waitlist_cols and "invite_link_clicked" not in waitlist_cols:
            try:
                conn.execute(text("ALTER TABLE waitlist RENAME COLUMN email_validated TO invite_link_clicked"))
                logger.info("Renamed 'email_validated' -> 'invite_link_clicked' on waitlist (#1126)")
            except Exception:
                conn.rollback()
            conn.commit()
