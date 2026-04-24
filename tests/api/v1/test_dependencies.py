from collections.abc import AsyncGenerator
from typing import cast

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.api.v1.dependencies import require_permission, require_role, require_superuser
from app.core.db import get_async_session
from app.models.rbac import RoleName
from app.models.user import User
from app.services.rbac import assign_role, seed_default_permissions


def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with dependency-protected routes."""
    test_app = FastAPI()

    @test_app.get("/test/admin-only")
    async def admin_only_route(user: User = Depends(require_role(RoleName.ADMIN))) -> dict[str, str]:
        return {"user": user.username}

    @test_app.get("/test/perm-users-list")
    async def perm_route(user: User = Depends(require_permission("users:list"))) -> dict[str, str]:
        return {"user": user.username}

    @test_app.get("/test/superuser-only")
    async def superuser_route(user: User = Depends(require_superuser)) -> dict[str, str]:
        return {"user": user.username}

    return test_app


async def _setup_users_and_perms(session: AsyncSession) -> tuple[User, User, User]:
    """Create superuser, admin, and member test users with roles and permissions."""
    superuser = User(name="Super", username="dep_super", email="dep_super@test.com", hashed_password="fake")
    admin = User(name="Admin", username="dep_admin", email="dep_admin@test.com", hashed_password="fake")
    member = User(name="Member", username="dep_member", email="dep_member@test.com", hashed_password="fake")
    session.add_all([superuser, admin, member])
    await session.flush()

    await assign_role(session, cast(int, superuser.id), RoleName.SUPERUSER)
    await assign_role(session, cast(int, admin.id), RoleName.ADMIN)
    await assign_role(session, cast(int, member.id), RoleName.MEMBER)
    await seed_default_permissions(session)

    return superuser, admin, member


def _override_deps(
    test_app: FastAPI,
    session: AsyncSession,
    user: User,
) -> None:
    """Set dependency overrides on the test app."""

    async def session_override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    async def user_override() -> User:
        return user

    test_app.dependency_overrides[get_async_session] = session_override
    test_app.dependency_overrides[get_current_user] = user_override


async def test_require_role_allows_correct_role(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/admin-only")
    assert response.status_code == 200
    assert response.json()["user"] == "dep_admin"


async def test_require_role_denies_wrong_role(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, member)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/admin-only")
    assert response.status_code == 403


async def test_require_role_allows_superuser(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, superuser)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/admin-only")
    assert response.status_code == 200
    assert response.json()["user"] == "dep_super"


async def test_require_permission_allows_when_granted(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, admin)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/perm-users-list")
    assert response.status_code == 200
    assert response.json()["user"] == "dep_admin"


async def test_require_permission_denies_when_not_granted(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, member)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/perm-users-list")
    assert response.status_code == 403


async def test_require_permission_superuser_bypass(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, superuser)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/perm-users-list")
    assert response.status_code == 200
    assert response.json()["user"] == "dep_super"


async def test_require_superuser_allows(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, superuser)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/superuser-only")
    assert response.status_code == 200
    assert response.json()["user"] == "dep_super"


async def test_require_superuser_denies(session: AsyncSession) -> None:
    superuser, admin, member = await _setup_users_and_perms(session)
    test_app = _build_test_app()
    _override_deps(test_app, session, member)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/test/superuser-only")
    assert response.status_code == 403
