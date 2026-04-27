import uuid
from typing import cast

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import make_transient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.auth import get_current_user
from app.models.user import User


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_superuser(session: AsyncSession) -> User:
    user = User(
        name="Admin",
        username=_uniq("admin"),
        email=f"{_uniq('admin')}@example.com",
        hashed_password="fakehash",
        is_superuser=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_regular_user(session: AsyncSession) -> User:
    user = User(
        name="Regular",
        username=_uniq("regular"),
        email=f"{_uniq('regular')}@example.com",
        hashed_password="fakehash",
        is_superuser=False,
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
        is_superuser=user.is_superuser,
    )
    make_transient(snapshot)

    async def override() -> User:
        return snapshot

    app_instance.dependency_overrides[get_current_user] = override


class TestListWhitelist:
    async def test_superuser_can_list(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_superuser(session)
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
        admin = await _create_superuser(session)
        _override_current_user(client, admin)

        email = f"{_uniq('user')}@example.com"
        response = await client.post("/api/v1/whitelist/", json={"value": email})
        assert response.status_code == 201
        data = response.json()
        assert data["value"] == email.lower()
        assert data["entry_type"] == "email"
        assert "id" in data

    async def test_add_domain(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_superuser(session)
        _override_current_user(client, admin)

        domain = f"@{_uniq('org')}.com"
        response = await client.post("/api/v1/whitelist/", json={"value": domain})
        assert response.status_code == 201
        data = response.json()
        assert data["entry_type"] == "domain"

    async def test_add_duplicate_returns_409(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_superuser(session)
        _override_current_user(client, admin)

        email = f"{_uniq('user')}@example.com"
        await client.post("/api/v1/whitelist/", json={"value": email})
        response = await client.post("/api/v1/whitelist/", json={"value": email})
        assert response.status_code == 409

    async def test_add_invalid_returns_422(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_superuser(session)
        _override_current_user(client, admin)

        response = await client.post("/api/v1/whitelist/", json={"value": "not-valid"})
        assert response.status_code == 422

    async def test_regular_user_gets_403(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _create_regular_user(session)
        _override_current_user(client, user)

        response = await client.post("/api/v1/whitelist/", json={"value": "a@b.com"})
        assert response.status_code == 403


class TestRemoveWhitelist:
    async def test_remove_entry(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_superuser(session)
        _override_current_user(client, admin)

        email = f"{_uniq('user')}@example.com"
        add_response = await client.post("/api/v1/whitelist/", json={"value": email})
        entry_id = add_response.json()["id"]

        response = await client.delete(f"/api/v1/whitelist/{entry_id}")
        assert response.status_code == 204

    async def test_remove_nonexistent_returns_404(self, client: AsyncClient, session: AsyncSession) -> None:
        admin = await _create_superuser(session)
        _override_current_user(client, admin)

        response = await client.delete("/api/v1/whitelist/999999")
        assert response.status_code == 404

    async def test_regular_user_gets_403(self, client: AsyncClient, session: AsyncSession) -> None:
        user = await _create_regular_user(session)
        _override_current_user(client, user)

        response = await client.delete("/api/v1/whitelist/1")
        assert response.status_code == 403
