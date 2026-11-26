from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.core.models.user import User
from sparkth.lib.frontend.hooks import DISPLAY_INFO, DisplayInfo
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.testing import AuditEventsFetcher, assert_plugin_use_denied, restrict_plugin_use

from .conftest import SCHEMA_PLUGIN_CONFIG_SCHEMA, add_preference

# Every by-name route as (method, path suffix, JSON body) for the plugin named in the URL.
BY_NAME_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "", None),
    ("POST", "/configure", {}),
    ("PATCH", "", {"enabled": True}),
    ("PUT", "/config", {"config": {}}),
    ("PATCH", "/enable", None),
    ("PATCH", "/disable", None),
]


@pytest.mark.parametrize(("method", "suffix", "body"), BY_NAME_ROUTES)
async def test_by_name_routes_refuse_without_a_grant(
    method: str,
    suffix: str,
    body: dict[str, Any] | None,
    current_user: User,
    client: AsyncClient,
    session: AsyncSession,
    schema_plugin: Plugin,
    audit_events: AuditEventsFetcher,
) -> None:
    await restrict_plugin_use(session, None)

    response = await client.request(method, f"/api/v1/plugins/schema_plugin{suffix}", json=body)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    await assert_plugin_use_denied(audit_events, "schema_plugin")


@pytest.mark.parametrize(("method", "suffix", "body"), BY_NAME_ROUTES)
async def test_by_name_routes_allow_a_grant_at_that_plugin(
    method: str,
    suffix: str,
    body: dict[str, Any] | None,
    current_user: User,
    client: AsyncClient,
    session: AsyncSession,
    schema_plugin: Plugin,
    audit_events: AuditEventsFetcher,
) -> None:
    await restrict_plugin_use(session, "schema_plugin")

    response = await client.request(method, f"/api/v1/plugins/schema_plugin{suffix}", json=body)

    assert response.status_code != status.HTTP_403_FORBIDDEN
    assert [event for event in await audit_events() if event.category == "permission"] == []


@pytest.mark.parametrize(("method", "suffix", "body"), BY_NAME_ROUTES)
async def test_by_name_routes_refuse_a_grant_at_another_plugin(
    method: str,
    suffix: str,
    body: dict[str, Any] | None,
    current_user: User,
    client: AsyncClient,
    session: AsyncSession,
    schema_plugin: Plugin,
) -> None:
    await restrict_plugin_use(session, "other_plugin")

    response = await client.request(method, f"/api/v1/plugins/schema_plugin{suffix}", json=body)

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_unknown_plugin_is_refused_without_a_grant(
    client: AsyncClient, session: AsyncSession, plugin_preferences: User
) -> None:
    await restrict_plugin_use(session, None)

    response = await client.get("/api/v1/plugins/does-not-exist")

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_plugin_success(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.get("/api/v1/plugins/plugin_a")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["is_core"] is True
    assert data["display"] is None
    assert data["sidebar"] is None
    assert data["has_frontend"] is False


async def test_get_reports_a_plugin_switched_off_system_wide(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.get("/api/v1/plugins/disabled_plugin")

    assert (response.json()["enabled"], response.json()["system_enabled"]) == (True, False)


async def test_get_plugin_carries_declared_display_info(
    client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    session.add(Plugin(name="displayed", is_core=True, enabled=True))
    await session.commit()

    # Hook storage is weakly keyed, so the entry vanishes with `plugin`.
    plugin = SparkthPlugin("displayed")
    DISPLAY_INFO.add_item(plugin, DisplayInfo("Displayed", "Shows up in settings", icon="eye"))

    response = await client.get("/api/v1/plugins/displayed")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["display"] == {"display_name": "Displayed", "description": "Shows up in settings", "icon": "eye"}
    assert data["sidebar"] is None
    assert data["has_frontend"] is False


async def test_get_plugin_not_found(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.get("/api/v1/plugins/plugin_abc")
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_plugin_fills_schema_keys_for_empty_config(
    client: AsyncClient, current_user: User, session: AsyncSession, schema_plugin: Plugin
) -> None:
    await add_preference(session, current_user, schema_plugin, config={})

    response = await client.get("/api/v1/plugins/schema_plugin")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"] == {"api_url": None, "api_key": None}


async def test_get_plugin_fills_schema_keys_missing_from_config(
    client: AsyncClient, current_user: User, session: AsyncSession, schema_plugin: Plugin
) -> None:
    await add_preference(session, current_user, schema_plugin, config={"api_key": "secret"})

    response = await client.get("/api/v1/plugins/schema_plugin")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"] == {"api_url": None, "api_key": "secret"}


async def test_get_plugin_reports_schema_keys_without_a_preference_row(
    client: AsyncClient, current_user: User, schema_plugin: Plugin
) -> None:
    response = await client.get("/api/v1/plugins/schema_plugin")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"] == {"api_url": None, "api_key": None}


async def test_get_plugin_carries_the_declared_config_schema(
    client: AsyncClient, current_user: User, schema_plugin: Plugin
) -> None:
    response = await client.get("/api/v1/plugins/schema_plugin")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config_schema"] == SCHEMA_PLUGIN_CONFIG_SCHEMA
