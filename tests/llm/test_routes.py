"""Tests for /api/v1/llm/configs endpoints, gated at the config owner's user scope."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models import LLMConfig
from sparkth.core.permissions.models import RoleAssignment
from sparkth.lib.permissions.scopes import GLOBAL, USER
from sparkth.lib.testing import AuditEventsFetcher, grant_permission_at_scope
from sparkth.main import app

OWNER_ID = 2
THIRD_ID = 3
READ = "llm.config.read"
UPDATE = "llm.config.update"
DELETE = "llm.config.delete"

_LLM_ENDPOINTS = [
    ("POST", "/api/v1/llm/configs"),
    ("GET", "/api/v1/llm/configs"),
    ("PATCH", "/api/v1/llm/configs/1"),
    ("PUT", "/api/v1/llm/configs/1/key"),
    ("PATCH", "/api/v1/llm/configs/1/active"),
    ("DELETE", "/api/v1/llm/configs/1"),
]

_CREATE_BODY = {"name": "My Key", "provider": "anthropic", "model": "claude-sonnet-4-20250514", "api_key": "sk-key"}

# (method, path suffix, body, permission, success status) per by-id route.
_BY_ID_ROUTES = [
    ("PATCH", "", {"name": "renamed"}, UPDATE, status.HTTP_200_OK),
    ("PUT", "/key", {"api_key": "sk-brand-new-key"}, UPDATE, status.HTTP_200_OK),
    ("PATCH", "/active", {"is_active": False}, UPDATE, status.HTTP_200_OK),
    ("DELETE", "", None, DELETE, status.HTTP_204_NO_CONTENT),
]
_BY_ID = pytest.mark.parametrize("method,suffix,body,permission,success", _BY_ID_ROUTES)

# The stored field each by-id route changes, and its new value, keyed by (method, suffix).
_STORED_CHANGE: dict[tuple[str, str], tuple[str, Any]] = {
    ("PATCH", ""): ("name", "renamed"),
    ("PUT", "/key"): ("masked_key", "sk-****-key"),
    ("PATCH", "/active"): ("is_active", False),
    ("DELETE", ""): ("is_deleted", True),
}

Call = Callable[..., Awaitable[Any]]


async def _seed(session: AsyncSession, user_id: int, name: str = "Key", **fields: Any) -> int:
    config = LLMConfig(
        user_id=user_id,
        name=name,
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
        **fields,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    assert config.id is not None
    return config.id


async def _drop_caller_assignment(session: AsyncSession) -> None:
    await session.exec(delete(RoleAssignment))
    await session.commit()


async def _stored(session: AsyncSession, config_id: int) -> LLMConfig:
    session.expire_all()
    result = await session.exec(select(LLMConfig).where(col(LLMConfig.id) == config_id))
    return result.one()


@pytest.fixture
def call(client: AsyncClient) -> Call:
    async def _call(method: str, config_id: int, suffix: str, body: dict[str, Any] | None) -> Any:
        return await client.request(method, f"/api/v1/llm/configs/{config_id}{suffix}", json=body)

    return _call


# ===========================================================================
# Behaviour of the routes for the owner
# ===========================================================================


async def test_create_config_returns_201(client: AsyncClient, current_user: object) -> None:
    resp = await client.post("/api/v1/llm/configs", json={**_CREATE_BODY, "api_key": "sk-real-key"})

    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["name"] == "My Key"
    assert "encrypted_key" not in data
    assert "api_key" not in data


async def test_create_duplicate_name_returns_409(client: AsyncClient, current_user: object) -> None:
    await client.post("/api/v1/llm/configs", json=_CREATE_BODY)

    resp = await client.post("/api/v1/llm/configs", json=_CREATE_BODY)

    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in resp.json()["detail"]


async def test_update_config_with_valid_model_returns_200(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    config_id = await _seed(session, 1)

    resp = await client.patch(f"/api/v1/llm/configs/{config_id}", json={"model": "claude-haiku-4-5"})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["model"] == "claude-haiku-4-5"


async def test_update_config_with_invalid_model_returns_400(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    config_id = await _seed(session, 1)

    resp = await client.patch(f"/api/v1/llm/configs/{config_id}", json={"model": "invalid-model"})

    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "not available" in resp.json()["detail"]


async def test_update_with_empty_body_returns_422(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    config_id = await _seed(session, 1)

    resp = await client.patch(f"/api/v1/llm/configs/{config_id}", json={})

    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_delete_own_config_returns_204(client: AsyncClient, current_user: object, session: AsyncSession) -> None:
    config_id = await _seed(session, 1)

    resp = await client.delete(f"/api/v1/llm/configs/{config_id}")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert (await _stored(session, config_id)).is_deleted is True


async def test_deactivate_then_activate_config(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    config_id = await _seed(session, 1)

    off = await client.patch(f"/api/v1/llm/configs/{config_id}/active", json={"is_active": False})
    on = await client.patch(f"/api/v1/llm/configs/{config_id}/active", json={"is_active": True})

    assert off.json()["is_active"] is False
    assert on.json()["is_active"] is True


async def test_rotate_key_returns_200(client: AsyncClient, current_user: object, session: AsyncSession) -> None:
    config_id = await _seed(session, 1)

    resp = await client.put(f"/api/v1/llm/configs/{config_id}/key", json={"api_key": "sk-brand-new-wxyz"})

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["masked_key"].endswith("wxyz")
    assert "encrypted_key" not in resp.json()


async def test_soft_deleted_config_is_404(client: AsyncClient, current_user: object, session: AsyncSession) -> None:
    config_id = await _seed(session, 1, is_deleted=True)

    assert (await client.delete(f"/api/v1/llm/configs/{config_id}")).status_code == status.HTTP_404_NOT_FOUND


async def test_inactive_config_can_be_reactivated(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    config_id = await _seed(session, 1, is_active=False)

    resp = await client.patch(f"/api/v1/llm/configs/{config_id}/active", json={"is_active": True})

    assert resp.status_code == status.HTTP_200_OK


@pytest.mark.parametrize("method,path", _LLM_ENDPOINTS)
async def test_unauthenticated_request_is_rejected(method: str, path: str) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.request(method, path, json={})
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# Create gate
# ===========================================================================


async def test_create_without_the_callers_own_grant_is_403(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    await _drop_caller_assignment(session)

    assert (await client.post("/api/v1/llm/configs", json=_CREATE_BODY)).status_code == status.HTTP_403_FORBIDDEN


# ===========================================================================
# By-id gates
# ===========================================================================


@_BY_ID
async def test_own_record_without_a_grant_is_403(
    call: Call,
    current_user: object,
    session: AsyncSession,
    method: str,
    suffix: str,
    body: Any,
    permission: str,
    success: int,
) -> None:
    config_id = await _seed(session, 1)
    await _drop_caller_assignment(session)

    assert (await call(method, config_id, suffix, body)).status_code == status.HTTP_403_FORBIDDEN


@_BY_ID
async def test_another_users_record_is_403_and_audited(
    call: Call,
    current_user: object,
    session: AsyncSession,
    audit_events: AuditEventsFetcher,
    method: str,
    suffix: str,
    body: Any,
    permission: str,
    success: int,
) -> None:
    config_id = await _seed(session, OWNER_ID)

    assert (await call(method, config_id, suffix, body)).status_code == status.HTTP_403_FORBIDDEN

    (event,) = await audit_events()
    assert event.action == "denied"
    assert event.target_id == permission
    assert event.error_detail == f"scope=user:{OWNER_ID}"
    assert (await _stored(session, config_id)).is_deleted is False


@_BY_ID
@pytest.mark.parametrize("scope_id", [None, str(OWNER_ID)])
async def test_grant_at_global_or_owner_reaches_it(
    call: Call,
    current_user: object,
    session: AsyncSession,
    method: str,
    suffix: str,
    body: Any,
    permission: str,
    success: int,
    scope_id: str | None,
) -> None:
    config_id = await _seed(session, OWNER_ID)
    await grant_permission_at_scope(session, 1, permission, GLOBAL if scope_id is None else USER, scope_id)
    await session.commit()

    response = await call(method, config_id, suffix, body)

    assert response.status_code == success
    stored = await _stored(session, config_id)
    assert stored.user_id == OWNER_ID
    field, expected = _STORED_CHANGE[(method, suffix)]
    assert getattr(stored, field) == expected


@_BY_ID
async def test_grant_at_a_third_user_is_403(
    call: Call,
    current_user: object,
    session: AsyncSession,
    method: str,
    suffix: str,
    body: Any,
    permission: str,
    success: int,
) -> None:
    config_id = await _seed(session, OWNER_ID)
    await grant_permission_at_scope(session, 1, permission, USER, str(THIRD_ID))
    await session.commit()

    assert (await call(method, config_id, suffix, body)).status_code == status.HTTP_403_FORBIDDEN


@_BY_ID
async def test_unknown_id_is_404_without_a_denial_row(
    call: Call,
    current_user: object,
    session: AsyncSession,
    audit_events: AuditEventsFetcher,
    method: str,
    suffix: str,
    body: Any,
    permission: str,
    success: int,
) -> None:
    await _drop_caller_assignment(session)

    assert (await call(method, 999999, suffix, body)).status_code == status.HTTP_404_NOT_FOUND
    assert await audit_events() == []


@_BY_ID
async def test_read_alone_cannot_change(
    call: Call,
    current_user: object,
    session: AsyncSession,
    method: str,
    suffix: str,
    body: Any,
    permission: str,
    success: int,
) -> None:
    config_id = await _seed(session, OWNER_ID)
    await grant_permission_at_scope(session, 1, READ, GLOBAL)
    await session.commit()

    assert (await call(method, config_id, suffix, body)).status_code == status.HTTP_403_FORBIDDEN


async def test_update_alone_cannot_delete(call: Call, current_user: object, session: AsyncSession) -> None:
    config_id = await _seed(session, OWNER_ID)
    await grant_permission_at_scope(session, 1, UPDATE, GLOBAL)
    await session.commit()

    assert (await call("DELETE", config_id, "", None)).status_code == status.HTTP_403_FORBIDDEN


async def test_holder_rename_checks_the_owners_names(
    call: Call, current_user: object, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    owner_a = await _seed(session, OWNER_ID, "a")
    await _seed(session, OWNER_ID, "b")
    caller_b = await _seed(session, 1, "b")
    await grant_permission_at_scope(session, 1, UPDATE, GLOBAL)
    await session.commit()

    assert (await call("PATCH", owner_a, "", {"name": "b"})).status_code == status.HTTP_409_CONFLICT
    assert (await call("PATCH", owner_a, "", {"name": "c"})).status_code == status.HTTP_200_OK

    assert (await _stored(session, owner_a)).name == "c"
    assert (await _stored(session, caller_b)).name == "b"
    events = [e for e in await audit_events() if e.action != "denied"]
    assert events
    assert {e.actor_id for e in events} == {"1"}


# ===========================================================================
# List gate
# ===========================================================================


async def test_list_shows_only_the_callers_even_with_a_global_grant(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    await _seed(session, 1, "mine")
    await _seed(session, OWNER_ID, "theirs")
    await grant_permission_at_scope(session, 1, READ, GLOBAL)
    await session.commit()

    body = (await client.get("/api/v1/llm/configs")).json()

    assert [c["name"] for c in body["configs"]] == ["mine"]


async def test_list_of_another_owner_needs_a_grant(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    await _seed(session, OWNER_ID)

    assert (await client.get(f"/api/v1/llm/configs?owner_id={OWNER_ID}")).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.parametrize("scope_id", [None, str(OWNER_ID)])
async def test_list_of_another_owner_with_a_grant(
    client: AsyncClient, current_user: object, session: AsyncSession, scope_id: str | None
) -> None:
    await _seed(session, 1, "mine")
    await _seed(session, OWNER_ID, "theirs")
    await grant_permission_at_scope(session, 1, READ, GLOBAL if scope_id is None else USER, scope_id)
    await session.commit()

    body = (await client.get(f"/api/v1/llm/configs?owner_id={OWNER_ID}")).json()

    assert [c["name"] for c in body["configs"]] == ["theirs"]


async def test_list_of_a_user_with_no_configs_is_empty(
    client: AsyncClient, current_user: object, session: AsyncSession
) -> None:
    await grant_permission_at_scope(session, 1, READ, GLOBAL)
    await session.commit()

    body = (await client.get("/api/v1/llm/configs?owner_id=999999")).json()

    assert body == {"configs": [], "total": 0}
