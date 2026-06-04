"""Configuration for Google Drive plugin."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.plugins.config_base import PluginConfig


class GoogleDriveConfig(PluginConfig):
    """Per-user runtime config injected into the plugin at request time.

    OAuth tokens are stored per-user in the DriveOAuthToken table.
    Environment-level settings (e.g. redirect URI) live in
    ``GoogleDriveSettings`` instead.
    """


class GoogleDriveSettings(BaseSettings):
    """Environment-level settings for the Google Drive plugin.

    Reads from the same ``.env`` / environment variables as the core
    ``Settings`` class.  Kept separate so Drive-specific config does not
    bleed into the application core.

    Use ``get_googledrive_settings()`` to obtain a cached instance.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GOOGLE_DRIVE_REDIRECT_URI: str
    DRIVE_MAX_UPLOAD_BYTES: int = 30 * 1024 * 1024
    # Max files ingested in parallel during a folder sync.
    INGESTION_CONCURRENCY: int = 1
    # Files larger than this are skipped during ingestion (the client enforces
    # the size guard; the RAG pipeline itself does not limit file size).
    INGESTION_MAX_FILE_SIZE_MB: int = 50


@lru_cache
def get_googledrive_settings() -> GoogleDriveSettings:
    return GoogleDriveSettings()
