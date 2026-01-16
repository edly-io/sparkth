from typing import Any, cast
from unittest.mock import patch

from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import get_current_user
from app.models.user import User
from app.services.plugin import ConfigValidationError, InternalServerError


async def test_configure_user_plugin_success(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"some_config": 123}

    with patch("app.services.plugin.PluginService.validate_user_config", return_value=payload):
        response = await client.post("/api/v1/user-plugins/plugin_a/configure", json=payload)

    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["config"] == payload
    assert data["is_core"] is True


async def test_configure_user_plugin_unauthorized(client: AsyncClient) -> None:
    user = User(
        name="Test User",
        username="unauthorized_user",
        email="unauthorized@example.com",
        hashed_password="fakehashedpassword",
    )

    def get_user_override() -> User:
        return user

    transport = cast(ASGITransport, client._transport)
    app = cast(FastAPI, transport.app)
    app.dependency_overrides[get_current_user] = get_user_override

    response = await client.post("/api/v1/user-plugins/plugin_a/configure", json={})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_configure_user_plugin_not_found(override_dependencies: Any) -> None:
    client = override_dependencies
    response = await client.post("/api/v1/user-plugins/missing_plugin/configure", json={})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"]


async def test_configure_user_plugin_admin_disabled(override_dependencies: Any) -> None:
    client = override_dependencies

    response = await client.post("/api/v1/user-plugins/disabled_plugin/configure", json={})
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "not enabled" in response.json()["detail"]


async def test_configure_user_plugin_already_configured(override_dependencies: Any) -> None:
    client = override_dependencies
    response = await client.post("/api/v1/user-plugins/plugin_b/configure", json={})
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already configured" in response.json()["detail"]


async def test_configure_user_plugin_invalid_config(override_dependencies: Any) -> None:
    client = override_dependencies

    with patch(
        "app.services.plugin.PluginService.validate_user_config",
        side_effect=ConfigValidationError("Invalid config"),
    ):
        response = await client.post(
            "/api/v1/user-plugins/plugin_a/configure",
            json={"bad": "data"},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid config"


async def test_configure_user_plugin_internal_error(override_dependencies: Any) -> None:
    client = override_dependencies

    with patch(
        "app.services.plugin.PluginService.validate_user_config",
        side_effect=InternalServerError("Plugin cannot be configured"),
    ):
        response = await client.post(
            "/api/v1/user-plugins/plugin_a/configure",
            json={"some confix": "abc"},
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Plugin cannot be configured"
