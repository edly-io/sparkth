import gc
from collections.abc import Iterator

import pytest

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


def test_a_registered_capability_is_enabled(stub_plugin: SparkthPlugin) -> None:
    assert STUB in enabled_capabilities(set())


def test_a_capability_of_a_disabled_plugin_is_left_out(stub_plugin: SparkthPlugin) -> None:
    assert STUB not in enabled_capabilities({"stub"})


def test_a_plugin_constructed_twice_offers_its_capability_once(stub_plugin: SparkthPlugin) -> None:
    """The loader and tests both construct plugins, so the same capability arrives from two instances."""
    second = SparkthPlugin("stub")
    CHAT_CAPABILITIES.add_item(second, STUB)

    assert enabled_capabilities(set()).count(STUB) == 1


def test_capabilities_follow_plugin_name_order(stub_plugin: SparkthPlugin) -> None:
    """The composed prompt must not depend on which plugin was imported first."""
    early = SparkthPlugin("aaa-early")
    first = ChatCapability("Early", "Early scope.", "Early prompt")
    CHAT_CAPABILITIES.add_item(early, first)

    capabilities = enabled_capabilities(set())

    assert capabilities.index(first) < capabilities.index(STUB)
