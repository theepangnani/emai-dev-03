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

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/google/callback"

    # Frontend
    frontend_url: str = "http://localhost:5173"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Email (SendGrid)
    sendgrid_api_key: str = ""
    from_email: str = "noreply@classbridge.app"

    class Config:
        env_file = ".env"


settings = Settings()
