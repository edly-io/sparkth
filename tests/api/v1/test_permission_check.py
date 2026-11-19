from typing import cast

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.permissions.scopes import GROUP, ROLE, WHITELIST
from sparkth.lib.testing import AuditEventsFetcher, grant_global_permission, grant_permission_at_scope

URL = "/api/v1/permissions/can"
BATCH_URL = f"{URL}/batch"


@pytest.fixture
async def role_grant(session: AsyncSession, current_user: User) -> None:
    """Give the current user ``analytics.read`` at ``role:5`` only."""
    await grant_permission_at_scope(session, cast(int, current_user.id), "analytics.read", ROLE, "5")
    await session.commit()


async def test_can_false_without_permission(client: AsyncClient, current_user: User) -> None:
    resp = await client.post(URL, json={"permission": "analytics.read", "scope": "global"})
    assert resp.status_code == 200
    assert resp.json() == {"allowed": False}


async def test_can_unknown_scope_returns_422(client: AsyncClient, current_user: User) -> None:
    resp = await client.post(URL, json={"permission": "analytics.read", "scope": "nope"})
    assert resp.status_code == 422


async def test_can_without_an_object_id_is_true_for_a_global_grant(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await grant_global_permission(session, cast(int, current_user.id), "analytics.read")
    await session.commit()

    resp = await client.post(URL, json={"permission": "analytics.read", "scope": ROLE.name})
    assert resp.json() == {"allowed": True}


async def test_can_without_an_object_id_is_false_when_held_at_no_object(
    client: AsyncClient, current_user: User
) -> None:
    resp = await client.post(URL, json={"permission": "analytics.read", "scope": ROLE.name})
    assert resp.json() == {"allowed": False}


@pytest.mark.usefixtures("role_grant")
async def test_can_without_an_object_id_ignores_grants_at_other_scopes(client: AsyncClient) -> None:
    resp = await client.post(URL, json={"permission": "analytics.read", "scope": GROUP.name})
    assert resp.json() == {"allowed": False}


async def test_can_at_an_objectless_scope_is_true_for_a_global_grant(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await grant_global_permission(session, cast(int, current_user.id), "email.whitelist.read")
    await session.commit()

    resp = await client.post(URL, json={"permission": "email.whitelist.read", "scope": WHITELIST.name})
    assert resp.json() == {"allowed": True}


@pytest.mark.usefixtures("role_grant")
async def test_can_with_an_object_id_containing_a_slash_returns_422(client: AsyncClient) -> None:
    resp = await client.post(URL, json={"permission": "analytics.read", "scope": ROLE.name, "scope_object_id": "5/x"})
    assert resp.status_code == 422


@pytest.mark.usefixtures("role_grant")
async def test_can_resolves_the_permission_before_the_scope(client: AsyncClient) -> None:
    resp = await client.post(URL, json={"permission": "does.not.exist", "scope": "nope"})
    assert resp.status_code == 422
    assert "does.not.exist" in str(resp.json()["detail"])


async def test_can_answers_one_check(client: AsyncClient, session: AsyncSession, current_user: User) -> None:
    await grant_global_permission(session, cast(int, current_user.id), "analytics.read")
    await session.commit()

    resp = await client.post(URL, json={"permission": "analytics.read", "scope": "global"})
    assert resp.status_code == 200
    assert resp.json() == {"allowed": True}


@pytest.mark.usefixtures("role_grant")
async def test_can_at_an_object_and_at_any_object(client: AsyncClient) -> None:
    check = {"permission": "analytics.read", "scope": ROLE.name}

    assert (await client.post(URL, json={**check, "scope_object_id": "5"})).json() == {"allowed": True}
    assert (await client.post(URL, json={**check, "scope_object_id": "6"})).json() == {"allowed": False}
    assert (await client.post(URL, json=check)).json() == {"allowed": True}


async def test_can_unknown_permission_returns_422(client: AsyncClient, current_user: User) -> None:
    resp = await client.post(URL, json={"permission": "does.not.exist", "scope": "global"})
    assert resp.status_code == 422
    assert "does.not.exist" in str(resp.json()["detail"])


@pytest.mark.usefixtures("role_grant")
async def test_batch_answers_in_request_order_and_echoes_each_check(client: AsyncClient) -> None:
    resp = await client.post(
        BATCH_URL,
        json=[
            {"permission": "analytics.read", "scope": ROLE.name, "scope_object_id": "5"},
            {"permission": "analytics.read", "scope": ROLE.name, "scope_object_id": "6"},
            {"permission": "analytics.read", "scope": ROLE.name},
            {"permission": "analytics.read", "scope": "global"},
        ],
    )

    assert resp.status_code == 200
    assert resp.json() == [
        {"permission": "analytics.read", "scope": "role", "scope_object_id": "5", "allowed": True},
        {"permission": "analytics.read", "scope": "role", "scope_object_id": "6", "allowed": False},
        {"permission": "analytics.read", "scope": "role", "scope_object_id": None, "allowed": True},
        {"permission": "analytics.read", "scope": "global", "scope_object_id": None, "allowed": False},
    ]


async def test_batch_unknown_permission_fails_the_whole_request(client: AsyncClient, current_user: User) -> None:
    resp = await client.post(
        BATCH_URL,
        json=[{"permission": "analytics.read", "scope": "global"}, {"permission": "does.not.exist", "scope": "global"}],
    )
    assert resp.status_code == 422
    assert "does.not.exist" in str(resp.json()["detail"])


async def test_batch_unknown_scope_returns_422(client: AsyncClient, current_user: User) -> None:
    resp = await client.post(BATCH_URL, json=[{"permission": "analytics.read", "scope": "nope"}])
    assert resp.status_code == 422


async def test_batch_object_id_with_a_slash_returns_422(client: AsyncClient, current_user: User) -> None:
    check = {"permission": "analytics.read", "scope": ROLE.name, "scope_object_id": "5/x"}
    resp = await client.post(BATCH_URL, json=[check])
    assert resp.status_code == 422


async def test_batch_accepts_50_checks_and_rejects_51(client: AsyncClient, current_user: User) -> None:
    check = {"permission": "analytics.read", "scope": "global"}

    accepted = await client.post(BATCH_URL, json=[check] * 50)
    assert accepted.status_code == 200
    assert len(accepted.json()) == 50
    assert (await client.post(BATCH_URL, json=[check] * 51)).status_code == 422


async def test_batch_with_no_checks_returns_an_empty_list(client: AsyncClient, current_user: User) -> None:
    resp = await client.post(BATCH_URL, json=[])
    assert resp.status_code == 200
    assert resp.json() == []


async def test_can_and_batch_require_authentication(client: AsyncClient) -> None:
    assert (await client.post(URL, json={"permission": "analytics.read", "scope": "global"})).status_code == 401
    assert (await client.post(BATCH_URL, json=[{"permission": "analytics.read", "scope": "global"}])).status_code == 401


async def test_can_and_batch_record_no_audit_event(
    client: AsyncClient, current_user: User, audit_events: AuditEventsFetcher
) -> None:
    assert (await client.post(URL, json={"permission": "analytics.read", "scope": "global"})).json() == {
        "allowed": False
    }
    batch = await client.post(BATCH_URL, json=[{"permission": "analytics.read", "scope": "global"}])
    assert batch.json()[0]["allowed"] is False

    assert await audit_events() == []


async def test_get_can_is_not_served(client: AsyncClient, current_user: User) -> None:
    resp = await client.get(URL, params={"permission": "analytics.read"})
    assert resp.status_code == 405


async def test_can_without_a_scope_returns_422(client: AsyncClient, current_user: User) -> None:
    resp = await client.post(URL, json={"permission": "analytics.read"})
    assert resp.status_code == 422


async def test_batch_check_without_a_scope_fails_the_whole_request(client: AsyncClient, current_user: User) -> None:
    checks = [{"permission": "analytics.read", "scope": "global"}, {"permission": "analytics.read"}]
    resp = await client.post(BATCH_URL, json=checks)
    assert resp.status_code == 422
