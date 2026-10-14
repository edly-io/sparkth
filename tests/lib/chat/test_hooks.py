import gc
from collections.abc import Iterator

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.lib.chat.hooks import CHAT_CAPABILITIES, ChatCapability, enabled_capabilities
from sparkth.lib.plugins import SparkthPlugin

STUB = ChatCapability("Stub", "Stub scope.", "Stub prompt")


@pytest.fixture
def stub_plugin() -> Iterator[SparkthPlugin]:
    """A plugin registering STUB; its weakly-keyed entry goes when the plugin is collected."""
    plugin = SparkthPlugin("stub")
    CHAT_CAPABILITIES.add_item(plugin, STUB)
    yield plugin
    del plugin
    gc.collect()


async def test_a_registered_capability_is_enabled(session: AsyncSession, stub_plugin: SparkthPlugin) -> None:
    assert STUB in await enabled_capabilities(session)


async def test_a_capability_of_a_plugin_disabled_system_wide_is_left_out(
    session: AsyncSession, stub_plugin: SparkthPlugin
) -> None:
    session.add(Plugin(name="stub", enabled=False))
    await session.commit()

    assert STUB not in await enabled_capabilities(session)


async def test_a_plugin_constructed_twice_offers_its_capability_once(
    session: AsyncSession, stub_plugin: SparkthPlugin
) -> None:
    """The loader and tests both construct plugins, so the same capability arrives from two instances."""
    second = SparkthPlugin("stub")
    CHAT_CAPABILITIES.add_item(second, STUB)

    assert (await enabled_capabilities(session)).count(STUB) == 1


async def test_capabilities_follow_plugin_name_order(session: AsyncSession, stub_plugin: SparkthPlugin) -> None:
    """The composed prompt must not depend on which plugin was imported first."""
    early = SparkthPlugin("aaa-early")
    first = ChatCapability("Early", "Early scope.", "Early prompt")
    CHAT_CAPABILITIES.add_item(early, first)

    capabilities = await enabled_capabilities(session)

    assert capabilities.index(first) < capabilities.index(STUB)
