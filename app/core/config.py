from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS512"
    # 60 minutes * 24 hours * 8 days = 11520 minutes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Plugin Configuration
# List of plugin module paths to load (all enabled by default)
# Format: "module.path:ClassName"
PLUGINS = [
    "app.core_plugins.canvas.plugin:CanvasPlugin",
    "app.core_plugins.openedx.plugin:OpenEdXPlugin",
]


def get_plugin_settings() -> List[str]:
    """
    Get list of plugin module paths to load.
    All plugins returned are enabled by default.

    Returns:
        List of plugin module strings in format "module.path:ClassName"
    """
    return PLUGINS
