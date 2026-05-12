"""Tests for GET /api/v1/llm/providers endpoint."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import get_current_user
from app.main import app
from app.models.user import User

_TEST_USER = User(
    id=1,
    name="LLM Test User",
    username="llmuser",
    email="llm@example.com",
    hashed_password="fakehash",
)


@pytest.fixture
async def auth_client() -> AsyncGenerator[AsyncClient, None]:
    async def get_user_override() -> User:
        return _TEST_USER

    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_list_providers(auth_client: AsyncClient) -> None:
    """GET /api/v1/llm/providers returns the provider catalog."""
    response = await auth_client.get("/api/v1/llm/providers")
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "default_provider" in data
    assert "default_model" in data
    assert len(data["providers"]) > 0
    provider = data["providers"][0]
    assert "id" in provider
    assert "label" in provider
    assert "models" in provider
    assert isinstance(provider["models"], list)
