"""Tests for /api/v1/llm/configs endpoints."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import get_current_user
from app.api.v1.llm import get_llm_service
from app.core.db import get_async_session
from app.main import app
from app.models.user import User

_LLM_ENDPOINTS = [
    ("POST", "/api/v1/llm/configs"),
    ("GET", "/api/v1/llm/configs"),
    ("PATCH", "/api/v1/llm/configs/1"),
    ("PUT", "/api/v1/llm/configs/1/key"),
    ("PATCH", "/api/v1/llm/configs/1/active"),
    ("DELETE", "/api/v1/llm/configs/1"),
]

_TEST_USER = User(
    id=1,
    name="LLM Test User",
    username="llmuser",
    email="llm@example.com",
    hashed_password="fakehash",
)


@pytest.fixture
async def llm_client() -> AsyncGenerator[AsyncClient, None]:
    mock_session = AsyncMock()

    async def get_session_override() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    async def get_user_override() -> User:
        return _TEST_USER

    app.dependency_overrides[get_async_session] = get_session_override
    app.dependency_overrides[get_current_user] = get_user_override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_async_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_llm_service, None)


@pytest.mark.asyncio
async def test_create_config_returns_201(llm_client: AsyncClient) -> None:
    from app.models import LLMConfig

    mock_service = MagicMock()
    created = LLMConfig(
        id=1,
        user_id=1,
        name="My Key",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
        created_at=datetime.now(timezone.utc),
    )
    mock_service.create = AsyncMock(return_value=created)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.post(
        "/api/v1/llm/configs",
        json={
            "name": "My Key",
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "api_key": "sk-real-key",
        },
    )

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["id"] == 1
    assert data["masked_key"] == "sk-...abcd"
    assert "encrypted_key" not in data
    assert "api_key" not in data


@pytest.mark.asyncio
async def test_list_configs_returns_only_current_user(llm_client: AsyncClient) -> None:
    from app.models import LLMConfig

    mock_service = MagicMock()
    configs = [
        LLMConfig(
            id=1,
            user_id=1,
            name="Key A",
            provider="openai",
            model="gpt-4o",
            encrypted_key="enc",
            masked_key="sk-...1111",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    mock_service.list = AsyncMock(return_value=configs)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.get("/api/v1/llm/configs")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data["configs"]) == 1
    assert data["configs"][0]["name"] == "Key A"
    assert "encrypted_key" not in data["configs"][0]


@pytest.mark.asyncio
async def test_update_config_with_valid_model_returns_200(llm_client: AsyncClient) -> None:
    from app.models import LLMConfig

    mock_service = MagicMock()
    updated = LLMConfig(
        id=1,
        user_id=1,
        name="My Key",
        provider="openai",
        model="gpt-4o-mini",
        encrypted_key="enc",
        masked_key="sk-...abcd",
        created_at=datetime.now(timezone.utc),
    )
    mock_service.update = AsyncMock(return_value=updated)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.patch("/api/v1/llm/configs/1", json={"model": "gpt-4o-mini"})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_update_config_with_invalid_model_returns_400(llm_client: AsyncClient) -> None:
    from app.llm.exceptions import LLMConfigValidationError

    mock_service = MagicMock()
    mock_service.update = AsyncMock(
        side_effect=LLMConfigValidationError("Model 'invalid-model' not available for provider 'openai'.")
    )
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.patch("/api/v1/llm/configs/1", json={"model": "invalid-model"})

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "not available" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_own_config_returns_204(llm_client: AsyncClient) -> None:
    mock_service = MagicMock()
    mock_service.delete = AsyncMock(return_value=True)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.delete("/api/v1/llm/configs/1")

    assert resp.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_delete_not_found_returns_404(llm_client: AsyncClient) -> None:
    mock_service = MagicMock()
    mock_service.delete = AsyncMock(return_value=False)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.delete("/api/v1/llm/configs/99")

    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_deactivate_config_returns_200(llm_client: AsyncClient) -> None:
    from app.models import LLMConfig

    mock_service = MagicMock()
    deactivated = LLMConfig(
        id=1,
        user_id=1,
        name="My Key",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
        is_active=False,
        created_at=datetime.now(timezone.utc),
    )
    mock_service.set_active = AsyncMock(return_value=deactivated)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.patch("/api/v1/llm/configs/1/active", json={"is_active": False})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["is_active"] is False
    mock_service.set_active.assert_called_once()


@pytest.mark.asyncio
async def test_activate_config_returns_200(llm_client: AsyncClient) -> None:
    from app.models import LLMConfig

    mock_service = MagicMock()
    activated = LLMConfig(
        id=1,
        user_id=1,
        name="My Key",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    mock_service.set_active = AsyncMock(return_value=activated)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.patch("/api/v1/llm/configs/1/active", json={"is_active": True})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_set_active_not_found_returns_404(llm_client: AsyncClient) -> None:
    mock_service = MagicMock()
    mock_service.set_active = AsyncMock(side_effect=ValueError("LLMConfig 99 not found"))
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.patch("/api/v1/llm/configs/99/active", json={"is_active": False})

    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_rotate_key_returns_200(llm_client: AsyncClient) -> None:
    from app.models import LLMConfig

    mock_service = MagicMock()
    rotated = LLMConfig(
        id=1,
        user_id=1,
        name="My Key",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc-new",
        masked_key="sk-...wxyz",
        created_at=datetime.now(timezone.utc),
    )
    mock_service.rotate_key = AsyncMock(return_value=rotated)
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.put("/api/v1/llm/configs/1/key", json={"api_key": "sk-brand-new-key"})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["masked_key"] == "sk-...wxyz"
    assert "encrypted_key" not in resp.json()
    mock_service.rotate_key.assert_called_once()


@pytest.mark.asyncio
async def test_rotate_key_not_found_returns_404(llm_client: AsyncClient) -> None:
    mock_service = MagicMock()
    mock_service.rotate_key = AsyncMock(side_effect=ValueError("LLMConfig 99 not found"))
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.put("/api/v1/llm/configs/99/key", json={"api_key": "sk-key"})

    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(llm_client: AsyncClient) -> None:
    mock_service = MagicMock()
    mock_service.create = AsyncMock(
        side_effect=ValueError("An LLM config with name 'My Key' already exists for this user.")
    )
    app.dependency_overrides[get_llm_service] = lambda: mock_service

    resp = await llm_client.post(
        "/api/v1/llm/configs",
        json={
            "name": "My Key",
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "api_key": "sk-key",
        },
    )

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", _LLM_ENDPOINTS)
async def test_unauthenticated_request_is_rejected(method: str, path: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.request(method, path, json={})
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
