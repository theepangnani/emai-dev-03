"""ai_usage_history: token/cost tracking (#1650) + regeneration tracking (#1651)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    inspector_local = sa_inspect(conn.engine)
    if "ai_usage_history" in inspector_local.get_table_names():
        existing_cols = {c["name"] for c in inspector_local.get_columns("ai_usage_history")}
        new_cols = [
            ("prompt_tokens", "INTEGER"),
            ("completion_tokens", "INTEGER"),
            ("total_tokens", "INTEGER"),
            ("estimated_cost_usd", "FLOAT"),
            ("model_name", "VARCHAR(50)"),
            ("parent_generation_id", "INTEGER REFERENCES ai_usage_history(id)"),
        ]
        for col_name, col_def in new_cols:
            if col_name not in existing_cols:
                try:
                    conn.execute(text(f"ALTER TABLE ai_usage_history ADD COLUMN {col_name} {col_def}"))
                    logger.info("Added '%s' column to ai_usage_history (S6.54)", col_name)
                except Exception:
                    conn.rollback()
        conn.commit()
        if "is_regeneration" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE ai_usage_history ADD COLUMN is_regeneration BOOLEAN NOT NULL DEFAULT FALSE"))
                logger.info("Added 'is_regeneration' column to ai_usage_history (S6.54)")
            except Exception:
                conn.rollback()
            conn.commit()
