from pydantic import Field, HttpUrl

from app.plugins.config_base import PluginConfig


class CanvasConfig(PluginConfig):
    api_url: HttpUrl = Field(..., description="Canvas API URL")
    api_key: str = Field(..., description="Canvas API key", min_length=1)

    @classmethod
    def lms_tool_prefix(cls) -> str:
        return "canvas_"

    def to_lms_credentials_hint(self) -> str:
        return f"Canvas credentials:\n  api_url: {self.api_url}\n  api_token: {self.api_key}"
