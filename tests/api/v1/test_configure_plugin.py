from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import status
from httpx import AsyncClient

from sparkth.core.models.user import User
from sparkth.core.plugins.exceptions import ConfigValidationError, InternalServerError
from sparkth.core.plugins.service import PluginService
from sparkth.lib.testing import AuditEventsFetcher


async def test_configure_plugin_success(client: AsyncClient, plugin_preferences: User) -> None:
    payload = {"some_config": 123}

    mock_plugin = SimpleNamespace(
        id=1,
        name="plugin_a",
        enabled=True,
        is_core=True,
        config_schema={},
    )

    mock_preference = SimpleNamespace(
        enabled=True,
        config=payload,
    )

    with (
        patch(
            "sparkth.core.plugins.service.PluginService.get_by_name",
            new=AsyncMock(return_value=mock_plugin),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.get_preference",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.create_preference",
            new=AsyncMock(return_value=mock_preference),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.validate_user_config",
            return_value=payload,
        ),
    ):
        response = await client.post(
            "/api/v1/plugins/plugin_a/configure",
            json=payload,
        )

    assert response.status_code == 201

    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["config"] == payload
    assert data["is_core"] is True


async def test_configure_plugin_unauthenticated(client: AsyncClient, audit_events: AuditEventsFetcher) -> None:
    response = await client.post("/api/v1/plugins/plugin_a/configure", json={})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert [event for event in await audit_events() if event.category == "permission"] == []


async def test_configure_plugin_not_found(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.post("/api/v1/plugins/missing_plugin/configure", json={})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"]


async def test_configure_plugin_admin_disabled(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.post("/api/v1/plugins/disabled_plugin/configure", json={})
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "not enabled" in response.json()["detail"]


async def test_configure_plugin_already_configured(client: AsyncClient, plugin_preferences: User) -> None:
    response = await client.post("/api/v1/plugins/plugin_b/configure", json={})
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already configured" in response.json()["detail"]


async def test_configure_plugin_invalid_config(client: AsyncClient, plugin_preferences: User) -> None:
    with patch(
        "sparkth.core.plugins.service.PluginService.validate_user_config",
        side_effect=ConfigValidationError("Invalid config"),
    ):
        response = await client.post(
            "/api/v1/plugins/plugin_a/configure",
            json={"bad": "data"},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid config"


async def test_configure_plugin_internal_error(client: AsyncClient, plugin_preferences: User) -> None:
    valid_config = {
        "api_url": "https://canvas.instructure.com",
        "api_key": "abc123",
    }

    with (
        patch.object(
            PluginService,
            "validate_user_config",
            return_value=valid_config,
        ),
        patch.object(
            PluginService,
            "create_preference",
            side_effect=InternalServerError("Plugin cannot be configured"),
        ),
    ):
        response = await client.post("/api/v1/plugins/plugin_a/configure", json=valid_config)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Plugin cannot be configured"
