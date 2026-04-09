from pydantic import Field, HttpUrl

from app.plugins.config_base import PluginConfig


class OpenEdxConfig(PluginConfig):
    lms_url: HttpUrl = Field(..., description="Open edX LMS URL")
    studio_url: HttpUrl = Field(..., description="Open edX Studio URL")
    lms_username: str = Field(..., description="Username for the Open edX instance", min_length=1)
    lms_password: str = Field(..., description="Password for the Open edX instance", min_length=1)

    @classmethod
    def lms_tool_prefix(cls) -> str:
        return "openedx_"

    def to_lms_credentials_hint(self) -> str:
        return (
            "Open edX credentials:\n"
            f"  lms_url: {self.lms_url}\n"
            f"  studio_url: {self.studio_url}\n"
            f"  username: {self.lms_username}\n"
            f"  password: {self.lms_password}"
        )
