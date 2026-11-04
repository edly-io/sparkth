"""``Permission.require_accessible`` gates a route that names no object and hands the handler the
ids of the objects the caller holds the permission at.
Authored with LLM (Claude) assistance."""

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pytest import raises
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.core.security import create_access_token
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import GROUP_READ
from sparkth.lib.permissions.scopes import GLOBAL, GROUP
from sparkth.lib.testing import AuditEventsFetcher


async def _user_with_grants(session: AsyncSession, username: str, grants: list[tuple[str, str | None]]) -> User:
    """A committed user holding ``group.read`` at each ``(scope, scope_object_id)`` in ``grants``."""
    user = User(name="T", username=username, email=f"{username}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    assert user.id is not None
    for scope, scope_object_id in grants:
        role = Role(name=f"{username}-{scope}-{scope_object_id}")
        session.add(role)
        await session.flush()
        assert role.id is not None
        session.add(RolePermission(role_id=role.id, permission="group.read"))
        session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=scope, scope_object_id=scope_object_id))
    await session.commit()
    await session.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}


def _client(session: AsyncSession) -> AsyncClient:
    """A one-route app whose handler echoes the accessible ids the dependency returns."""
    app = FastAPI()

    async def db() -> AsyncSession:
        return session

    app.dependency_overrides[get_async_session] = db

    @app.get("/probe")
    async def probe(
        accessible_ids: set[str] | None = Depends(GROUP_READ.require_accessible(GROUP)),
    ) -> dict[str, list[str] | None]:
        return {"ids": None if accessible_ids is None else sorted(accessible_ids)}

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_holder_at_two_objects_gets_exactly_those_ids(session: AsyncSession) -> None:
    user = await _user_with_grants(session, "alice", [("group", "7"), ("group", "13")])
    async with _client(session) as client:
        response = await client.get("/probe", headers=_headers(user))
    assert response.status_code == 200
    assert response.json() == {"ids": ["13", "7"]}


async def test_global_holder_gets_no_restriction(session: AsyncSession) -> None:
    user = await _user_with_grants(session, "bob", [(GLOBAL.name, None)])
    async with _client(session) as client:
        response = await client.get("/probe", headers=_headers(user))
    assert response.status_code == 200
    assert response.json() == {"ids": None}


async def test_holder_nowhere_is_refused_and_the_refusal_is_audited(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user_with_grants(session, "carol", [])
    async with _client(session) as client:
        response = await client.get("/probe", headers=_headers(user))
    assert response.status_code == 403
    (event,) = await audit_events()
    assert event.action == "denied"
    assert event.target_id == "group.read"
    assert event.error_detail == "scope=group"


async def test_unauthenticated_request_is_refused_before_any_check(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    async with _client(session) as client:
        response = await client.get("/probe")
    assert response.status_code == 401
    assert await audit_events() == []


def test_an_objectless_scope_is_a_wiring_error() -> None:
    with raises(ValueError):
        GROUP_READ.require_accessible(GLOBAL)
