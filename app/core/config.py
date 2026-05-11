from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS512"
    # 60 minutes * 24 hours * 8 days = 11520 minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_DIR: Path = Path("frontend/out")
    REGISTRATION_ENABLED: bool = False

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_AUTH_REDIRECT_URI: str = "http://localhost:7727/api/v1/auth/google/callback"

    # Google Drive OAuth (uses same client credentials, different redirect URI)
    GOOGLE_DRIVE_REDIRECT_URI: str = "http://localhost:7727/api/v1/googledrive/oauth/callback"

    # Slack TA Bot OAuth
    SLACK_CLIENT_ID: str
    SLACK_CLIENT_SECRET: str
    SLACK_SIGNING_SECRET: str
    SLACK_REDIRECT_URI: str

    RAG_CONCURRENCY: int = 1  # max number of files to process in parallel for RAG
    RAG_MAX_FILE_SIZE_MB: int = 50  # skip files larger than this during RAG ingestion
    RAG_STORE_BATCH_SIZE: int = 32  # number of chunks to embed + write to DB per batch
    RAG_EMBEDDING_PROVIDER: str = "huggingface"  # embedding provider: huggingface or openai
    RAG_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"  # model name passed to provider
    RAG_DISPLAY_NAME_MAX_CHARS: int = 30  # max chars for section/filename labels in the UI
    MEMORY_PROFILING_ENABLED: bool = False
    RAG_ALLOWED_EXTENSIONS: str = ""  # comma-separated extensions, e.g. "pdf,txt,docx"; empty = allow all supported
    RAG_MCP_URL: str

    LLM_ENCRYPTION_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_KEY_TTL: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_rag_allowed_extensions(raw: str) -> list[str]:
    """Parse a comma-separated extensions string into a normalised list.

    Strips whitespace, lowercases, and removes leading dots and duplicates.
    Returns an empty list when *raw* is blank, which means all supported types
    are permitted.
    """
    if not raw.strip():
        return []
    parts = [ext.strip().lower().lstrip(".") for ext in raw.split(",")]
    return list(dict.fromkeys(p for p in parts if p))


# Plugin Configuration
# List of plugin module paths to load (all enabled by default)
# Format: "module.path:ClassName"
PLUGINS = [
    "app.core_plugins.canvas.plugin:CanvasPlugin",
    "app.core_plugins.openedx.plugin:OpenEdxPlugin",
    "app.core_plugins.chat.plugin:ChatPlugin",
    "app.core_plugins.googledrive.plugin:GoogleDrivePlugin",
    "app.core_plugins.slack.plugin:SlackBotPlugin",
]


def get_plugin_settings() -> list[str]:
    """
    Get list of plugin module paths to load.
    All plugins returned are enabled by default.

    Returns:
        List of plugin module strings in format "module.path:ClassName"
    """
    return PLUGINS
