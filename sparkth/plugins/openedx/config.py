from pydantic import Field, HttpUrl

from sparkth.lib.plugins import ConfigWidget, PluginConfig, widget


class OpenEdxConfig(PluginConfig):
    lms_url: HttpUrl = Field(..., description="Open edX LMS URL")
    studio_url: HttpUrl = Field(..., description="Open edX Studio URL")
    lms_username: str = Field(..., description="Username for the Open edX instance", min_length=1)
    lms_password: str = Field(
        ...,
        description="Password for the Open edX instance",
        min_length=1,
        json_schema_extra=widget(ConfigWidget.PASSWORD),
    )
