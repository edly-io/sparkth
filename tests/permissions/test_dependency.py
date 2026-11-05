from collections.abc import Awaitable, Callable

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.core.permissions.scopes import PERMISSION_SCOPES, PermissionScope
from sparkth.core.permissions.scopes.mixins import ScopeObjectMixin
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import Permission
from sparkth.lib.permissions.scopes import GLOBAL


class _Course(ScopeObjectMixin):
    id: int


async def probe() -> dict[str, bool]:
    return {"ok": True}


async def course_id() -> str:
    return "5"


async def other_id() -> str:
    return "6"


async def course() -> _Course:
    return _Course(id=42, scope_path="org:5/course:42")


async def other_course() -> _Course:
    return _Course(id=42, scope_path="org:6/course:42")


def _client(
    session: AsyncSession, user: User, dep: Callable[..., Awaitable[User]], path: str = "/probe"
) -> AsyncClient:
    """An async client for a one-route app gated by ``dep``, run as ``user`` on ``session``."""
    app = FastAPI()

    async def current_user() -> User:
        return user

    async def db() -> AsyncSession:
        return session

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_async_session] = db

    app.get(path, dependencies=[Depends(dep)])(probe)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def course_scope(monkeypatch: pytest.MonkeyPatch) -> PermissionScope:
    """Register a 'course' scope on the global hook for the duration of one test.

    PERMISSION_SCOPES is a process-wide singleton with no reset and a duplicate guard, so
    patch its backing dict via monkeypatch (auto-restored) rather than calling create()/
    add_item(), which would leak the scope into every later test.
    """
    scope = PermissionScope("course", parent=GLOBAL)
    monkeypatch.setitem(PERMISSION_SCOPES._items, "course", scope)
    return scope


async def _seed(session: AsyncSession, username: str, permission: str | None) -> User:
    user = User(
        name="T",
        username=username,
        email=f"{username}@e.com",
        hashed_password="x",
    )
    session.add(user)
    await session.flush()
    if permission is not None:
        assert user.id is not None
        role = Role(name=f"{username}-role")
        session.add(role)
        await session.flush()
        assert role.id is not None
        session.add(RolePermission(role_id=role.id, permission=permission))
        session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
        await session.flush()
    return user


async def _grant(session: AsyncSession, user: User, scope: str, scope_object_id: str) -> None:
    """Give ``user`` a role holding ``assignment.grade`` at ``scope``/``scope_object_id``."""
    assert user.id is not None
    role = Role(name=f"{user.username}-{scope}-{scope_object_id}")
    session.add(role)
    await session.flush()
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission="assignment.grade"))
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=scope, scope_object_id=scope_object_id))
    await session.flush()


async def test_dependency_allows_when_granted(session: AsyncSession) -> None:
    user = await _seed(session, "alice", "assignment.grade")
    dep = Permission("assignment.grade").require_in_global_scope()
    async with _client(session, user, dep) as client:
        assert (await client.get("/probe")).status_code == 200


async def test_dependency_denies_without_permission(session: AsyncSession) -> None:
    user = await _seed(session, "bob", None)
    dep = Permission("assignment.grade").require_in_global_scope()
    async with _client(session, user, dep) as client:
        assert (await client.get("/probe")).status_code == 403


async def test_dependency_resolves_scope_from_path_params(session: AsyncSession, course_scope: PermissionScope) -> None:
    user = await _seed(session, "carol", None)
    await _grant(session, user, "course", "5")
    dep = Permission("assignment.grade").require(course_scope, "course_id")

    async with _client(session, user, dep, "/c/{course_id}") as client:
        assert (await client.get("/c/5")).status_code == 200
        assert (await client.get("/c/9")).status_code == 403


async def test_dependency_raises_for_missing_scope_param(session: AsyncSession, course_scope: PermissionScope) -> None:
    # scope_param names a path parameter the route doesn't provide — a wiring error, not an auth
    # failure. The dependency raises a plain exception (FastAPI turns it into a 500), never a
    # silent 403.
    user = await _seed(session, "dave", None)
    dep = Permission("assignment.grade").require(course_scope, "course_id")
    async with _client(session, user, dep) as client:
        with pytest.raises(RuntimeError):
            await client.get("/probe")


async def test_dependency_denies_admin_role_without_the_checked_permission(session: AsyncSession) -> None:
    # Holding the global admin role is not a bypass: authorization is purely permission-based,
    # so an admin role that does not grant the checked permission is still denied.
    user = await _seed(session, "erin", None)
    assert user.id is not None
    role = Role(name="admin")
    session.add(role)
    await session.flush()
    assert role.id is not None
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()

    dep = Permission("assignment.grade").require_in_global_scope()
    async with _client(session, user, dep) as client:
        assert (await client.get("/probe")).status_code == 403


def test_require_objectless_scope_rejects_scope_param() -> None:
    # GLOBAL is objectless -> naming a path param is a wiring error, caught at definition time.
    with pytest.raises(ValueError):
        Permission("assignment.grade").require(GLOBAL, "course_id")


def test_require_object_bearing_scope_requires_a_scope_param_or_scope_object_id(course_scope: PermissionScope) -> None:
    with pytest.raises(ValueError):
        Permission("assignment.grade").require(course_scope)


def test_require_rejects_both_scope_param_and_object_id(course_scope: PermissionScope) -> None:
    with pytest.raises(ValueError):
        Permission("assignment.grade").require(course_scope, "course_id", "5")


def test_require_objectless_scope_rejects_object_id() -> None:
    with pytest.raises(ValueError):
        Permission("assignment.grade").require(GLOBAL, None, "5")


async def test_require_objectless_scope_allows_no_param(session: AsyncSession) -> None:
    # require(GLOBAL) with no object id authorizes a global grant.
    user = await _seed(session, "gwen", "assignment.grade")
    dep = Permission("assignment.grade").require(GLOBAL)
    async with _client(session, user, dep) as client:
        assert (await client.get("/probe")).status_code == 200


async def test_require_fixed_object_id(session: AsyncSession, course_scope: PermissionScope) -> None:
    user = await _seed(session, "hank", None)
    await _grant(session, user, "course", "5")
    granted = Permission("assignment.grade").require(course_scope, None, "5")
    other = Permission("assignment.grade").require(course_scope, None, "6")

    async with _client(session, user, granted) as client:
        assert (await client.get("/probe")).status_code == 200
    async with _client(session, user, other) as client:
        assert (await client.get("/probe")).status_code == 403


async def test_require_object_id_dependency_returning_str(session: AsyncSession, course_scope: PermissionScope) -> None:
    user = await _seed(session, "ivy", None)
    await _grant(session, user, "course", "5")

    granted = Permission("assignment.grade").require(course_scope, None, course_id)
    other = Permission("assignment.grade").require(course_scope, None, other_id)
    async with _client(session, user, granted) as client:
        assert (await client.get("/probe")).status_code == 200
    async with _client(session, user, other) as client:
        assert (await client.get("/probe")).status_code == 403


async def test_require_object_id_dependency_returning_a_scope_object_cascades(
    session: AsyncSession, course_scope: PermissionScope
) -> None:
    user = await _seed(session, "jay", None)
    await _grant(session, user, "org", "5")

    granted = Permission("assignment.grade").require(course_scope, None, course)
    other = Permission("assignment.grade").require(course_scope, None, other_course)
    async with _client(session, user, granted) as client:
        assert (await client.get("/probe")).status_code == 200
    async with _client(session, user, other) as client:
        assert (await client.get("/probe")).status_code == 403
