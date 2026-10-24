from pydantic import Field, HttpUrl

from sparkth.lib.plugins import ConfigWidget, PluginConfig, widget


class CanvasConfig(PluginConfig):
    api_url: HttpUrl = Field(..., description="Canvas API URL")
    api_key: str = Field(
        ...,
        description="Canvas API key",
        min_length=1,
        json_schema_extra=widget(ConfigWidget.PASSWORD),
    )

    @classmethod
    def lms_tool_prefix(cls) -> str:
        return "canvas_"
