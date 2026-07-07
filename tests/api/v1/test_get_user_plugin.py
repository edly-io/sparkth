from fastapi import status
from httpx import AsyncClient

from sparkth.core.models.user import User


async def test_get_user_plugin_success(client: AsyncClient, user_plugins: User) -> None:
    response = await client.get("/api/v1/user-plugins/plugin_a")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["plugin_name"] == "plugin_a"
    assert data["enabled"] is True
    assert data["is_core"] is True


async def test_get_user_plugin_not_found(client: AsyncClient, user_plugins: User) -> None:
    response = await client.get("/api/v1/user-plugins/plugin_abc")
    assert response.status_code == status.HTTP_404_NOT_FOUND
