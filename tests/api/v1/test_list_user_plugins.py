from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.v1.auth import get_current_user
from app.models import User
from app.services.plugin import PluginService, get_plugin_service


def test_list_user_plugins_basic(override_dependencies: Any) -> None:
    client = override_dependencies

    response = client.get("/api/v1/user-plugins/")
    assert response.status_code == 200

    data = response.json()
    expected = [
        {
            "plugin_name": "plugin_a",
            "enabled": True,
            "config": {},
            "is_builtin": True,
        },
        {
            "plugin_name": "plugin_b",
            "enabled": True,
            "config": {"some config": "abc"},
            "is_builtin": True,
        },
        {
            "plugin_name": "configured_plugin_disabled",
            "enabled": False,
            "config": {"some config": "abc"},
            "is_builtin": True,
        },
        {
            "plugin_name": "disabled_plugin",
            "enabled": True,
            "config": {},
            "is_builtin": True,
        },
    ]
    assert data == expected


def test_list_user_plugins_empty(client: TestClient, session: Session) -> None:
    user = User(name="Test User", username="noplugins", email="empty@example.com", hashed_password="fakehashedpassword")
    session.add(user)
    session.commit()
    session.refresh(user)

    def get_user_override() -> User:
        return user

    def get_plugin_service_override() -> PluginService:
        return PluginService()

    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_current_user] = get_user_override
    app.dependency_overrides[get_plugin_service] = get_plugin_service_override

    response = client.get("/api/v1/user-plugins/")
    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides.clear()
