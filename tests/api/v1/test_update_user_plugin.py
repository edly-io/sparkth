from fastapi import status
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.core.models.user import User

from .conftest import SCHEMA_PLUGIN_CONFIG_SCHEMA, add_user_plugin


async def test_enable_reports_schema_keys_for_a_never_configured_plugin(
    client: AsyncClient, current_user: User, schema_plugin: Plugin
) -> None:
    """Enabling creates a user plugin with an empty config, which must still carry the
    schema keys — the settings UI renders the toggle response without refetching."""
    response = await client.patch("/api/v1/user-plugins/schema_plugin/enable")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["enabled"] is True
    assert data["config"] == {"api_url": None, "api_key": None}


async def test_disable_keeps_the_stored_config(
    client: AsyncClient, current_user: User, session: AsyncSession, schema_plugin: Plugin
) -> None:
    await add_user_plugin(session, current_user, schema_plugin, config={"api_url": "https://lms.example.com"})

    response = await client.patch("/api/v1/user-plugins/schema_plugin/disable")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["enabled"] is False
    assert data["config"] == {"api_url": "https://lms.example.com", "api_key": None}


async def test_enable_carries_the_declared_config_schema(
    client: AsyncClient, current_user: User, schema_plugin: Plugin
) -> None:
    response = await client.patch("/api/v1/user-plugins/schema_plugin/enable")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config_schema"] == SCHEMA_PLUGIN_CONFIG_SCHEMA
