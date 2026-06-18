import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from app.api.v1.auth import RequirePermission
from app.lib.permissions import SCOPE_GLOBAL
from app.models.user import User
from app.permissions.models import Role, RoleAssignment, RolePermission


def _request() -> Request:
    return Request({"type": "http"})


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
        session.add(RoleAssignment(user_id=user.id, role_id=role.id))
        await session.flush()
    return user


async def test_dependency_allows_when_granted(session: AsyncSession) -> None:
    user = await _seed(session, "alice", "assignment.grade")
    dep = RequirePermission("assignment.grade", SCOPE_GLOBAL)
    assert await dep(_request(), user, session) is user


async def test_dependency_denies_without_permission(session: AsyncSession) -> None:
    user = await _seed(session, "bob", None)
    dep = RequirePermission("assignment.grade", SCOPE_GLOBAL)
    with pytest.raises(HTTPException) as exc:
        await dep(_request(), user, session)
    assert exc.value.status_code == 403


async def test_dependency_resolves_scope_from_path_params(session: AsyncSession) -> None:
    user = await _seed(session, "carol", None)
    assert user.id is not None
    role = Role(name="course-grader")
    session.add(role)
    await session.flush()
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission="assignment.grade"))
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope_type="course", scope_id="5"))
    await session.flush()

    dep = RequirePermission("assignment.grade", "course", "course_id")

    granted = Request({"type": "http", "path_params": {"course_id": "5"}})
    assert await dep(granted, user, session) is user

    denied = Request({"type": "http", "path_params": {"course_id": "9"}})
    with pytest.raises(HTTPException) as exc:
        await dep(denied, user, session)
    assert exc.value.status_code == 403
