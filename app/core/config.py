from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "EMAI"
    debug: bool = False
    environment: str = "development"  # development, production
    log_level: str = ""  # DEBUG, INFO, WARNING, ERROR, CRITICAL (empty = auto based on environment)
    log_to_file: bool = True  # Enable file logging

    # Database (SQLite for local dev, PostgreSQL for production)
    database_url: str = "sqlite:///./emai.db"

    # JWT
    secret_key: str = "your-secret-key-change-in-production"
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

    # Email (SendGrid)
    sendgrid_api_key: str = ""
    from_email: str = "noreply@classbridge.app"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
