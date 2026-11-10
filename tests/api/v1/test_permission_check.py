from typing import cast

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.permissions.scopes import ROLE
from sparkth.lib.testing import grant_global_permission, grant_permission_at_scope

URL = "/api/v1/permissions/can"


@pytest.fixture
async def role_grant(session: AsyncSession, current_user: User) -> None:
    """Give the current user ``analytics.read`` at ``role:5`` only."""
    await grant_permission_at_scope(session, cast(int, current_user.id), "analytics.read", ROLE, "5")
    await session.commit()


async def test_can_true_when_user_holds_permission(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await grant_global_permission(session, cast(int, current_user.id), "analytics.read")
    await session.commit()

    resp = await client.get(URL, params={"permission": "analytics.read"})
    assert resp.status_code == 200
    assert resp.json() == {"allowed": True}


async def test_can_false_without_permission(client: AsyncClient, current_user: User) -> None:
    resp = await client.get(URL, params={"permission": "analytics.read"})
    assert resp.status_code == 200
    assert resp.json() == {"allowed": False}


async def test_can_unknown_permission_returns_422(client: AsyncClient, current_user: User) -> None:
    resp = await client.get(URL, params={"permission": "does.not.exist"})
    assert resp.status_code == 422


async def test_can_unknown_scope_returns_422(client: AsyncClient, current_user: User) -> None:
    resp = await client.get(URL, params={"permission": "analytics.read", "scope": "nope"})
    assert resp.status_code == 422


async def test_can_requires_authentication(client: AsyncClient) -> None:
    # Missing credentials are a 401 (not 403): FastAPI 0.140 answers the security
    # dependency per RFC 9110 with WWW-Authenticate. (Authenticated-but-denied stays 403.)
    resp = await client.get(URL, params={"permission": "analytics.read"})
    assert resp.status_code == 401


@pytest.mark.usefixtures("role_grant")
async def test_can_at_an_object_is_true_for_the_granted_object_only(client: AsyncClient) -> None:
    params = {"permission": "analytics.read", "scope": ROLE.name}

    assert (await client.get(URL, params={**params, "scope_object_id": "5"})).json() == {"allowed": True}
    assert (await client.get(URL, params={**params, "scope_object_id": "6"})).json() == {"allowed": False}
    assert (await client.get(URL, params=params)).json() == {"allowed": False}


@pytest.mark.usefixtures("role_grant")
async def test_can_with_an_object_id_containing_a_slash_returns_422(client: AsyncClient) -> None:
    resp = await client.get(URL, params={"permission": "analytics.read", "scope": ROLE.name, "scope_object_id": "5/x"})
    assert resp.status_code == 422


@pytest.mark.usefixtures("role_grant")
async def test_can_resolves_the_permission_before_the_scope(client: AsyncClient) -> None:
    resp = await client.get(URL, params={"permission": "does.not.exist", "scope": "nope"})
    assert resp.status_code == 422
    assert "does.not.exist" in str(resp.json()["detail"])
