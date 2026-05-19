import uuid
from unittest.mock import patch

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.whitelist import WhitelistService


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def test_register_allowed_email(client: AsyncClient, session: AsyncSession) -> None:
    email = f"{_uniq('user')}@example.com"
    await WhitelistService.add_entry(session, value=email, added_by_id=1)

    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Test User",
                "username": _uniq("testuser"),
                "email": email,
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 200


async def test_register_allowed_by_domain(client: AsyncClient, session: AsyncSession) -> None:
    # Use hex-only suffix so the domain and local part are valid email characters
    suffix = uuid.uuid4().hex[:8]
    domain_suffix = f"org{suffix}.com"
    await WhitelistService.add_entry(session, value=f"@{domain_suffix}", added_by_id=1)

    local = uuid.uuid4().hex[:8]
    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Test User",
                "username": _uniq("testuser"),
                "email": f"{local}@{domain_suffix}",
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 200


async def test_register_blocked_email(client: AsyncClient) -> None:
    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Blocked User",
                "username": _uniq("blocked"),
                "email": f"{_uniq('blocked')}@nowhere.com",
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


async def test_register_blocked_when_whitelist_empty(client: AsyncClient) -> None:
    with patch("app.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "New User",
                "username": _uniq("newuser"),
                "email": f"{_uniq('new')}@example.com",
                "password": "Sup3rSecret!",
            },
        )
    assert response.status_code == 403
