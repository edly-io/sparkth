from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.analytics.models import raw_events
from app.core.security import get_password_hash
from app.models.user import User

LOGIN_URL = "/api/v1/auth/login"


async def _make_verified_user(session: AsyncSession, username: str, password: str) -> User:
    user = User(
        name="Login Producer",
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(password),
        email_verified=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_successful_login_emits_user_logged_in_event(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    user = await _make_verified_user(session, "loginproducer", "testpassword")

    response = await client.post(LOGIN_URL, json={"username": "loginproducer", "password": "testpassword"})
    assert response.status_code == 200

    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    assert len(rows) == 1
    assert rows[0]["event_type"] == "user.logged_in"
    assert rows[0]["event_version"] == 1
    assert rows[0]["actor_id"] == str(user.id)
    assert rows[0]["payload"] == {"username": "loginproducer"}


async def test_login_succeeds_even_if_analytics_emit_fails(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    await _make_verified_user(session, "resilientlogin", "testpassword")

    # Analytics is fire-and-forget: a gateway failure must never break login.
    with patch("app.api.v1.auth.ingest_event", side_effect=SQLAlchemyError("boom")):
        response = await client.post(LOGIN_URL, json={"username": "resilientlogin", "password": "testpassword"})

    assert response.status_code == 200
    assert "access_token" in response.json()
