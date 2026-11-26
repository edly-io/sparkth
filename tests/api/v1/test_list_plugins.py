from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models import User
from sparkth.core.models.plugin import Plugin
from sparkth.core.plugins.service import PluginService, get_plugin_service
from sparkth.lib.auth import get_current_user
from sparkth.lib.frontend.hooks import (
    DISPLAY_INFO,
    FRONTEND_APPS,
    SIDEBAR_ENTRIES,
    DisplayInfo,
    FrontendApp,
    SidebarEntry,
)
from sparkth.lib.plugins import SparkthPlugin, secret
from sparkth.lib.testing import AddTranslation, AuditEventsFetcher, restrict_plugin_use

from .conftest import SCHEMA_PLUGIN_CONFIG_SCHEMA, add_preference


async def test_list_shows_only_the_plugins_granted(
    client: AsyncClient, session: AsyncSession, plugin_preferences: User
) -> None:
    await restrict_plugin_use(session, "plugin_a")

    response = await client.get("/api/v1/plugins/")

    assert response.status_code == 200
    assert [entry["plugin_name"] for entry in response.json()] == ["plugin_a"]


async def test_list_is_empty_without_a_grant(
    client: AsyncClient, session: AsyncSession, plugin_preferences: User, audit_events: AuditEventsFetcher
) -> None:
    await restrict_plugin_use(session, None)

    response = await client.get("/api/v1/plugins/")

    assert response.status_code == 200
    assert response.json() == []
    assert [event.action for event in await audit_events() if event.category == "permission"] == []


def _plugin_entry(
    plugin_name: str, enabled: bool, system_enabled: bool, config: dict[str, str], is_core: bool
) -> dict[str, object]:
    """Expected response entry for a plugin that declared no frontend metadata."""
    return {
        "plugin_name": plugin_name,
        "enabled": enabled,
        "system_enabled": system_enabled,
        "config": config,
        "is_core": is_core,
        "config_schema": {},
        "display": None,
        "sidebar": None,
        "has_frontend": False,
        "secrets_set": [],
        "masked_secrets": {},
    }


async def test_list_plugins_basic(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.get("/api/v1/plugins/")
    assert response.status_code == 200

    data = response.json()
    expected = [
        _plugin_entry("plugin_a", enabled=True, system_enabled=True, config={}, is_core=True),
        _plugin_entry("plugin_b", enabled=True, system_enabled=True, config={"some config": "abc"}, is_core=True),
        _plugin_entry(
            "configured_plugin_disabled",
            enabled=False,
            system_enabled=True,
            config={"some config": "abc"},
            is_core=True,
        ),
        _plugin_entry("disabled_plugin", enabled=True, system_enabled=False, config={}, is_core=True),
    ]
    assert data == expected


async def test_list_reports_a_plugin_switched_off_system_wide(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.get("/api/v1/plugins/")

    states = {entry["plugin_name"]: (entry["enabled"], entry["system_enabled"]) for entry in response.json()}
    assert states["disabled_plugin"] == (True, False)
    assert states["plugin_a"] == (True, True)


async def test_list_plugins_carries_declared_frontend_metadata(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    session.add(Plugin(name="with-frontend", is_core=True, enabled=True))
    await session.commit()

    # A live plugin instance declaring its frontend-facing metadata through the
    # hooks; the hook storage is weakly keyed, so entries vanish with `plugin`.
    plugin = SparkthPlugin("with-frontend")
    DISPLAY_INFO.add_item(plugin, DisplayInfo("With Frontend", "A plugin that ships a page", icon="sparkles"))
    SIDEBAR_ENTRIES.add_item(plugin, SidebarEntry("With Frontend", icon="sparkles", order=2))
    FRONTEND_APPS.add_item(plugin, FrontendApp())

    response = await client.get("/api/v1/plugins/")
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "with-frontend")
    assert entry["display"] == {
        "display_name": "With Frontend",
        "description": "A plugin that ships a page",
        "icon": "sparkles",
    }
    assert entry["sidebar"] == {"label": "With Frontend", "icon": "sparkles", "order": 2}
    assert entry["has_frontend"] is True


async def test_list_plugins_translates_frontend_metadata(
    client: AsyncClient, current_user: User, session: AsyncSession, translation_catalog: AddTranslation
) -> None:
    session.add(Plugin(name="translated", is_core=True, enabled=True))
    await session.commit()

    plugin = SparkthPlugin("translated")
    DISPLAY_INFO.add_item(plugin, DisplayInfo("With Frontend", "A plugin that ships a page", icon="sparkles"))
    SIDEBAR_ENTRIES.add_item(plugin, SidebarEntry("With Frontend", icon="sparkles", order=2))

    translation_catalog("With Frontend", "Con interfaz")
    translation_catalog("A plugin that ships a page", "Un plugin que incluye una página")

    response = await client.get("/api/v1/plugins/", headers={"Accept-Language": "es"})
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "translated")
    assert entry["display"] == {
        "display_name": "Con interfaz",
        "description": "Un plugin que incluye una página",
        "icon": "sparkles",
    }
    assert entry["sidebar"] == {"label": "Con interfaz", "icon": "sparkles", "order": 2}


async def test_list_plugins_empty(client: AsyncClient, session: AsyncSession) -> None:
    user = User(name="Test User", username="noplugins", email="empty@example.com", hashed_password="fakehashedpassword")
    session.add(user)
    await session.commit()
    await session.refresh(user)

    def get_user_override() -> User:
        return user

    def get_plugin_service_override() -> PluginService:
        return PluginService()

    transport = cast(ASGITransport, client._transport)
    app = cast(FastAPI, transport.app)
    app.dependency_overrides[get_current_user] = get_user_override
    app.dependency_overrides[get_plugin_service] = get_plugin_service_override

    response = await client.get("/api/v1/plugins/")
    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()


async def test_list_plugins_fills_schema_keys_for_empty_config(
    client: AsyncClient, current_user: User, session: AsyncSession, schema_plugin: Plugin
) -> None:
    """Enabling a plugin stores an empty config; the schema keys must still be reported.

    The settings UI renders one field per key it receives, so dropping them leaves the
    user with no way to configure the plugin.
    """
    await add_preference(session, current_user, schema_plugin, config={})

    response = await client.get("/api/v1/plugins/")
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "schema_plugin")
    assert entry["config"] == {"api_url": None, "api_key": None}


async def test_list_plugins_fills_schema_keys_missing_from_config(
    client: AsyncClient, current_user: User, session: AsyncSession, schema_plugin: Plugin
) -> None:
    await add_preference(session, current_user, schema_plugin, config={"api_url": "https://lms.example.com"})

    response = await client.get("/api/v1/plugins/")
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "schema_plugin")
    assert entry["config"] == {"api_url": "https://lms.example.com", "api_key": None}


async def test_list_plugins_carries_the_declared_config_schema(
    client: AsyncClient, current_user: User, schema_plugin: Plugin
) -> None:
    """The settings form is rendered from the schema, so the API must ship it.

    Without it the frontend knows key names only -- no types, labels, defaults or
    widgets -- and can render nothing but untyped text inputs.
    """
    response = await client.get("/api/v1/plugins/")
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "schema_plugin")
    assert entry["config_schema"] == SCHEMA_PLUGIN_CONFIG_SCHEMA


async def test_list_plugins_reports_an_empty_schema_for_a_plugin_without_one(
    client: AsyncClient, plugin_preferences: User
) -> None:
    response = await client.get("/api/v1/plugins/")
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "plugin_a")
    assert entry["config_schema"] == {}


async def test_list_plugins_never_returns_secrets(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    schema = {"properties": {"api_url": {"type": "string"}, "api_key": {"type": "string", **secret()}}}
    plugin = Plugin(name="secret_plugin", is_core=True, enabled=True, config_schema=schema)
    session.add(plugin)
    await session.flush()
    await add_preference(session, current_user, plugin, {"api_url": "https://lms.example.com", "api_key": "s3cret"})

    response = await client.get("/api/v1/plugins/")

    entry = next(p for p in response.json() if p["plugin_name"] == "secret_plugin")
    assert "s3cret" not in response.text
    assert entry["config"] == {"api_url": "https://lms.example.com"}
    assert entry["secrets_set"] == ["api_key"]
