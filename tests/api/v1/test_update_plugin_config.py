from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from httpx import AsyncClient

from sparkth.core.models.user import User
from sparkth.core.plugins.exceptions import ConfigValidationError, InternalServerError


async def test_update_plugin_not_configured_success(client: AsyncClient, plugin_preferences: User) -> None:
    payload = {"config": {"some_config": 123}}

    mock_preference = MagicMock()
    mock_preference.config = payload["config"]
    mock_preference.enabled = True

    with (
        patch(
            "sparkth.core.plugins.service.PluginService.apply_preprocess",
            new=AsyncMock(return_value=payload["config"]),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.apply_postprocess",
            new=AsyncMock(return_value=payload["config"]),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.apply_cache_sync",
            new=AsyncMock(),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.update_preference_config",
            new=AsyncMock(return_value=mock_preference),
        ),
        patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new=AsyncMock()),
        patch("sqlalchemy.ext.asyncio.AsyncSession.refresh", new=AsyncMock()),
    ):
        response = await client.put("/api/v1/plugins/plugin_a/config", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["config"] == payload["config"]
    assert data["is_core"] is True


async def test_update_plugin_success(client: AsyncClient, plugin_preferences: User) -> None:
    payload = {"config": {"some_config": 123}}

    mock_preference = MagicMock()
    mock_preference.config = payload["config"]
    mock_preference.enabled = True

    with (
        patch(
            "sparkth.core.plugins.service.PluginService.apply_preprocess",
            new=AsyncMock(return_value=payload["config"]),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.apply_postprocess",
            new=AsyncMock(return_value=payload["config"]),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.apply_cache_sync",
            new=AsyncMock(),
        ),
        patch(
            "sparkth.core.plugins.service.PluginService.update_preference_config",
            new=AsyncMock(return_value=mock_preference),
        ),
        patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new=AsyncMock()),
        patch("sqlalchemy.ext.asyncio.AsyncSession.refresh", new=AsyncMock()),
        patch("sparkth.core.plugins.service.PluginService.validate_user_config", return_value=payload),
    ):
        response = await client.put("/api/v1/plugins/plugin_b/config", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["plugin_name"] == "plugin_b"
    assert data["enabled"] is True
    assert data["config"] == payload["config"]
    assert data["is_core"] is True


async def test_update_plugin_not_found(client: AsyncClient, plugin_preferences: User) -> None:
    payload = {"config": {"some_config": 123}}

    response = await client.put("/api/v1/plugins/plugin_not_found/config", json=payload)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_update_admin_disabled_plugin(client: AsyncClient, plugin_preferences: User) -> None:
    payload = {"config": {"some_config": 123}}

    response = await client.put("/api/v1/plugins/disabled_plugin/config", json=payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_update_user_disabled_plugin(client: AsyncClient, plugin_preferences: User) -> None:
    payload = {"config": {"some_config": 123}}

    response = await client.put("/api/v1/plugins/configured_plugin_disabled/config", json=payload)

    assert response.status_code == status.HTTP_409_CONFLICT


async def test_update_plugin_invalid_config(client: AsyncClient, plugin_preferences: User) -> None:
    with patch(
        "sparkth.core.plugins.service.PluginService.validate_user_config",
        side_effect=ConfigValidationError("Invalid config"),
    ):
        response = await client.put(
            "/api/v1/plugins/plugin_a/config",
            json={"config": {"bad": "data"}},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid config"


async def test_update_plugin_value_error_is_a_bad_request(client: AsyncClient, plugin_preferences: User) -> None:
    with patch(
        "sparkth.core.plugins.service.PluginService.update_preference_config",
        side_effect=ValueError("Model not allowed"),
    ):
        response = await client.put("/api/v1/plugins/plugin_a/config", json={"config": {"model": "x"}})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Model not allowed"


async def test_update_plugin_internal_error_is_a_server_error(client: AsyncClient, plugin_preferences: User) -> None:
    with patch(
        "sparkth.core.plugins.service.PluginService.update_preference_config",
        side_effect=InternalServerError("Plugin cannot be configured"),
    ):
        response = await client.put("/api/v1/plugins/plugin_a/config", json={"config": {"some_config": 1}})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Plugin cannot be configured"
