from typing import Any, cast

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User


@pytest.fixture
async def user_plugins(current_user: User, session: AsyncSession) -> User:
    plugin_a = Plugin(name="plugin_a", is_core=True, enabled=True)
    plugin_b = Plugin(name="plugin_b", is_core=True, enabled=True)
    configured_plugin_disabled = Plugin(name="configured_plugin_disabled", is_core=True, enabled=True)
    disabled_plugin = Plugin(name="disabled_plugin", is_core=True, enabled=False)
    session.add_all([plugin_a, plugin_b, configured_plugin_disabled, disabled_plugin])
    await session.flush()

    user_plugin_b = UserPlugin(
        user_id=cast(int, current_user.id),
        plugin_id=cast(int, plugin_b.id),
        enabled=True,
        config={"some config": "abc"},
    )
    session.add(user_plugin_b)
    await session.flush()

    user_plugin_c = UserPlugin(
        user_id=cast(int, current_user.id),
        plugin_id=cast(int, configured_plugin_disabled.id),
        enabled=False,
        config={"some config": "abc"},
    )
    session.add(user_plugin_c)
    await session.flush()

    return current_user


# A plugin config schema in the shape Pydantic's ``model_json_schema()`` emits, so the
# responses exercise the same key extraction as a real plugin (see
# ``PluginService.initial_config``).
SCHEMA_PLUGIN_CONFIG_SCHEMA: dict[str, Any] = {
    "title": "SchemaPluginConfig",
    "type": "object",
    "properties": {
        "api_url": {"title": "Api Url", "type": "string"},
        "api_key": {"title": "Api Key", "type": "string"},
    },
    "required": ["api_url", "api_key"],
}


@pytest.fixture
async def schema_plugin(session: AsyncSession) -> Plugin:
    """A plugin declaring a two-field config schema."""
    plugin = Plugin(name="schema_plugin", is_core=True, enabled=True, config_schema=SCHEMA_PLUGIN_CONFIG_SCHEMA)
    session.add(plugin)
    await session.flush()
    return plugin


async def add_user_plugin(
    session: AsyncSession, user: User, plugin: Plugin, config: dict[str, Any], enabled: bool = True
) -> UserPlugin:
    """Attach ``plugin`` to ``user`` with the given stored config."""
    user_plugin = UserPlugin(
        user_id=cast(int, user.id),
        plugin_id=cast(int, plugin.id),
        enabled=enabled,
        config=config,
    )
    session.add(user_plugin)
    await session.flush()
    return user_plugin
