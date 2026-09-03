from fastapi import status
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.core.models.user import User
from sparkth.lib.frontend.hooks import DISPLAY_INFO, DisplayInfo
from sparkth.lib.plugins import SparkthPlugin

from .conftest import add_user_plugin


async def test_get_user_plugin_success(client: AsyncClient, user_plugins: User) -> None:
    response = await client.get("/api/v1/user-plugins/plugin_a")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["is_core"] is True
    assert data["display"] is None
    assert data["sidebar"] is None
    assert data["has_frontend"] is False


async def test_get_user_plugin_carries_declared_display_info(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    session.add(Plugin(name="displayed", is_core=True, enabled=True))
    await session.commit()

    # Hook storage is weakly keyed, so the entry vanishes with `plugin`.
    plugin = SparkthPlugin("displayed")
    DISPLAY_INFO.add_item(plugin, DisplayInfo("Displayed", "Shows up in settings", icon="eye"))

    response = await client.get("/api/v1/user-plugins/displayed")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["display"] == {"display_name": "Displayed", "description": "Shows up in settings", "icon": "eye"}
    assert data["sidebar"] is None
    assert data["has_frontend"] is False


async def test_get_user_plugin_not_found(client: AsyncClient, user_plugins: User) -> None:
    response = await client.get("/api/v1/user-plugins/plugin_abc")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_user_plugin_fills_schema_keys_for_empty_config(
    client: AsyncClient, current_user: User, session: AsyncSession, schema_plugin: Plugin
) -> None:
    await add_user_plugin(session, current_user, schema_plugin, config={})

    response = await client.get("/api/v1/user-plugins/schema_plugin")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"] == {"api_url": None, "api_key": None}


async def test_get_user_plugin_fills_schema_keys_missing_from_config(
    client: AsyncClient, current_user: User, session: AsyncSession, schema_plugin: Plugin
) -> None:
    await add_user_plugin(session, current_user, schema_plugin, config={"api_key": "secret"})

    response = await client.get("/api/v1/user-plugins/schema_plugin")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"] == {"api_url": None, "api_key": "secret"}


async def test_get_user_plugin_reports_schema_keys_without_a_user_plugin_row(
    client: AsyncClient, current_user: User, schema_plugin: Plugin
) -> None:
    response = await client.get("/api/v1/user-plugins/schema_plugin")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"] == {"api_url": None, "api_key": None}
