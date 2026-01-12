from typing import Any
from unittest.mock import patch

from fastapi import status

from app.services.plugin import ConfigValidationError


async def test_update_plugin_not_configured_success(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"config": {"some_config": 123}}

    with patch("app.services.plugin.PluginService.validate_user_config", return_value=payload):
        response = await client.put("/api/v1/user-plugins/plugin_a/config", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["config"] == payload
    assert data["is_core"] is True


async def test_update_plugin_success(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"config": {"some_config": 123}}

    with patch("app.services.plugin.PluginService.validate_user_config", return_value=payload):
        response = await client.put("/api/v1/user-plugins/plugin_b/config", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["plugin_name"] == "plugin_b"
    assert data["enabled"] is True
    assert data["config"] == payload
    assert data["is_core"] is True


async def test_update_plugin_not_found(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"config": {"some_config": 123}}

    response = await client.put("/api/v1/user-plugins/plugin_not_found/config", json=payload)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_update_admin_disabled_plugin(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"config": {"some_config": 123}}

    response = await client.put("/api/v1/user-plugins/disabled_plugin/config", json=payload)

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_update_user_disabled_plugin(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"config": {"some_config": 123}}

    response = await client.put("/api/v1/user-plugins/configured_plugin_disabled/config", json=payload)

    assert response.status_code == status.HTTP_409_CONFLICT


async def test_update_user_plugin_invalid_config(override_dependencies: Any) -> None:
    client = override_dependencies

    with patch(
        "app.services.plugin.PluginService.validate_user_config",
        side_effect=ConfigValidationError("Invalid config"),
    ):
        response = await client.put(
            "/api/v1/user-plugins/plugin_a/config",
            json={"config": {"bad": "data"}},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid config"
