from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.core.config import get_settings
from sparkth.core.models.user import User
from sparkth.core.models.whitelist import WhitelistedEmail
from sparkth.core.security import get_password_hash

LOGIN_URL = "/api/v1/auth/login"
GOOGLE_CALLBACK_URL = "/api/v1/auth/google/callback?code=x"


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
    assert rows[0]["payload"] == {"method": "password"}


async def test_analytics_write_failure_propagates_from_the_login_background_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A failed analytics write is not hidden — it reaches the caller.

    _emit_login_event runs as a Starlette BackgroundTask. In production those run
    after the response is flushed, so this surfaces as a logged unhandled task
    error and the user still gets their token. Under the httpx ASGI test transport
    the background task runs inside the request, so the exception is re-raised here
    — which is exactly what lets us assert it was not swallowed.
    """
    await _make_verified_user(session, "resilientlogin", "testpassword")

    with (
        patch("sparkth.lib.analytics.ingest_event", side_effect=SQLAlchemyError("boom")),
        pytest.raises(SQLAlchemyError, match="boom"),
    ):
        await client.post(LOGIN_URL, json={"username": "resilientlogin", "password": "testpassword"})


async def test_unexpected_analytics_error_propagates_from_the_login_background_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    """An error type outside the analytics-specific trio propagates just the same.

    emit_event catches nothing at all — not just UnknownEventTypeError,
    ValidationError, and SQLAlchemyError — so a RuntimeError from the gateway
    reaches the caller exactly like any other failure. As in the case above, this
    only surfaces inside the request because of the httpx ASGI test transport; in
    production the background task raises after the response has already been sent.
    """
    await _make_verified_user(session, "unexpectederrorlogin", "testpassword")

    with (
        patch("sparkth.lib.analytics.ingest_event", side_effect=RuntimeError("unexpected internal error")),
        pytest.raises(RuntimeError),
    ):
        await client.post(LOGIN_URL, json={"username": "unexpectederrorlogin", "password": "testpassword"})


async def test_analytics_session_acquisition_failure_propagates_from_the_login_background_task(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A dead analytics database is not hidden either — it reaches the caller too.

    emit_event opens its own analytics session and catches nothing, so a failure to
    acquire that session (e.g. the analytics database is unprovisioned or
    unreachable) propagates exactly like a write failure. As above, this only
    surfaces inside the request because of the httpx ASGI test transport; in
    production the background task raises after the response has already been sent.
    """
    await _make_verified_user(session, "analyticsdownlogin", "testpassword")

    @asynccontextmanager
    async def _failing_scope(*args: Any, **kwargs: Any) -> Any:
        raise SQLAlchemyError("analytics database unreachable")
        yield  # pragma: no cover -- unreachable, makes this a generator

    with (
        patch("sparkth.lib.analytics.analytics_session_scope", _failing_scope),
        pytest.raises(SQLAlchemyError, match="analytics database unreachable"),
    ):
        await client.post(LOGIN_URL, json={"username": "analyticsdownlogin", "password": "testpassword"})


def _google_patches(google_id: str, email: str) -> tuple[Any, Any]:
    return (
        patch("sparkth.api.v1.auth.exchange_auth_code", new_callable=AsyncMock, return_value={"access_token": "t"}),
        patch(
            "sparkth.api.v1.auth.get_google_user_info",
            new_callable=AsyncMock,
            return_value={"id": google_id, "email": email, "name": "Google User"},
        ),
    )


async def test_google_login_emits_user_logged_in_event(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    user = await _make_verified_user(session, "googleproducer", "testpassword")
    exchange, user_info = _google_patches("gid-producer", user.email)

    with exchange, user_info:
        response = await client.get(GOOGLE_CALLBACK_URL)
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login/callback")

    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    assert len(rows) == 1
    assert rows[0]["event_type"] == "user.logged_in"
    assert rows[0]["event_version"] == 1
    assert rows[0]["actor_id"] == str(user.id)
    assert rows[0]["payload"] == {"method": "google"}


async def test_google_signup_counts_as_a_login(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first Google sign-in creates the account and logs the user in, so it is a login too."""
    monkeypatch.setattr(get_settings(), "REGISTRATION_ENABLED", True)
    session.add(WhitelistedEmail(value="newgoogle@example.com", entry_type="email", added_by_id=None))
    await session.commit()
    exchange, user_info = _google_patches("gid-new", "newgoogle@example.com")

    with exchange, user_info:
        response = await client.get(GOOGLE_CALLBACK_URL)
    assert response.status_code == 302

    result = await analytics_session.execute(select(raw_events).where(raw_events.c.event_type == "user.logged_in"))
    assert [row["payload"] for row in result.mappings().all()] == [{"method": "google"}]


async def test_refused_google_login_emits_nothing(
    client: AsyncClient, session: AsyncSession, analytics_session: AsyncSession
) -> None:
    """A callback that sends the user back to the login page did not log anyone in."""
    with patch("sparkth.api.v1.auth.exchange_auth_code", new_callable=AsyncMock, side_effect=ValueError("denied")):
        response = await client.get(GOOGLE_CALLBACK_URL)
    assert response.headers["location"].startswith("/login?error=")

    assert (await analytics_session.execute(select(raw_events))).mappings().all() == []
