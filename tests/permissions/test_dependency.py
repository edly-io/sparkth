import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from app.core.permissions.models import Role, RoleAssignment, RolePermission
from app.core.permissions.scopes import PERMISSION_SCOPES, ObjectScope, PermissionScope
from app.lib.permissions import Permission
from app.lib.permissions.scopes import GLOBAL
from app.models.user import User


def _request() -> Request:
    return Request({"type": "http"})


@pytest.fixture
def course_scope(monkeypatch: pytest.MonkeyPatch) -> PermissionScope:
    """Register a 'course' scope on the global hook for the duration of one test.

    PERMISSION_SCOPES is a process-wide singleton with no reset and a duplicate guard, so
    patch its backing dict via monkeypatch (auto-restored) rather than calling create()/
    add_item(), which would leak the scope into every later test.
    """
    scope = ObjectScope("course", parent=GLOBAL)
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


async def test_dependency_allows_when_granted(session: AsyncSession) -> None:
    user = await _seed(session, "alice", "assignment.grade")
    dep = Permission("assignment.grade").require_in_global_scope()
    assert await dep(_request(), user, session) is user


async def test_dependency_denies_without_permission(session: AsyncSession) -> None:
    user = await _seed(session, "bob", None)
    dep = Permission("assignment.grade").require_in_global_scope()
    with pytest.raises(HTTPException) as exc:
        await dep(_request(), user, session)
    assert exc.value.status_code == 403


async def test_dependency_resolves_scope_from_path_params(session: AsyncSession, course_scope: PermissionScope) -> None:
    user = await _seed(session, "carol", None)
    assert user.id is not None
    role = Role(name="course-grader")
    session.add(role)
    await session.flush()
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission="assignment.grade"))
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope="course", scope_object_id="5"))
    await session.flush()

    dep = Permission("assignment.grade").require(course_scope, "course_id")

    granted = Request({"type": "http", "path_params": {"course_id": "5"}})
    assert await dep(granted, user, session) is user

    denied = Request({"type": "http", "path_params": {"course_id": "9"}})
    with pytest.raises(HTTPException) as exc:
        await dep(denied, user, session)
    assert exc.value.status_code == 403


async def test_dependency_raises_for_missing_scope_param(session: AsyncSession, course_scope: PermissionScope) -> None:
    # scope_param names a path parameter the route doesn't provide — a wiring error, not an auth
    # failure. The dependency raises a plain exception (FastAPI turns it into a 500), never a
    # silent 403.
    user = await _seed(session, "dave", None)
    dep = Permission("assignment.grade").require(course_scope, "course_id")
    with pytest.raises(RuntimeError):
        await dep(_request(), user, session)


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
    with pytest.raises(HTTPException) as exc:
        await dep(_request(), user, session)
    assert exc.value.status_code == 403


def test_require_objectless_scope_rejects_scope_param() -> None:
    # GLOBAL is objectless -> naming a path param is a wiring error, caught at definition time.
    with pytest.raises(ValueError):
        Permission("assignment.grade").require(GLOBAL, "course_id")


def test_require_object_bearing_scope_requires_scope_param(course_scope: PermissionScope) -> None:
    with pytest.raises(ValueError):
        Permission("assignment.grade").require(course_scope)


async def test_require_objectless_scope_allows_no_param(session: AsyncSession) -> None:
    # require(GLOBAL) with no object id authorizes a global grant.
    user = await _seed(session, "gwen", "assignment.grade")
    dep = Permission("assignment.grade").require(GLOBAL)
    assert await dep(_request(), user, session) is user
