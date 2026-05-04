import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User
from app.services.whitelist import WhitelistService


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def create_user_in_db(
    session: AsyncSession,
    *,
    name: str = "Test User",
    username: str | None = None,
    email: str | None = None,
    password: str = "testpassword",
    email_verified: bool = True,
) -> User:
    username = username or _uniq("testuser")
    email = email or f"{_uniq('test')}@example.com"

    user = User(
        name=name,
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        email_verified=email_verified,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_create_user(client: AsyncClient, session: AsyncSession) -> None:
    username = _uniq("testuser")
    email = f"{_uniq('test')}@example.com"

    await WhitelistService.add_entry(session, value=email, added_by_id=1)

    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Test User",
                "username": username,
                "email": email,
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email
    assert data["username"] == username
    assert "id" in data
    assert "hashed_password" not in data


async def test_create_user_existing_username(client: AsyncClient, session: AsyncSession) -> None:
    username = _uniq("testuser")
    await create_user_in_db(session, username=username, email=f"{_uniq('test')}@example.com")

    new_email = f"{_uniq('another')}@example.com"
    await WhitelistService.add_entry(session, value=new_email, added_by_id=1)

    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Another User",
                "username": username,
                "email": new_email,
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}


async def test_create_user_existing_email(client: AsyncClient, session: AsyncSession) -> None:
    email = f"{_uniq('test')}@example.com"
    await create_user_in_db(session, username=_uniq("testuser"), email=email)

    await WhitelistService.add_entry(session, value=email, added_by_id=1)

    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Another User",
                "username": _uniq("anotheruser"),
                "email": email,
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}


# Optional: Add a test for when registration is disabled
async def test_registration_disabled(client: AsyncClient) -> None:
    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", False):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Test User",
                "username": "testuser",
                "email": "test@example.com",
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 403
    assert response.json() == {"detail": "Registration is currently disabled"}


async def test_login(client: AsyncClient, session: AsyncSession) -> None:
    password = "testpassword"
    username = _uniq("testuser")
    await create_user_in_db(session, username=username, email=f"{_uniq('test')}@example.com", password=password)

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, session: AsyncSession) -> None:
    username = _uniq("testuser")
    await create_user_in_db(session, username=username, email=f"{_uniq('test')}@example.com", password="testpassword")

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}


async def test_login_non_existent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": _uniq("nonexistent"), "password": "Sup3rSecret!"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}


class TestPasswordComplexity:
    """Server-side enforcement of registration password rules."""

    async def _register(self, client: AsyncClient, session: AsyncSession, password: str) -> int:
        username = _uniq("pw")
        email = f"{username}@example.com"
        await WhitelistService.add_entry(session, value=email, added_by_id=1)

        with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Pat",
                    "username": username,
                    "email": email,
                    "password": password,
                },
            )
        return response.status_code

    @pytest.mark.parametrize(
        "weak_password,reason",
        [
            ("Aa1!aa", "too short"),
            ("alllowercase1!", "no uppercase"),
            ("NoDigits!!", "no digit"),
            ("NoSpecial1A", "no special character"),
        ],
    )
    async def test_weak_passwords_rejected(
        self,
        client: AsyncClient,
        session: AsyncSession,
        weak_password: str,
        reason: str,
    ) -> None:
        status_code = await self._register(client, session, weak_password)
        assert status_code == 422, f"Expected 422 for {reason} ({weak_password!r})"

    async def test_strong_password_accepted(self, client: AsyncClient, session: AsyncSession) -> None:
        status_code = await self._register(client, session, "Sup3rSecret!")
        assert status_code == 200
