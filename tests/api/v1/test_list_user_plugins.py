from typing import Any, cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.models import User
from app.services.plugin import PluginService, get_plugin_service


async def test_list_user_plugins_basic(override_dependencies: Any) -> None:
    client = override_dependencies

    response = await client.get("/api/v1/user-plugins/")
    assert response.status_code == 200

    data = response.json()
    expected = [
        {
            "plugin_name": "plugin_a",
            "enabled": True,
            "config": {},
            "is_core": True,
        },
        {
            "plugin_name": "plugin_b",
            "enabled": True,
            "config": {"some config": "abc"},
            "is_core": True,
        },
        {
            "plugin_name": "configured_plugin_disabled",
            "enabled": False,
            "config": {"some config": "abc"},
            "is_core": True,
        },
        {
            "plugin_name": "disabled_plugin",
            "enabled": True,
            "config": {},
            "is_core": True,
        },
    ]
    assert data == expected


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
