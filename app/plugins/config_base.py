from pydantic import BaseModel, ConfigDict


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
        are present.  Override in each LMS config class.
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
