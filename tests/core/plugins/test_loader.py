"""Tests for the plugin loader's explicit-name contract.

A plugin declares its own name by passing it positionally to ``super().__init__()``;
the loader constructs each class with no arguments and never derives a name from
the class name.
"""

import pytest

from sparkth.core.plugins.loader import PluginLoader
from sparkth.lib.plugins import SparkthPlugin

_MODULE = __name__


class AlphaPlugin(SparkthPlugin):
    """Declares a name that has nothing to do with its class name."""

    def __init__(self) -> None:
        super().__init__("totally-custom-name")


class BravoPlugin(SparkthPlugin):
    def __init__(self) -> None:
        super().__init__("bravo")


class DuplicateOfAlpha(SparkthPlugin):
    def __init__(self) -> None:
        super().__init__("totally-custom-name")


class ExplodingPlugin(SparkthPlugin):
    def __init__(self) -> None:
        raise RuntimeError("boom")


class NamelessPlugin(SparkthPlugin):
    """Never calls super().__init__, so it declares no name."""

    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        pass


class LegacyNameParameterPlugin(SparkthPlugin):
    """Old-style plugin still expecting the loader to pass a name in."""

    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)


def _loader_for(monkeypatch: pytest.MonkeyPatch, *classes: type[SparkthPlugin]) -> PluginLoader:
    module_strings = [f"{_MODULE}:{cls.__name__}" for cls in classes]
    monkeypatch.setattr("sparkth.core.plugins.loader.get_plugin_settings", lambda: module_strings)
    return PluginLoader()


def test_loads_plugin_under_its_declared_name(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _loader_for(monkeypatch, AlphaPlugin)
    loaded = loader.get_loaded_plugins()
    assert [name for name, _ in loaded] == ["totally-custom-name"]
    assert isinstance(loaded[0][1], AlphaPlugin)


def test_name_is_not_derived_from_class_name(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _loader_for(monkeypatch, AlphaPlugin)
    names = [name for name, _ in loader.get_loaded_plugins()]
    assert "alpha" not in names


def test_duplicate_declared_names_keep_the_first_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _loader_for(monkeypatch, AlphaPlugin, DuplicateOfAlpha)
    loaded = loader.get_loaded_plugins()
    assert len(loaded) == 1
    assert isinstance(loaded[0][1], AlphaPlugin)


def test_failing_plugin_does_not_block_others(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _loader_for(monkeypatch, ExplodingPlugin, BravoPlugin)
    assert [name for name, _ in loader.get_loaded_plugins()] == ["bravo"]


def test_plugin_without_a_declared_name_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _loader_for(monkeypatch, NamelessPlugin, BravoPlugin)
    assert [name for name, _ in loader.get_loaded_plugins()] == ["bravo"]


def test_legacy_plugin_expecting_a_name_argument_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = _loader_for(monkeypatch, LegacyNameParameterPlugin, BravoPlugin)
    assert [name for name, _ in loader.get_loaded_plugins()] == ["bravo"]
