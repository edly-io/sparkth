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
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.testing import AddTranslation


def _plugin_entry(plugin_name: str, enabled: bool, config: dict[str, str], is_core: bool) -> dict[str, object]:
    """Expected response entry for a plugin that declared no frontend metadata."""
    return {
        "plugin_name": plugin_name,
        "enabled": enabled,
        "config": config,
        "is_core": is_core,
        "display": None,
        "sidebar": None,
        "has_frontend": False,
    }


async def test_list_user_plugins_basic(client: AsyncClient, user_plugins: User) -> None:
    response = await client.get("/api/v1/user-plugins/")
    assert response.status_code == 200

    data = response.json()
    expected = [
        _plugin_entry("plugin_a", enabled=True, config={}, is_core=True),
        _plugin_entry("plugin_b", enabled=True, config={"some config": "abc"}, is_core=True),
        _plugin_entry("configured_plugin_disabled", enabled=False, config={"some config": "abc"}, is_core=True),
        _plugin_entry("disabled_plugin", enabled=True, config={}, is_core=True),
    ]
    assert data == expected


async def test_list_user_plugins_carries_declared_frontend_metadata(
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

    response = await client.get("/api/v1/user-plugins/")
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "with-frontend")
    assert entry["display"] == {
        "display_name": "With Frontend",
        "description": "A plugin that ships a page",
        "icon": "sparkles",
    }
    assert entry["sidebar"] == {"label": "With Frontend", "icon": "sparkles", "order": 2}
    assert entry["has_frontend"] is True


async def test_list_user_plugins_translates_frontend_metadata(
    client: AsyncClient, current_user: User, session: AsyncSession, translation_catalog: AddTranslation
) -> None:
    session.add(Plugin(name="translated", is_core=True, enabled=True))
    await session.commit()

    plugin = SparkthPlugin("translated")
    DISPLAY_INFO.add_item(plugin, DisplayInfo("With Frontend", "A plugin that ships a page", icon="sparkles"))
    SIDEBAR_ENTRIES.add_item(plugin, SidebarEntry("With Frontend", icon="sparkles", order=2))

    translation_catalog("With Frontend", "Con interfaz")
    translation_catalog("A plugin that ships a page", "Un plugin que incluye una página")

    response = await client.get("/api/v1/user-plugins/", headers={"Accept-Language": "es"})
    assert response.status_code == 200

    entry = next(item for item in response.json() if item["plugin_name"] == "translated")
    assert entry["display"] == {
        "display_name": "Con interfaz",
        "description": "Un plugin que incluye una página",
        "icon": "sparkles",
    }
    assert entry["sidebar"] == {"label": "Con interfaz", "icon": "sparkles", "order": 2}


async def test_list_user_plugins_empty(client: AsyncClient, session: AsyncSession) -> None:
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

    response = await client.get("/api/v1/user-plugins/")
    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()
