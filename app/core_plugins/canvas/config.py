from pydantic import Field

from app.plugins.config_base import PluginConfig


class CanvasConfig(PluginConfig):
    api_url: str = Field(..., description="Canvas API URL")
    api_key: str = Field(..., description="Canvas API key", min_length=1)
