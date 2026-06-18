import pytest
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from app.api.v1.auth import RequirePermission
from app.models.permissions import Role, RoleAssignment, RolePermission
from app.models.user import User


def _request() -> Request:
    return Request({"type": "http"})


async def _seed(session: AsyncSession, username: str, permission: str | None, is_superuser: bool = False) -> User:
    user = User(
        name="T",
        username=username,
        email=f"{username}@e.com",
        hashed_password="x",
        is_superuser=is_superuser,
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
    dep = RequirePermission("assignment.grade")
    assert await dep(_request(), user, session) is user


async def test_dependency_denies_without_permission(session: AsyncSession) -> None:
    user = await _seed(session, "bob", None)
    dep = RequirePermission("assignment.grade")
    with pytest.raises(HTTPException) as exc:
        await dep(_request(), user, session)
    assert exc.value.status_code == 403


async def test_dependency_allows_superuser(session: AsyncSession) -> None:
    user = await _seed(session, "root", None, is_superuser=True)
    dep = RequirePermission("assignment.grade")
    assert await dep(_request(), user, session) is user
