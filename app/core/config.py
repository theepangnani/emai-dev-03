import secrets

from pydantic_settings import BaseSettings


def _generate_dev_secret() -> str:
    """Generate a random secret for local development only."""
    return secrets.token_hex(32)


class Settings(BaseSettings):
    # App
    app_name: str = "EMAI"
    debug: bool = False
    environment: str = "development"  # development, production
    log_level: str = ""  # DEBUG, INFO, WARNING, ERROR, CRITICAL (empty = auto based on environment)
    log_to_file: bool = True  # Enable file logging

    # Database (SQLite for local dev, PostgreSQL for production)
    database_url: str = "sqlite:///./emai.db"

    # JWT — no default; must be set via SECRET_KEY env var in production.
    # In development, a random key is generated per-process if not set.
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/google/callback"

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # CORS (comma-separated origins, empty = allow all in development)
    allowed_origins: str = ""

    # Anthropic Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-5-20250929"

    # Study guide limits
    max_study_guides_per_student: int = 100
    max_study_guides_per_parent: int = 200

    # Audit logging
    audit_log_enabled: bool = True
    audit_log_retention_days: int = 90

    # Email
    sendgrid_api_key: str = ""
    from_email: str = "noreply@classbridge.app"
    # Gmail SMTP (used when SendGrid is not configured)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # Gmail App Password

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Validate secret key
_KNOWN_WEAK_KEYS = {"your-secret-key-change-in-production", "changeme", "secret", ""}

if settings.secret_key in _KNOWN_WEAK_KEYS:
    if settings.environment == "production":
        raise RuntimeError(
            "SECRET_KEY is not set or uses a known weak default. "
            "Set a strong SECRET_KEY env var (e.g. `openssl rand -hex 32`)."
        )
    # Development: generate a random key so the app can start
    settings.secret_key = _generate_dev_secret()
