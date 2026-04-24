from collections.abc import AsyncGenerator
from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import get_current_user
from app.core.db import get_async_session
from app.models.rbac import RoleName
from app.models.user import User
from app.services.rbac import assign_role, seed_default_permissions


async def _setup_admin_test(session: AsyncSession) -> tuple[FastAPI, User, User, User]:
    """Create a test app with admin routes and users with roles."""
    test_app = FastAPI()
    test_app.include_router(admin_router, prefix="/api/v1/admin")

    superuser = User(name="Super", username="adm_super", email="adm_super@test.com", hashed_password="fake")
    admin = User(name="Admin", username="adm_admin", email="adm_admin@test.com", hashed_password="fake")
    member = User(name="Member", username="adm_member", email="adm_member@test.com", hashed_password="fake")
    session.add_all([superuser, admin, member])
    await session.flush()

    await assign_role(session, cast(int, superuser.id), RoleName.SUPERUSER)
    await assign_role(session, cast(int, admin.id), RoleName.ADMIN)
    await assign_role(session, cast(int, member.id), RoleName.MEMBER)
    await seed_default_permissions(session)

    return test_app, superuser, admin, member


def _set_overrides(
    test_app: FastAPI,
    session: AsyncSession,
    user: User,
) -> None:
    async def session_override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    async def user_override() -> User:
        return user

    test_app.dependency_overrides[get_async_session] = session_override
    test_app.dependency_overrides[get_current_user] = user_override


async def test_list_users_as_admin(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/users")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    assert len(data["users"]) >= 3


async def test_list_users_as_member(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, member)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/users")
    assert response.status_code == 403


async def test_list_users_as_superuser(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, superuser)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/users")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3


async def test_get_user_detail_with_roles(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/admin/users/{member.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "adm_member"
    assert "member" in data["roles"]


async def test_get_user_detail_not_found(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/users/99999")
    assert response.status_code == 404


async def test_assign_role_as_admin(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/admin/users/{member.id}/roles",
            json={"role": "admin"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "admin" in data["roles"]


async def test_assign_role_as_member(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, member)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/admin/users/{admin.id}/roles",
            json={"role": "superuser"},
        )
    assert response.status_code == 403


async def test_assign_role_invalid_role(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/admin/users/{member.id}/roles",
            json={"role": "nonexistent"},
        )
    assert response.status_code == 422


async def test_deactivate_user_as_admin(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(f"/api/v1/admin/users/{member.id}/deactivate")
    assert response.status_code == 200
    assert response.json()["detail"] == "User deactivated"


async def test_deactivate_user_as_member(session: AsyncSession) -> None:
    test_app, superuser, admin, member = await _setup_admin_test(session)
    _set_overrides(test_app, session, member)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch(f"/api/v1/admin/users/{admin.id}/deactivate")
    assert response.status_code == 403
