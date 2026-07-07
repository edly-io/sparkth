from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.core.security import get_password_hash
from sparkth.models.user import User

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
    with patch("sparkth.api.v1.auth.ingest_event", side_effect=SQLAlchemyError("boom")):
        response = await client.post(LOGIN_URL, json={"username": "resilientlogin", "password": "testpassword"})

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_unexpected_analytics_error_does_not_break_login(client: AsyncClient, session: AsyncSession) -> None:
    """RuntimeError is not in the caught exception tuple, so it escapes the try block.

    Currently this causes login to return 500 because the exception propagates
    through the synchronous inline emission and surfaces to FastAPI's error handler.
    After moving to BackgroundTasks the exception is isolated to the background task
    and can never affect the already-sent 200 response.
    """
    await _make_verified_user(session, "unexpectederrorlogin", "testpassword")

    with patch("sparkth.api.v1.auth.ingest_event", side_effect=RuntimeError("unexpected internal error")):
        response = await client.post(LOGIN_URL, json={"username": "unexpectederrorlogin", "password": "testpassword"})

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_succeeds_when_analytics_session_unavailable(client: AsyncClient, session: AsyncSession) -> None:
    await _make_verified_user(session, "analyticsdownlogin", "testpassword")

    # The analytics DB may be unprovisioned or unreachable (e.g. the e2e env never
    # creates the separate analytics database). Acquiring the session must not break
    # login: emission acquires the session *inside* the swallowing try, so a connect
    # failure during acquisition or teardown can never surface as a 500.
    @asynccontextmanager
    async def _failing_scope(*args: Any, **kwargs: Any) -> Any:
        raise SQLAlchemyError("analytics database unreachable")
        yield  # pragma: no cover -- unreachable, makes this a generator

    with patch("sparkth.api.v1.auth.analytics_session_scope", _failing_scope):
        response = await client.post(LOGIN_URL, json={"username": "analyticsdownlogin", "password": "testpassword"})

    assert response.status_code == 200
    assert "access_token" in response.json()
