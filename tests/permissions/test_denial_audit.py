"""A refusal from the ``Permission.require*`` dependencies lands a
``permission.denied`` audit row that survives the request's rollback, and the
write is fail-closed. Granted requests and the ``/permissions/can`` probe
record nothing."""

from collections.abc import Awaitable, Callable

import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from pytest import MonkeyPatch, raises
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.core.permissions.scopes import PERMISSION_SCOPES, PermissionScope
from sparkth.core.security import create_access_token
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import Permission
from sparkth.lib.permissions.scopes import GLOBAL
from sparkth.lib.testing import AuditEventsFetcher

ROLES_URL = "/api/v1/permissions/roles"


async def _user(session: AsyncSession, username: str, permission: str | None = None) -> User:
    user = User(name="T", username=username, email=f"{username}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    if permission is not None:
        assert user.id is not None
        role = Role(name=f"{username}-role")
        session.add(role)
        await session.flush()
        assert role.id is not None
        session.add(RolePermission(role_id=role.id, permission=permission))
        session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope="global", scope_object_id=None))
    await session.commit()
    await session.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}


async def test_denied_request_records_permission_denied_event(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "denied-alice")

    response = await client.get(ROLES_URL, headers=_auth(user))
    assert response.status_code == 403

    (event,) = await audit_events()
    assert event.category == "permission"
    assert event.action == "denied"
    assert event.outcome == "denied"
    assert event.actor_type == "user"
    assert event.actor_id == str(user.id)
    assert event.target_type == "permission"
    assert event.target_id == "role.read"
    assert event.error_detail == "scope=role"


async def test_denied_scoped_request_names_the_scope_object(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "denied-bob")

    response = await client.get(f"{ROLES_URL}/7", headers=_auth(user))
    assert response.status_code == 403

    (event,) = await audit_events()
    assert event.target_id == "role.read"
    assert event.error_detail == "scope=role:7"


async def test_granted_request_records_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "granted-carol", "role.read")

    response = await client.get(ROLES_URL, headers=_auth(user))
    assert response.status_code == 200

    assert await audit_events() == []


async def test_permission_probe_records_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "probe-dave")

    response = await client.get("/api/v1/permissions/can", params={"permission": "analytics.read"}, headers=_auth(user))
    assert response.status_code == 200
    assert response.json() == {"allowed": False}

    assert await audit_events() == []


async def test_denial_is_fail_closed_when_audit_write_fails(
    client: AsyncClient, session: AsyncSession, monkeypatch: MonkeyPatch
) -> None:
    user = await _user(session, "broken-erin")

    async def broken_record(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("audit unavailable")

    monkeypatch.setattr("sparkth.core.permissions.record_event_now", broken_record)

    with raises(SQLAlchemyError):
        await client.get(ROLES_URL, headers=_auth(user))


class _QuizNotFound(Exception):
    """Raised by the object-id dependency when the record does not exist."""


async def not_found(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "Quiz not found"}, status_code=404)


async def probe() -> dict[str, bool]:
    return {"ok": True}


def _object_id_client(
    session: AsyncSession, scope: PermissionScope, scope_object_id: Callable[..., Awaitable[str]]
) -> AsyncClient:
    """A one-route app gated by ``require(scope, scope_object_id=...)`` with the real auth dependency."""
    app = FastAPI()

    async def db() -> AsyncSession:
        return session

    app.dependency_overrides[get_async_session] = db

    app.add_exception_handler(_QuizNotFound, not_found)

    app.get("/probe", dependencies=[Depends(Permission("quiz.read").require(scope, None, scope_object_id))])(probe)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def quiz_scope(monkeypatch: MonkeyPatch) -> PermissionScope:
    scope = PermissionScope("quiz", parent=GLOBAL)
    monkeypatch.setitem(PERMISSION_SCOPES._items, "quiz", scope)
    return scope


async def missing_quiz() -> str:
    raise _QuizNotFound()


async def quiz_id() -> str:
    return "7"


async def test_missing_object_is_404_and_records_no_denial(
    session: AsyncSession, quiz_scope: PermissionScope, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "notfound-fay")

    async with _object_id_client(session, quiz_scope, missing_quiz) as client:
        response = await client.get("/probe", headers=_auth(user))

    assert response.status_code == 404
    assert await audit_events() == []


async def test_unauthenticated_request_is_401_before_the_object_id_dependency(
    session: AsyncSession, quiz_scope: PermissionScope
) -> None:
    ran: list[bool] = []

    async def quiz_id() -> str:
        ran.append(True)
        return "7"

    async with _object_id_client(session, quiz_scope, quiz_id) as client:
        response = await client.get("/probe")

    assert response.status_code == 401
    assert ran == []


async def test_denial_names_the_object_id_the_check_ran_at(
    session: AsyncSession, quiz_scope: PermissionScope, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "denied-gus")

    async with _object_id_client(session, quiz_scope, quiz_id) as client:
        response = await client.get("/probe", headers=_auth(user))

    assert response.status_code == 403
    (event,) = await audit_events()
    assert event.error_detail == "scope=quiz:7"
