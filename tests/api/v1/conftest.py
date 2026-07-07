from typing import cast

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.models.plugin import Plugin, UserPlugin
from sparkth.models.user import User


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
