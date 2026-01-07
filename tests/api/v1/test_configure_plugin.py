from typing import Any, cast
from unittest.mock import patch

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.v1.auth import get_current_user
from app.models.plugin import UserPlugin
from app.models.user import User
from app.services.plugin import ConfigValidationError, InternalServerError, PluginService


def test_create_plugin_success(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"config": {"some_config": 123}}

    with patch("app.services.plugin.PluginService.validate_user_config", return_value=payload["config"]):
        response = client.put("/api/v1/user-plugins/plugin_a/config", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["config"] == payload["config"]
    assert data["is_core"] is True


def test_update_plugin_success(override_dependencies: Any) -> None:
    client = override_dependencies
    payload = {"config": {"some_config": 456}}

    with patch("app.services.plugin.PluginService.validate_user_config", return_value=payload["config"]):
        response = client.put("/api/v1/user-plugins/plugin_b/config", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["plugin_name"] == "plugin_b"
    assert data["enabled"] is True
    assert data["config"] == payload["config"]
    assert data["is_core"] is True


def test_user_not_authenticated(client: TestClient) -> None:
    user = User(
        name="Test User",
        username="unauth_user",
        email="unauth@example.com",
        hashed_password="fakehashedpassword",
    )

    def get_user_override() -> User:
        return user

    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_current_user] = get_user_override

    response = client.put("/api/v1/user-plugins/plugin_a/config", json={"config": {}})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "authenticated" in response.json()["detail"]


def test_plugin_not_found(override_dependencies: Any) -> None:
    client = override_dependencies
    response = client.put("/api/v1/user-plugins/missing_plugin/config", json={"config": {}})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"]


def test_admin_disabled_plugin(override_dependencies: Any) -> None:
    client = override_dependencies
    response = client.put("/api/v1/user-plugins/disabled_plugin/config", json={"config": {}})
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "disabled" in response.json()["detail"]


def test_user_disabled_plugin(override_dependencies: Any) -> None:
    client = override_dependencies
    response = client.put(
        "/api/v1/user-plugins/configured_plugin_disabled/config",
        json={"config": {"some_config": 123}},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "disabled" in response.json()["detail"]


def test_invalid_config(override_dependencies: Any) -> None:
    client = override_dependencies

    with patch(
        "app.services.plugin.PluginService.validate_user_config",
        side_effect=ConfigValidationError("Invalid config"),
    ):
        response = client.put(
            "/api/v1/user-plugins/plugin_a/config",
            json={"config": {"bad": "data"}},
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Invalid config"


def test_internal_server_error_on_create(override_dependencies: Any) -> None:
    client = override_dependencies

    valid_config = {"some_config": 123}

    with (
        patch.object(
            PluginService,
            "validate_user_config",
            return_value=valid_config,
        ),
        patch.object(
            PluginService,
            "create_or_update_user_plugin_config",
            side_effect=InternalServerError("Plugin cannot be configured"),
        ),
    ):
        response = client.put(
            "/api/v1/user-plugins/plugin_a/config",
            json={"config": valid_config},
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Plugin cannot be configured"


def test_merge_existing_config(session: Session, override_dependencies: Any) -> None:
    client = override_dependencies
    existing_config = {"key1": 1}
    new_config = {"key2": 2}
    merged_config = {**existing_config, **new_config}

    user_plugin_instance = UserPlugin(
        user_id=1,
        plugin_id=1,
        enabled=True,
        config=existing_config,
    )
    session.add(user_plugin_instance)
    session.commit()

    with (
        patch(
            "app.services.plugin.PluginService.get_user_plugin",
            return_value=user_plugin_instance,
        ),
        patch(
            "app.services.plugin.PluginService.validate_user_config",
            return_value=merged_config,
        ),
    ):
        response = client.put("/api/v1/user-plugins/plugin_a/config", json={"config": new_config})

    assert response.status_code == 200
    data = response.json()
    assert data["config"] == merged_config
