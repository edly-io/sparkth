"""Tests for listing and reading users over the REST API."""

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.permissions.scopes import USER
from sparkth.lib.testing import grant_permission_at_scope, login_as, make_user, make_user_with_permissions


async def test_list_users_returns_summaries(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["user.read"])
    await session.commit()
    login_as(client, caller)
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
    assert response.json() == [
        {"id": caller.id, "name": caller.name, "username": caller.username, "email": caller.email}
    ]


async def test_list_users_filters_by_search(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["user.read"])
    wanted = await make_user(session, "zebra_unique")
    await make_user(session, "other_person")
    await session.commit()
    login_as(client, caller)
    response = await client.get("/api/v1/users", params={"search": "bra_uni"})
    assert [row["id"] for row in response.json()] == [wanted.id]


async def test_list_users_pages(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["user.read"])
    for username in ("page_a", "page_b", "page_c"):
        await make_user(session, username)
    await session.commit()
    login_as(client, caller)
    response = await client.get("/api/v1/users", params={"search": "page_", "limit": 1, "offset": 1})
    assert [row["username"] for row in response.json()] == ["page_b"]


async def test_list_users_rejects_limit_over_200(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["user.read"])
    await session.commit()
    login_as(client, caller)
    response = await client.get("/api/v1/users", params={"limit": 201})
    assert response.status_code == 422


async def test_get_user_returns_summary(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["user.read"])
    target = await make_user(session, "lookup_target")
    await session.commit()
    login_as(client, caller)
    response = await client.get(f"/api/v1/users/{target.id}")
    assert response.status_code == 200
    assert response.json() == {
        "id": target.id,
        "name": target.name,
        "username": "lookup_target",
        "email": "lookup_target@example.com",
    }


async def test_get_unknown_user_returns_404(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, ["user.read"])
    await session.commit()
    login_as(client, caller)
    response = await client.get("/api/v1/users/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found: 999999"


async def test_users_routes_refuse_a_caller_without_user_read(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user_with_permissions(session, [])
    await session.commit()
    login_as(client, caller)
    assert (await client.get("/api/v1/users")).status_code == 403
    assert (await client.get(f"/api/v1/users/{caller.id}")).status_code == 403


async def test_user_read_at_a_user_scope_does_not_list_users(client: AsyncClient, session: AsyncSession) -> None:
    caller = await make_user(session, "scoped_reader")
    assert caller.id is not None
    await grant_permission_at_scope(session, caller.id, "user.read", USER, str(caller.id))
    await session.commit()
    login_as(client, caller)
    assert (await client.get("/api/v1/users")).status_code == 403
