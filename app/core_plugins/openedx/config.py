from pydantic import Field, HttpUrl

from app.plugins.config_base import PluginConfig


class OpenEdxConfig(PluginConfig):
    lms_url: HttpUrl = Field(..., description="Open edX LMS URL")
    studio_url: HttpUrl = Field(..., description="Open edX Studio URL")
    username: str = Field(..., description="Username for the Open edX instance", min_length=1)
    password: str = Field(..., description="Password for the Open edX instance", min_length=1)
