"""Tests for the plugin-config helpers in sparkth.lib.config.

Exercises the CONFIG_ADAPTERS hook and its lookup helpers, mirroring the
CONFIG_SCHEMAS pattern. Everything is imported from the public sparkth.lib.config
surface, never the framework internals behind it.
"""

from sparkth.lib.config import get_plugin_adapter, iter_plugin_adapters
from sparkth.lib.config.hooks import CONFIG_ADAPTERS
from sparkth.lib.llm import LLMConfigAdapter
from sparkth.lib.plugins import SparkthPlugin


def test_get_plugin_adapter_returns_registered_adapter() -> None:
    plugin = SparkthPlugin("fake-adapter-plugin")
    adapter = LLMConfigAdapter()
    CONFIG_ADAPTERS.add_item(plugin, adapter)

    assert get_plugin_adapter("fake-adapter-plugin") is adapter


def test_get_plugin_adapter_returns_none_for_unknown_plugin() -> None:
    assert get_plugin_adapter("plugin-that-never-registered") is None


def test_iter_plugin_adapters_yields_registered_pairs() -> None:
    plugin = SparkthPlugin("another-fake-adapter-plugin")
    adapter = LLMConfigAdapter()
    CONFIG_ADAPTERS.add_item(plugin, adapter)

    assert ("another-fake-adapter-plugin", adapter) in list(iter_plugin_adapters())
