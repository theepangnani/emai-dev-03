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

    # Domain redirect (301 non-canonical → canonical)
    canonical_domain: str = ""  # e.g. "www.classbridge.ca"

    # CORS (comma-separated origins, empty = allow all in development)
    allowed_origins: str = ""

    # Anthropic Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Study guide limits
    max_study_guides_per_student: int = 100
    max_study_guides_per_parent: int = 200

    # File upload limits
    max_upload_size_mb: int = 20       # Max per-file size for course material uploads
    max_files_per_session: int = 10    # Max files per upload session (enforced on frontend + paste endpoint)

    # Audit logging
    audit_log_enabled: bool = True
    audit_log_retention_days: int = 90

    # Email
    sendgrid_api_key: str = ""
    from_email: str = "clazzbridge@gmail.com"
    # Gmail SMTP (used when SendGrid is not configured)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # Gmail App Password

    # Shadow teacher auto-invite (#946)
    auto_invite_shadow_teachers: bool = True

    # Feature toggles (#1054)
    google_classroom_enabled: bool = False
    waitlist_enabled: bool = True  # Show "Join the Waitlist" instead of "Sign Up" on login (#1113)

    # AI usage limits
    ai_default_usage_limit: int = 10
    ai_usage_warning_threshold: float = 0.8

    # Waitlist (#1114) — when True, registration requires an invite token
    waitlist_enabled: bool = False

    # File storage
    upload_dir: str = "./uploads"

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
