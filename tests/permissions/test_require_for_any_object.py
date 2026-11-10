"""``Permission.require_for_any_object`` gates a route that names no object and hands the handler the
ids of the objects the caller holds the permission at.
Authored with LLM (Claude) assistance."""

from collections.abc import Callable

from fastapi import Depends
from httpx import AsyncClient
from pytest import raises
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.permissions import GROUP_READ
from sparkth.lib.permissions.scopes import GLOBAL, GROUP
from sparkth.lib.testing import AuditEventsFetcher, assign, make_role, make_user


async def _user_with_grants(session: AsyncSession, username: str, grants: list[tuple[str, str | None]]) -> User:
    """A committed user holding ``group.read`` at each ``(scope, scope_object_id)`` in ``grants``."""
    user = await make_user(session, username)
    for scope, scope_object_id in grants:
        role = await make_role(session, f"{username}-{scope}-{scope_object_id}", ["group.read"])
        await assign(session, user, role, scope, scope_object_id)
    await session.commit()
    await session.refresh(user)
    return user


async def ids_route(
    accessible_ids: set[str] | None = Depends(GROUP_READ.require_for_any_object(GROUP)),
) -> dict[str, list[str] | None]:
    """Echo the accessible ids the dependency returns."""
    return {"ids": None if accessible_ids is None else sorted(accessible_ids)}


async def test_holder_at_two_objects_gets_exactly_those_ids(
    session: AsyncSession, gated_client: Callable[..., AsyncClient]
) -> None:
    user = await _user_with_grants(session, "alice", [("group", "7"), ("group", "13")])
    async with gated_client(None, user, endpoint=ids_route) as client:
        response = await client.get("/probe")
    assert response.status_code == 200
    assert response.json() == {"ids": ["13", "7"]}


async def test_global_holder_gets_no_restriction(
    session: AsyncSession, gated_client: Callable[..., AsyncClient]
) -> None:
    user = await _user_with_grants(session, "bob", [(GLOBAL.name, None)])
    async with gated_client(None, user, endpoint=ids_route) as client:
        response = await client.get("/probe")
    assert response.status_code == 200
    assert response.json() == {"ids": None}


async def test_holder_nowhere_is_refused_and_the_refusal_is_audited(
    session: AsyncSession, gated_client: Callable[..., AsyncClient], audit_events: AuditEventsFetcher
) -> None:
    user = await _user_with_grants(session, "carol", [])
    async with gated_client(None, user, endpoint=ids_route) as client:
        response = await client.get("/probe")
    assert response.status_code == 403
    (event,) = await audit_events()
    assert event.action == "denied"
    assert event.target_id == "group.read"
    assert event.error_detail == "scope=group"


async def test_unauthenticated_request_is_refused_before_any_check(
    gated_client: Callable[..., AsyncClient], audit_events: AuditEventsFetcher
) -> None:
    async with gated_client(None, endpoint=ids_route) as client:
        response = await client.get("/probe")
    assert response.status_code == 401
    assert await audit_events() == []


def test_an_objectless_scope_is_a_wiring_error() -> None:
    with raises(ValueError):
        GROUP_READ.require_for_any_object(GLOBAL)
