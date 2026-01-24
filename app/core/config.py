from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "EMAI"
    debug: bool = False

    # Database
    database_url: str = "postgresql://user:password@localhost:5432/emai_db"

    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    class Config:
        env_file = ".env"


settings = Settings()
