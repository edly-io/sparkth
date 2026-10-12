import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select as sa_select
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.core.config import get_settings
from sparkth.core.models.user import User
from sparkth.core.models.whitelist import WhitelistedEmail
from sparkth.services.email_verification import EmailVerificationService

REGISTER_URL = "/api/v1/auth/register"
VERIFY_URL = "/api/v1/auth/verify-email"
GOOGLE_CALLBACK_URL = "/api/v1/auth/google/callback?code=x"


@pytest.fixture(autouse=True)
def enable_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "REGISTRATION_ENABLED", True)


async def _whitelist(session: AsyncSession, email: str) -> None:
    session.add(WhitelistedEmail(value=email, entry_type="email", added_by_id=None))
    await session.commit()


async def _rows(analytics_session: AsyncSession, event_type: str) -> list[Any]:
    result = await analytics_session.execute(sa_select(raw_events).where(raw_events.c.event_type == event_type))
    return list(result.mappings().all())


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _google_patches(google_id: str, email: str) -> tuple[Any, Any]:
    return (
        patch("sparkth.api.v1.auth.exchange_auth_code", new_callable=AsyncMock, return_value={"access_token": "t"}),
        patch(
            "sparkth.api.v1.auth.get_google_user_info",
            new_callable=AsyncMock,
            return_value={"id": google_id, "email": email, "name": "Google User"},
        ),
    )


async def test_password_registration_emits_user_registered(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    await _whitelist(session, email)

    with patch("sparkth.api.v1.auth.send_verification_email", new_callable=AsyncMock):
        response = await client.post(
            REGISTER_URL,
            json={"name": "Reg", "username": f"reg{uuid.uuid4().hex[:8]}", "email": email, "password": "Sup3rSecret!"},
        )
    assert response.status_code == 200, response.text

    user = (await session.exec(select(User).where(User.email == email))).one()
    rows = await _rows(analytics_session, "user.registered")
    assert len(rows) == 1
    assert rows[0]["event_version"] == 1
    assert rows[0]["actor_id"] == str(user.id)
    assert rows[0]["payload"] == {"method": "password"}
    assert _utc(rows[0]["occurred_at"]) == _utc(user.created_at)


async def test_failed_registration_emits_nothing(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    response = await client.post(
        REGISTER_URL,
        json={"name": "No", "username": "nowhitelist", "email": "nope@example.com", "password": "Sup3rSecret!"},
    )
    assert response.status_code == 403
    assert await _rows(analytics_session, "user.registered") == []


async def _unverified_user(session: AsyncSession) -> tuple[User, str]:
    username = f"v{uuid.uuid4().hex[:8]}"
    user = User(name="Ver", username=username, email=f"{username}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    assert user.id is not None
    raw = await EmailVerificationService.create_token(session, user_id=user.id)
    await session.commit()
    return user, raw


async def test_email_verification_emits_user_email_verified(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    user, raw = await _unverified_user(session)

    response = await client.post(VERIFY_URL, json={"token": raw})
    assert response.status_code == 204

    await session.refresh(user)
    assert user.email_verified_at is not None
    rows = await _rows(analytics_session, "user.email_verified")
    assert len(rows) == 1
    assert rows[0]["event_version"] == 1
    assert rows[0]["actor_id"] == str(user.id)
    assert rows[0]["payload"] == {}
    assert _utc(rows[0]["occurred_at"]) == _utc(user.email_verified_at)


async def test_rejected_verification_emits_nothing(client: AsyncClient, analytics_session: AsyncSession) -> None:
    response = await client.post(VERIFY_URL, json={"token": "bogus"})
    assert response.status_code == 400
    assert await _rows(analytics_session, "user.email_verified") == []


async def test_google_first_sign_in_emits_user_registered(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    await _whitelist(session, "firstgoogle@example.com")
    exchange, user_info = _google_patches("gid-first", "firstgoogle@example.com")

    with exchange, user_info:
        response = await client.get(GOOGLE_CALLBACK_URL)
    assert response.status_code == 302

    user = (await session.exec(select(User).where(User.email == "firstgoogle@example.com"))).one()
    rows = await _rows(analytics_session, "user.registered")
    assert len(rows) == 1
    assert rows[0]["actor_id"] == str(user.id)
    assert rows[0]["payload"] == {"method": "google"}
    assert _utc(rows[0]["occurred_at"]) == _utc(user.created_at)
    assert len(await _rows(analytics_session, "user.logged_in")) == 1


async def test_google_sign_in_of_existing_user_emits_no_user_registered(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    user = User(name="Old", username="oldgoogle", email="oldgoogle@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    exchange, user_info = _google_patches("gid-old", "oldgoogle@example.com")

    with exchange, user_info:
        response = await client.get(GOOGLE_CALLBACK_URL)
    assert response.status_code == 302

    assert await _rows(analytics_session, "user.registered") == []
    assert len(await _rows(analytics_session, "user.logged_in")) == 1
