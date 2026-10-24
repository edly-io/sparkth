"""Tests for the sparkth.lib.plugins public API surface.

Everything here is imported from sparkth.lib.plugins only — this suite exercises the
public plugin-authoring boundary, never the plugin framework internals behind it. The one
core import is the object a lazy export must resolve to.
"""

from typing import cast

import pytest
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

import sparkth.lib.plugins as plugins_api
from sparkth.core.models.user import User
from sparkth.core.plugins.middleware import PluginAccessMiddleware
from sparkth.lib.plugins import PluginConfig, SparkthPlugin


class TestPluginsPublicApi:
    def test_all_lists_only_public_symbols(self) -> None:
        assert set(plugins_api.__all__) == {
            "SparkthPlugin",
            "PluginConfig",
            "ConfigAdapter",
            "ConfigWidget",
            "widget",
            "PluginAccessMiddleware",
            "get_plugin_loader",
            "PluginService",
            "get_plugin_service",
            "ConfigValidationError",
            "InternalServerError",
            "PluginDisabledError",
            "UserPluginResponse",
            "disabled_plugin_names",
            "get_disabled_plugins",
            "load_user_plugin_config",
            "PluginNotConfiguredError",
        }


class TestPluginsImportSafety:
    def test_module_imports_without_circular_error(self) -> None:
        import importlib

        # A re-import must succeed: the facade is imported during framework
        # bootstrap (sparkth.lib.hooks -> sparkth.lib.plugins), so it must stay free of
        # import cycles back through sparkth.lib.hooks.
        importlib.import_module("sparkth.lib.plugins")

    def test_resolves_access_middleware_lazily(self) -> None:
        assert plugins_api.PluginAccessMiddleware is PluginAccessMiddleware

    def test_resolves_plugin_service_lazily(self) -> None:
        assert isinstance(plugins_api.get_plugin_service(), plugins_api.PluginService)

    async def test_resolves_disabled_plugin_names_lazily(self, session: AsyncSession, current_user: User) -> None:
        assert await plugins_api.disabled_plugin_names(cast(int, current_user.id), session) == set()

    def test_unknown_attribute_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            plugins_api.does_not_exist  # noqa: B018


class TestSparkthPluginConstruction:
    def test_stores_plugin_name(self) -> None:
        plugin = SparkthPlugin("demo")
        assert plugin.name == "demo"

    def test_subclass_declares_its_name_positionally(self) -> None:
        class DemoPlugin(SparkthPlugin):
            def __init__(self) -> None:
                super().__init__("demo")

        plugin = DemoPlugin()
        assert plugin.name == "demo"

    def test_repr_includes_plugin_name(self) -> None:
        assert repr(SparkthPlugin("demo")) == "<SparkthPlugin: demo>"

    @pytest.mark.parametrize(
        "bad_name",
        ["", "Has Space", "UPPER", "trailing-", "-leading", "under_score", "dot.name"],
    )
    def test_rejects_names_that_are_not_kebab_case_slugs(self, bad_name: str) -> None:
        with pytest.raises(ValueError):
            SparkthPlugin(bad_name)

    @pytest.mark.parametrize("good_name", ["demo", "google-drive", "open-edx", "a1", "x2-y3"])
    def test_accepts_kebab_case_slugs(self, good_name: str) -> None:
        assert SparkthPlugin(good_name).name == good_name


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
