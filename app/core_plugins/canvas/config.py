from pydantic import Field, HttpUrl

from app.plugins.config_base import PluginConfig


class CanvasConfig(PluginConfig):
    api_url: HttpUrl = Field(..., description="Canvas API URL")
    api_key: str = Field(..., description="Canvas API key", min_length=1)
