from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Affiliate Adoption Portal"

    # sqlite default lets the repo run with zero setup; use Postgres in prod.
    database_url: str = "sqlite:///./portal.db"

    jwt_secret: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    # Base URL of this API (used to build the webhook URLs shown to admins).
    portal_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173"

    # Bootstrap admin (created on first startup if missing).
    admin_email: str = "admin@portal.local"
    admin_password: str = "admin123"
    admin_name: str = "Portal Admin"

    # Email delivery: Resend (preferred — just set the API key), SMTP as a
    # fallback, console logging when neither is configured.
    resend_api_key: str = ""
    email_from: str = "Adoption HQ <onboarding@resend.dev>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
