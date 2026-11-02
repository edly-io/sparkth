import gc
from collections.abc import Iterator

import pytest

from sparkth.lib.compose.exceptions import DuplicateChatCapabilityError
from sparkth.lib.compose.hooks import CHAT_CAPABILITIES, ChatCapability, enabled_capabilities, register_chat_capability
from sparkth.lib.plugins import SparkthPlugin

STUB = ChatCapability("Stub", "Stub scope.", "Stub prompt")


@pytest.fixture
def stub_plugin() -> Iterator[SparkthPlugin]:
    """A plugin registering STUB; its weakly-keyed entry goes when the plugin is collected."""
    plugin = SparkthPlugin("stub")
    register_chat_capability(plugin, STUB)
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
    register_chat_capability(second, STUB)

    assert enabled_capabilities(set()).count(STUB) == 1


def test_a_different_capability_under_a_registered_title_is_refused(stub_plugin: SparkthPlugin) -> None:
    other = SparkthPlugin("other")

    with pytest.raises(DuplicateChatCapabilityError):
        register_chat_capability(other, ChatCapability(STUB.title, "Other scope.", "Other prompt"))

    assert all(owner is not other for owner, _ in CHAT_CAPABILITIES.iter_items())


def test_capabilities_follow_plugin_name_order(stub_plugin: SparkthPlugin) -> None:
    """The composed prompt must not depend on which plugin was imported first."""
    early = SparkthPlugin("aaa-early")
    first = ChatCapability("Early", "Early scope.", "Early prompt")
    register_chat_capability(early, first)

    capabilities = enabled_capabilities(set())

    assert capabilities.index(first) < capabilities.index(STUB)
