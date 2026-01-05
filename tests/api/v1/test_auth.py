from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_password_hash
from app.models.user import User


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def create_user_in_db(
    session: AsyncSession,
    *,
    name: str = "Test User",
    username: str | None = None,
    email: str | None = None,
    password: str = "testpassword",
) -> User:
    username = username or _uniq("testuser")
    email = email or f"{_uniq('test')}@example.com"

    user = User(
        name=name,
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_create_user(client: AsyncClient) -> None:
    username = _uniq("testuser")
    email = f"{_uniq('test')}@example.com"

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Test User",
            "username": username,
            "email": email,
            "password": "testpassword",
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

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Another User",
            "username": username,
            "email": f"{_uniq('another')}@example.com",
            "password": "testpassword",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Username already registered"}


async def test_create_user_existing_email(client: AsyncClient, session: AsyncSession) -> None:
    email = f"{_uniq('test')}@example.com"
    await create_user_in_db(session, username=_uniq("testuser"), email=email)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "name": "Another User",
            "username": _uniq("anotheruser"),
            "email": email,
            "password": "testpassword",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Email already registered"}


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
        json={"username": _uniq("nonexistent"), "password": "testpassword"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect username or password"}
