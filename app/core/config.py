import secrets
from typing import Literal

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
    log_format: str = ""  # "json" or "text" (empty = auto: json in prod, text in dev)

    # Database (SQLite for local dev, PostgreSQL for production)
    database_url: str = "sqlite:///./emai.db"

    # JWT — no default; must be set via SECRET_KEY env var in production.
    # In development, a random key is generated per-process if not set.
    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 2

    # Security token TTLs
    pwd_reset_token_expire_hours: int = 1
    email_verify_token_expire_hours: int = 4
    unsubscribe_token_expire_days: int = 30

    # Account lockout tiers
    lockout_tier1_attempts: int = 5
    lockout_tier1_seconds: int = 900      # 15 min
    lockout_tier2_attempts: int = 10
    lockout_tier2_seconds: int = 3600     # 1 hour
    lockout_tier3_attempts: int = 15
    lockout_tier3_seconds: int = 86400    # 24 hours

    # Token encryption (Fernet key for encrypting OAuth tokens at rest)
    token_encryption_key: str = ""

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

    # OpenAI (used for embeddings in help chatbot RAG pipeline)
    openai_api_key: str = ""

    # Moderation fail mode (#4084). For K-12 safety, when the moderation API
    # is unavailable (missing key or network error) we fail CLOSED by default
    # — block the message rather than stream unfiltered content. Dev/staging
    # can override with MODERATION_FAIL_MODE=open.
    moderation_fail_mode: Literal["closed", "open"] = "closed"

    # Study guide limits
    max_study_guides_per_student: int = 100
    max_study_guides_per_parent: int = 200

    # File upload limits
    max_upload_size_mb: int = 30       # Max per-file size for course material uploads
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
    waitlist_enabled: bool = True  # Waitlist gated flow: "Join Waitlist" on login, token-gated registration (#1113, #1114)

    # XP / Gamification
    xp_enabled: bool = True

    # AI usage limits
    ai_default_usage_limit: int = 10
    ai_usage_warning_threshold: float = 0.8

    # File storage
    upload_dir: str = "./uploads"

    # GCS storage (#1643)
    gcs_bucket_name: str = ""
    use_gcs: bool = False

    # GCP Vision OCR (#3410) — enable for handwritten student notes
    gcp_vision_enabled: bool = False

    # Storage limits per tier (#1007)
    free_storage_limit_bytes: int = 104857600
    free_upload_limit_bytes: int = 10485760
    premium_storage_limit_bytes: int = 1073741824
    premium_upload_limit_bytes: int = 52428800
    storage_warning_threshold: float = 0.8

    # YouTube Data API v3 (§6.57.3 live search)
    youtube_api_key: str = ""

    # GitHub API (§6.115 bug reports)
    github_token: str = ""

    # Stripe payments (§6.60)
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # Twilio WhatsApp (#2967)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""  # e.g. +14155238886 (Twilio sandbox)
    twilio_whatsapp_digest_content_sid: str = ""  # Twilio Content SID for daily_digest template
    # #3956 — Phase A of #3905 multi-variable redesign. Dormant until Meta
    # approves the 4-variable sectioned template. When set, the digest job
    # uses the V2 4-variable sectioned template path; when empty, falls back
    # to V1 (single-variable bullet-marker template) with no user-visible change.
    twilio_whatsapp_digest_content_sid_v2: str = ""
    twilio_whatsapp_otp_content_sid: str = ""  # Twilio Content SID for OTP authentication template
    twilio_sms_from: str = ""

    # Rate limiting storage (memory:// for dev, redis://host:port for prod)
    rate_limit_storage_url: str = "memory://"

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
