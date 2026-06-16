"""Tests for the app.lib.plugins public API surface.

Everything here is imported from app.lib.plugins only — this suite exercises the
public plugin-authoring boundary, never the plugin framework internals behind it.
"""

import pytest
from pydantic import ValidationError

import app.lib.plugins as plugins_api
from app.lib.plugins import PluginConfig, SparkthPlugin


class TestPluginsPublicApi:
    def test_exposes_base_plugin_class(self) -> None:
        assert isinstance(SparkthPlugin, type)

    def test_exposes_config_base_class(self) -> None:
        assert isinstance(PluginConfig, type)

    def test_all_lists_only_public_symbols(self) -> None:
        assert set(plugins_api.__all__) == {
            "SparkthPlugin",
            "PluginConfig",
            "PluginAccessMiddleware",
            "get_plugin_loader",
        }


class TestPluginsImportSafety:
    def test_module_imports_without_circular_error(self) -> None:
        import importlib

        # A re-import must succeed: the facade is imported during framework
        # bootstrap (app.lib.hooks -> app.lib.plugins), so it must stay free of
        # import cycles back through app.lib.hooks.
        importlib.import_module("app.lib.plugins")

    def test_exposes_plugin_loader(self) -> None:
        assert callable(plugins_api.get_plugin_loader)

    def test_resolves_access_middleware_lazily(self) -> None:
        assert isinstance(plugins_api.PluginAccessMiddleware, type)

    def test_unknown_attribute_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            plugins_api.does_not_exist  # noqa: B018


class TestSparkthPluginConstruction:
    def test_stores_plugin_name(self) -> None:
        plugin = SparkthPlugin("demo")
        assert plugin.name == "demo"

    def test_subclass_passes_name_through_super_init(self) -> None:
        class DemoPlugin(SparkthPlugin):
            def __init__(self, plugin_name: str) -> None:
                super().__init__(plugin_name)

        plugin = DemoPlugin("demo")
        assert plugin.name == "demo"

    def test_repr_includes_plugin_name(self) -> None:
        assert repr(SparkthPlugin("demo")) == "<SparkthPlugin: demo>"


class TestPluginConfig:
    def test_subclass_forbids_extra_fields(self) -> None:
        class DemoConfig(PluginConfig):
            value: int

        with pytest.raises(ValidationError):
            DemoConfig(**{"value": 1, "unexpected": "x"})  # type: ignore[arg-type]

    def test_subclass_is_not_an_lms_by_default(self) -> None:
        class DemoConfig(PluginConfig):
            value: int

        config = DemoConfig(value=1)
        assert config.lms_tool_prefix() is None
        assert config.to_lms_credentials_hint() is None
