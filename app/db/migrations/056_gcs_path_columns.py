"""GCS path columns (#1643) + drop legacy blob columns (#1697)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    # Add gcs_path to source_files
    try:
        conn.execute(text("ALTER TABLE source_files ADD COLUMN gcs_path VARCHAR(500)"))
        conn.commit()
    except Exception:
        conn.rollback()

    # Add gcs_path to content_images
    try:
        conn.execute(text("ALTER TABLE content_images ADD COLUMN gcs_path VARCHAR(500)"))
        conn.commit()
    except Exception:
        conn.rollback()

    # Make file_data nullable
    if "sqlite" not in settings.database_url:
        try:
            conn.execute(text("ALTER TABLE source_files ALTER COLUMN file_data DROP NOT NULL"))
            conn.commit()
        except Exception:
            conn.rollback()

        try:
            conn.execute(text("ALTER TABLE content_images ALTER COLUMN image_data DROP NOT NULL"))
            conn.commit()
        except Exception:
            conn.rollback()

    # Drop legacy blob columns after GCS migration (#1697)
    try:
        conn.execute(text("ALTER TABLE source_files DROP COLUMN IF EXISTS file_data"))
        conn.commit()
    except Exception:
        conn.rollback()

    try:
        conn.execute(text("ALTER TABLE content_images DROP COLUMN IF EXISTS image_data"))
        conn.commit()
    except Exception:
        conn.rollback()
