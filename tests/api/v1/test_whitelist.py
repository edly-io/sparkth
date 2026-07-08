import uuid
from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import make_transient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.lib.auth import get_current_user

_WHITELIST_PERMISSIONS = ["email.whitelist.read", "email.whitelist.create", "email.whitelist.delete"]


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_user_with_permissions(session: AsyncSession, permissions: list[str]) -> User:
    user = User(
        name="Admin",
        username=_uniq("admin"),
        email=f"{_uniq('admin')}@example.com",
        hashed_password="fakehash",
    )
    session.add(user)
    await session.flush()
    assert user.id is not None
    role = Role(name=_uniq("role"))
    session.add(role)
    await session.flush()
    assert role.id is not None
    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission=permission))
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope="global", scope_object_id=None))
    await session.flush()
    return user


async def _create_whitelist_manager(session: AsyncSession, permissions: list[str]) -> User:
    """A user whose role is assigned at the whitelist scope (no global grant) — a Whitelist Manager."""
    user = User(
        name="Manager",
        username=_uniq("manager"),
        email=f"{_uniq('manager')}@example.com",
        hashed_password="fakehash",
    )
    session.add(user)
    await session.flush()
    assert user.id is not None
    role = Role(name=_uniq("role"))
    session.add(role)
    await session.flush()
    assert role.id is not None
    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission=permission))
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope="whitelist", scope_object_id=None))
    await session.flush()
    return user


async def _create_regular_user(session: AsyncSession) -> User:
    user = User(
        name="Regular",
        username=_uniq("regular"),
        email=f"{_uniq('regular')}@example.com",
        hashed_password="fakehash",
    )
    session.add(user)
    await session.flush()
    return user


def _override_current_user(client: AsyncClient, user: User) -> None:
    transport = cast(ASGITransport, client._transport)
    app_instance = cast(FastAPI, transport.app)

    # Snapshot the user's fields into a detached instance so SQLAlchemy never
    # tries to lazy-load attributes across request boundaries.
    snapshot = User(
        id=user.id,
        name=user.name,
        username=user.username,
        email=user.email,
        hashed_password=user.hashed_password,
    )
    make_transient(snapshot)

    async def override() -> User:
        return snapshot

    app_instance.dependency_overrides[get_current_user] = override


class TestListWhitelist:
    async def test_permitted_user_can_list(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_user_with_permissions(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, admin)

        response = await client.get("/api/v1/whitelist/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_regular_user_gets_403(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _create_regular_user(session)
        _override_current_user(client, user)

        response = await client.get("/api/v1/whitelist/")
        assert response.status_code == 403


class TestAddWhitelist:
    async def test_add_email(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_user_with_permissions(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, admin)

        email = f"{_uniq('user')}@example.com"
        response = await client.post("/api/v1/whitelist/", json={"value": email})
        assert response.status_code == 201
        data = response.json()
        assert data["value"] == email.lower()
        assert data["entry_type"] == "email"
        assert "id" in data

    async def test_add_domain(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_user_with_permissions(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, admin)

        domain = f"@{_uniq('org')}.com"
        response = await client.post("/api/v1/whitelist/", json={"value": domain})
        assert response.status_code == 201
        data = response.json()
        assert data["entry_type"] == "domain"

    async def test_add_duplicate_returns_409(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_user_with_permissions(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, admin)

        email = f"{_uniq('user')}@example.com"
        await client.post("/api/v1/whitelist/", json={"value": email})
        response = await client.post("/api/v1/whitelist/", json={"value": email})
        assert response.status_code == 409
        assert response.json()["detail"] == f"Entry already exists: {email}"

    async def test_add_invalid_returns_422(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_user_with_permissions(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, admin)

        response = await client.post("/api/v1/whitelist/", json={"value": "not-valid"})
        assert response.status_code == 422
        assert response.json()["detail"] == "Invalid email format: not-valid"

    async def test_read_only_user_cannot_create(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _create_user_with_permissions(session, ["email.whitelist.read"])
        _override_current_user(client, user)

        response = await client.post("/api/v1/whitelist/", json={"value": "a@b.com"})
        assert response.status_code == 403

    async def test_regular_user_gets_403(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _create_regular_user(session)
        _override_current_user(client, user)

        response = await client.post("/api/v1/whitelist/", json={"value": "a@b.com"})
        assert response.status_code == 403


class TestRemoveWhitelist:
    async def test_remove_entry(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_user_with_permissions(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, admin)

        email = f"{_uniq('user')}@example.com"
        add_response = await client.post("/api/v1/whitelist/", json={"value": email})
        entry_id = add_response.json()["id"]

        response = await client.delete(f"/api/v1/whitelist/{entry_id}")
        assert response.status_code == 204

    async def test_remove_nonexistent_returns_404(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_user_with_permissions(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, admin)

        response = await client.delete("/api/v1/whitelist/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Whitelist entry not found: 999999"

    async def test_regular_user_gets_403(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _create_regular_user(session)
        _override_current_user(client, user)

        response = await client.delete("/api/v1/whitelist/1")
        assert response.status_code == 403


class TestWhitelistManagerScope:
    async def test_manager_can_list(self, client: AsyncClient, session: AsyncSession) -> None:
        manager = await _create_whitelist_manager(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, manager)
        response = await client.get("/api/v1/whitelist/")
        assert response.status_code == 200

    async def test_manager_can_create(self, client: AsyncClient, session: AsyncSession) -> None:
        manager = await _create_whitelist_manager(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, manager)
        email = f"{_uniq('user')}@example.com"
        response = await client.post("/api/v1/whitelist/", json={"value": email})
        assert response.status_code == 201

    async def test_manager_can_delete(self, client: AsyncClient, session: AsyncSession) -> None:
        manager = await _create_whitelist_manager(session, _WHITELIST_PERMISSIONS)
        _override_current_user(client, manager)
        email = f"{_uniq('user')}@example.com"
        entry_id = (await client.post("/api/v1/whitelist/", json={"value": email})).json()["id"]
        response = await client.delete(f"/api/v1/whitelist/{entry_id}")
        assert response.status_code == 204

    async def test_read_only_manager_cannot_create(self, client: AsyncClient, session: AsyncSession) -> None:
        manager = await _create_whitelist_manager(session, ["email.whitelist.read"])
        _override_current_user(client, manager)
        response = await client.post("/api/v1/whitelist/", json={"value": "a@b.com"})
        assert response.status_code == 403


class TestWhitelistExceptionRegistration:
    def test_domain_exceptions_are_registered(self) -> None:
        """The API package registers its 3 domain exceptions on the central registry."""
        from sparkth.core.exceptions.handlers import EXCEPTION_HANDLERS
        from sparkth.services.whitelist import (
            InvalidWhitelistValue,
            WhitelistEntryAlreadyExists,
            WhitelistEntryNotFound,
        )

        registered = dict(EXCEPTION_HANDLERS.iter_items())
        assert WhitelistEntryAlreadyExists in registered
        assert WhitelistEntryNotFound in registered
        assert InvalidWhitelistValue in registered
