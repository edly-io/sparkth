from pydantic import Field, HttpUrl

from sparkth.lib.plugins import ConfigWidget, PluginConfig, widget


class MoodleConfig(PluginConfig):
    api_url: HttpUrl = Field(..., description="Moodle API URL")
    api_key: str = Field(
        ...,
        description="Moodle API key",
        min_length=1,
        json_schema_extra=widget(ConfigWidget.PASSWORD),
    )

    @classmethod
    def lms_tool_prefix(cls) -> str:
        return "moodle_"

    def to_lms_credentials_hint(self) -> str:
        return f"Moodle credentials:\n  api_url: {self.api_url}\n  api_token: {self.api_key}"
