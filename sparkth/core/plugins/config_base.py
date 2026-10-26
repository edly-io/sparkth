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

    @classmethod
    def lms_tool_prefix(cls) -> str | None:
        """
        Return the tool-name prefix for this LMS plugin (e.g. ``"openedx_"``),
        or ``None`` if this plugin is not an LMS.

        Used to detect whether any active tools belong to this LMS so that the
        credential injection can short-circuit the database call when no LMS tools
        are present.  It also decides which LMS's saved credentials chat sends: only an LMS
        with at least one bound tool carrying its prefix.  Override in each LMS config class.
        """
        return None

    # SECURITY NOTE: This string is injected into the LLM system prompt and is
    # transmitted to the configured LLM provider (Anthropic/OpenAI/etc.) in
    # plaintext on every chat request. The LLM uses it to call the authenticate
    # tool automatically.
    def to_lms_credentials_hint(self) -> str | None:
        """
        Return a human-readable, newline-formatted block of credentials for the
        LLM system prompt, or ``None`` if credentials are incomplete or this
        plugin is not an LMS.

        Override in each LMS config class.  The returned string will be included
        verbatim in the system message that instructs the LLM to use these
        credentials automatically when calling LMS tools.
        """
        return None


class ConfigAdapter:
    """Base for a plugin's config adapter; each step defaults to a no-op.

    A plugin registers a subclass on ``CONFIG_ADAPTERS`` and overrides only the steps it needs.

    preprocess_config: validates or rewrites the config a user is saving; returns the config to store.
    postprocess_config: derives the config returned to the frontend from the stored one.
    sync_cache: runs after a user updates an existing config, not on the first save, so the plugin
    can drop state cached from the old config.
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
