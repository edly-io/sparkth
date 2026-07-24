from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `.env` holds dev defaults; `.env.local` (git-ignored) holds sensitive creds and
    # local overrides and takes precedence. Real environment variables (CI, prod/k8s)
    # still win over both.
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore")
    DATABASE_URL: str
    ANALYTICS_DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS512"
    # 60 minutes * 24 hours * 8 days = 11520 minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_DIR: Path = Path("frontend/out")
    # Serve the static frontend export from FRONTEND_DIR at "/". Off by default so
    # native/dev runs never serve a stale export; the production image enables it.
    SERVE_FRONTEND: bool = False
    REGISTRATION_ENABLED: bool = False
    # Number of trusted reverse-proxy hops in front of the app. 0 (default)
    # means X-Forwarded-For is ignored entirely (the header is client-forgeable)
    # and the socket peer address is used, e.g. for the audit trail's request_ip.
    TRUSTED_PROXY_HOPS: int = 0

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_AUTH_REDIRECT_URI: str = "http://localhost:7727/api/v1/auth/google/callback"

    # Email / SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Sparkth"

    # Email verification (uses the shared REDIS_URL below for resend rate limiting)
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS: int = 24
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS: int = 60
    FRONTEND_BASE_URL: str = "http://localhost:7727"

    MEMORY_PROFILING_ENABLED: bool = False

    LLM_ENCRYPTION_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_KEY_TTL: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Plugin Configuration
# List of plugin module paths to load (all enabled by default)
# Format: "module.path:ClassName"
PLUGINS = [
    "sparkth.plugins.canvas.plugin:CanvasPlugin",
    "sparkth.plugins.openedx.plugin:OpenEdxPlugin",
    "sparkth.plugins.chat.plugin:ChatPlugin",
    "sparkth.plugins.googledrive.plugin:GoogleDrivePlugin",
    "sparkth.plugins.slack.plugin:Slack",
]


def get_plugin_settings() -> list[str]:
    """
    Get list of plugin module paths to load.
    All plugins returned are enabled by default.

    Returns:
        List of plugin module strings in format "module.path:ClassName"
    """
    return PLUGINS
