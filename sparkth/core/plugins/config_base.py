from pydantic import BaseModel, ConfigDict


class PluginConfig(BaseModel):
    """Base class for all plugin configs"""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        strict=True,
    )
