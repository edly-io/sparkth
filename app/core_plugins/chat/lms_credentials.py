from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core_plugins.chat.constants import LMS_RULES
from app.lib.config import iter_plugin_config_schemas
from app.services.plugin import PluginService


def _lms_tool_prefixes() -> tuple[str, ...]:
    """
    Derive LMS tool-name prefixes from all registered plugin configs.

    Any config class that overrides ``lms_tool_prefix`` contributes its prefix.
    """

    return tuple(prefix for _name, cls in iter_plugin_config_schemas() if (prefix := cls.lms_tool_prefix()) is not None)


def _has_lms_tools(tools: list[Any]) -> bool:
    prefixes = _lms_tool_prefixes()
    return any(getattr(tool, "name", "").startswith(prefixes) for tool in tools)


async def build_lms_credentials_message(
    session: AsyncSession,
    user_id: int,
    tools: list[Any] | None,
) -> str | None:
    """Return a system message for the LLM about LMS credentials, or None when
    no LMS tools are active.

    - If credentials are configured: includes them so the LLM uses them
      automatically without asking the user.
    - If credentials are missing: returns the rules block directing the LLM
      to send the user to the 'My Plugins' page instead of asking in chat.

    Adding support for a new LMS requires only implementing
    ``lms_tool_prefix()`` and ``to_lms_credentials_hint()`` on its
    ``PluginConfig`` subclass — no changes to this function are needed.
    """
    # Intentional early-exit for both None (tools disabled by caller) and []
    # (tool names were requested but none resolved). Either way there are no
    # active tools to inspect, so no credentials hint is needed.
    if not tools or not _has_lms_tools(tools):
        return None

    plugin_service = PluginService()
    user_plugin_map = await plugin_service.get_user_plugin_map(session, user_id)

    credential_sections: list[str] = []

    for plugin_name, config_class in iter_plugin_config_schemas():
        if config_class.lms_tool_prefix() is None:
            continue

        user_plugin = user_plugin_map.get(plugin_name)
        if not user_plugin or not user_plugin.config:
            continue

        try:
            config_instance = config_class(**user_plugin.config)
        except (ValueError, TypeError):
            continue

        hint = config_instance.to_lms_credentials_hint()
        if hint:
            credential_sections.append(hint)

    if not credential_sections:
        return LMS_RULES

    return (
        LMS_RULES
        + "\n5. Use the credentials below automatically when calling LMS tools without asking"
        + " the user to provide them again:\n\n"
        + "\n\n".join(credential_sections)
    )
