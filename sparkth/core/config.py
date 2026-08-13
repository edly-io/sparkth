from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Env files every BaseSettings class in the app and plugins must read, in order:
# `.env` holds dev defaults; `.env.local` (git-ignored) holds sensitive creds and
# local overrides and takes precedence. Real environment variables (CI, prod/k8s)
# still win over both. Plugins import this via sparkth.lib.settings.
ENV_FILES = (".env", ".env.local")


class LanguageInfo(NamedTuple):
    """Display names for a supported language.

    Attributes:
        name: The language's name in English, for logs and admin surfaces.
        native_name: The endonym, for the user-facing picker — someone looking
            for their language reads it in their own language.
    """

    name: str
    native_name: str


# The allowlist of languages the platform accepts: the values a user may pick as a
# preference, and the set DEFAULT_LANGUAGE is validated against. A resolved tag is
# injected into the chat system prompt, so generated replies and course content follow
# it — which is why membership is a reviewed decision, not a promise the model is
# equally strong in every listed language.
#
# Keys are BCP 47 tags (RFC 5646) — the hyphenated form HTML `lang`,
# `Accept-Language` and the JS `Intl` API all consume; never the underscored POSIX
# form.
#
# The list is deliberately short. LLM output quality varies by language, so a
# language is added only once a speaker has reviewed generated course content in
# it. It sits beside Settings because the startup validation below is its first
# consumer.
SUPPORTED_LANGUAGES: dict[str, LanguageInfo] = {
    "en": LanguageInfo("English", "English"),
    "es": LanguageInfo("Spanish", "Español"),
    "fr": LanguageInfo("French", "Français"),
}


def is_supported_language(tag: str) -> bool:
    """Whether ``tag`` is one of the platform's supported BCP 47 tags.

    The single expression of allowlist membership: ``DEFAULT_LANGUAGE`` validation
    and every other caller share it, so the rule cannot drift between what the
    platform accepts as its default and what it accepts from a user. Matching is
    exact and case-sensitive — ``en-US`` and ``EN`` are unsupported rather than
    normalised to ``en``.
    """
    return tag in SUPPORTED_LANGUAGES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")
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
    # The platform-wide language preference: what applies to a user who has not
    # picked one, and the value reported as the default to clients.
    # Must be a key of SUPPORTED_LANGUAGES; validated below so an unsupported value
    # fails fast at startup rather than being accepted and served as the default.
    DEFAULT_LANGUAGE: str = "en"

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

    @field_validator("DEFAULT_LANGUAGE")
    @classmethod
    def _check_supported(cls, v: str) -> str:
        if not is_supported_language(v):
            supported = ", ".join(sorted(SUPPORTED_LANGUAGES))
            raise ValueError(f"DEFAULT_LANGUAGE must be one of: {supported}")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Path the FastMCP app is mounted on (sparkth/main.py). The audit context
# middleware stamps AuditSource.MCP on every request under this mount.
MCP_MOUNT_PATH = "/ai"


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
