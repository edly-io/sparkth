from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlmodel.ext.asyncio.session import AsyncSession


class PluginConfig(BaseModel):
    """Base class for all plugin configs"""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        strict=True,
    )


class ConfigAdapter:
    """Base for a plugin's config adapter; each step defaults to a no-op.

    A plugin registers a subclass on ``CONFIG_ADAPTERS`` and overrides only the steps it needs.

    preprocess_config: validates or rewrites the config a user is saving; returns the config to store.
    postprocess_config: derives the config returned to the frontend from the stored one.
    sync_cache: runs only after ``PUT /api/v1/user-plugins/{plugin_name}/config`` updates the config,
    not after ``POST /api/v1/user-plugins/{plugin_name}/configure``, so the plugin can drop state
    cached from the old config.
    """

    async def preprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        incoming_config: dict[str, Any],
    ) -> dict[str, Any]:
        return incoming_config

    async def postprocess_config(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> dict[str, Any]:
        return stored_config

    async def sync_cache(
        self,
        *,
        session: AsyncSession,
        user_id: int,
        stored_config: dict[str, Any],
    ) -> None:
        """Does nothing unless a subclass overrides it."""
