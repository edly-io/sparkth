from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

_LMS_RULES = (
    "If the user asks whether you have their credentials for any LMS (e.g., 'Do you have my <LMS NAME> credentials?') "
    "OR requests any LMS-related action (such as publishing a course, fetching courses, or creating/updating content), "
    "you must follow these rules:\n\n"
    "1. NEVER request, accept, or display LMS credentials in the chat.\n"
    "2. If the LMS is NOT configured:\n"
    "   - Clearly state that you do not have access to their <LMS NAME> credentials.\n"
    "   - Instruct the user to configure their credentials via the 'My Plugins' page.\n\n"
    "3. If the LMS IS configured:\n"
    "   - Do NOT reveal or display any credentials.\n"
    "   - Inform the user that their credentials are already configured.\n"
    "   - Direct them to the 'My Plugins' page if they want to view or manage them.\n\n"
    "4. These rules apply to ALL LMS platforms without exception."
)


def _lms_tool_prefixes() -> tuple[str, ...]:
    """
    Derive LMS tool-name prefixes from all registered plugin configs.

    Any config class that overrides ``lms_tool_prefix`` contributes its prefix.
    Lazy-imported to avoid circular dependencies at module load time.
    """
    from app.plugins import PLUGIN_CONFIG_CLASSES  # lazy import — avoids circular dep

    return tuple(prefix for cls in PLUGIN_CONFIG_CLASSES.values() if (prefix := cls.lms_tool_prefix()) is not None)


def _has_lms_tools(tools: list[Any]) -> bool:
    """Return True if any tool name starts with an LMS-specific prefix."""
    prefixes = _lms_tool_prefixes()
    return any(getattr(tool, "name", "").startswith(prefix) for tool in tools for prefix in prefixes)


async def build_lms_credentials_message(
    session: AsyncSession,
    user_id: int,
    tools: list[Any] | None,
) -> str | None:
    """
    Return a system message for the LLM about LMS credentials, or None when
    no LMS tools are active.

    - If credentials are configured: includes them so the LLM uses them
      automatically without asking the user.
    - If credentials are missing: returns the rules block directing the LLM
      to send the user to the 'My Plugins' page instead of asking in chat.

    Adding support for a new LMS requires only implementing
    ``lms_tool_prefix()`` and ``to_lms_credentials_hint()`` on its
    ``PluginConfig`` subclass — no changes to this function are needed.
    """
    if not tools or not _has_lms_tools(tools):
        return None

    from app.plugins import PLUGIN_CONFIG_CLASSES  # lazy import — avoids circular dep
    from app.services.plugin import PluginService  # lazy import — avoids circular dep

    plugin_service = PluginService()
    user_plugin_map = await plugin_service.get_user_plugin_map(session, user_id)

    credential_sections: list[str] = []

    for plugin_name, config_class in PLUGIN_CONFIG_CLASSES.items():
        if config_class.lms_tool_prefix() is None:
            continue

        user_plugin = user_plugin_map.get(plugin_name)
        if not user_plugin or not user_plugin.config:
            continue

        try:
            config_instance = config_class(**user_plugin.config)
        except Exception:
            continue

        hint = config_instance.to_lms_credentials_hint()
        if hint:
            credential_sections.append(hint)

    if not credential_sections:
        return _LMS_RULES

    return (
        _LMS_RULES
        + "\n5. Use the credentials below automatically when calling LMS tools without asking the user to provide them again:\n\n"
        + "\n\n".join(credential_sections)
    )
