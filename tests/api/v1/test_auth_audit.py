"""Login is the first audit capture seam: every attempt (success, bad
credentials, unverified email) must land an auth.login row, and the write is
fail-closed: no audit record, no token."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from pytest import MonkeyPatch, raises
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.models import AuditEvent
from sparkth.core.models.user import User
from sparkth.core.security import get_password_hash

PASSWORD = "Sup3rSecret!"


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_user(session: AsyncSession, *, email_verified: bool = True) -> User:
    user = User(
        name="Test User",
        username=_uniq("audituser"),
        email=f"{_uniq('audit')}@example.com",
        hashed_password=get_password_hash(PASSWORD),
        email_verified=email_verified,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _login_events(session: AsyncSession) -> list[AuditEvent]:
    return list((await session.exec(select(AuditEvent).where(AuditEvent.action == "login"))).all())


async def test_successful_login_records_success_event(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session)

    response = await client.post("/api/v1/auth/login", json={"username": user.username, "password": PASSWORD})
    assert response.status_code == 200

    (event,) = await _login_events(session)
    assert event.category == "auth"
    assert event.outcome == "success"
    assert event.actor_type == "user"
    assert event.actor_id == str(user.id)
    assert event.actor_label == user.username
    assert event.source == "rest"
    assert event.request_id is not None
    assert event.user_agent is not None


async def test_wrong_password_records_failure_event(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session)

    response = await client.post("/api/v1/auth/login", json={"username": user.username, "password": "wrong"})
    assert response.status_code == 401

    (event,) = await _login_events(session)
    assert event.outcome == "failure"
    assert event.actor_type == "anonymous"
    assert event.actor_id is None
    assert event.actor_label is None
    # The claimed identity is evidence about the event's target, not the actor.
    assert event.target_type == "username"
    assert event.target_id == user.username
    assert event.error_detail is not None


async def test_unknown_username_records_failure_event(client: AsyncClient, session: AsyncSession) -> None:
    username = _uniq("ghost")
    response = await client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 401

    (event,) = await _login_events(session)
    assert event.outcome == "failure"
    assert event.target_type == "username"
    assert event.target_id == username


async def test_unverified_email_records_denied_event(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, email_verified=False)

    response = await client.post("/api/v1/auth/login", json={"username": user.username, "password": PASSWORD})
    assert response.status_code == 403

    (event,) = await _login_events(session)
    assert event.outcome == "denied"
    assert event.target_type == "username"
    assert event.target_id == user.username


async def test_login_is_fail_closed_when_audit_write_fails(
    client: AsyncClient, session: AsyncSession, monkeypatch: MonkeyPatch
) -> None:
    user = await _create_user(session)

    async def broken_record(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("audit unavailable")

    monkeypatch.setattr("sparkth.api.v1.auth.record_event_now", broken_record)

    with raises(SQLAlchemyError):
        await client.post("/api/v1/auth/login", json={"username": user.username, "password": PASSWORD})


async def _events(session: AsyncSession, action: str) -> list[AuditEvent]:
    return list((await session.exec(select(AuditEvent).where(AuditEvent.action == action))).all())


async def test_registration_records_registered_event(client: AsyncClient, session: AsyncSession) -> None:
    from sparkth.core.models.whitelist import WhitelistedEmail

    username = _uniq("newbie")
    email = f"{username}@example.com"
    session.add(WhitelistedEmail(value=email, entry_type="email", added_by_id=None))
    await session.commit()

    with MonkeyPatch.context() as mp:
        from sparkth.api.v1 import auth as api_auth

        mp.setattr(api_auth.settings, "REGISTRATION_ENABLED", True)
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "New", "username": username, "email": email, "password": PASSWORD},
        )
    assert response.status_code == 200
    user_id = response.json()["id"]

    (event,) = await _events(session, "registered")
    assert event.category == "auth"
    assert event.outcome == "success"
    assert event.actor_type == "user"
    assert event.actor_id == str(user_id)
    assert event.target_type == "user"
    assert event.target_id == str(user_id)
    assert event.new_values == {"method": "password"}


async def test_email_verification_records_success_event(client: AsyncClient, session: AsyncSession) -> None:
    from sparkth.services.email_verification import EmailVerificationService

    user = await _create_user(session, email_verified=False)
    assert user.id is not None
    raw_token = await EmailVerificationService.create_token(session, user_id=user.id)
    await session.commit()

    response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 204

    (event,) = await _events(session, "email_verified")
    assert event.category == "auth"
    assert event.outcome == "success"
    assert event.actor_type == "user"
    assert event.actor_id == str(user.id)
    assert event.target_type == "user"
    assert event.target_id == str(user.id)


async def test_bad_verification_token_records_failure_event(client: AsyncClient, session: AsyncSession) -> None:
    response = await client.post("/api/v1/auth/verify-email", json={"token": "nope"})
    assert response.status_code == 400

    (event,) = await _events(session, "email_verified")
    assert event.outcome == "failure"
    assert event.actor_type == "anonymous"
    assert event.error_detail is not None
    # The raw token is a credential: it must never land in the record.
    assert "nope" not in event.canonical_bytes.decode()


def _google_patches(email: str, google_id: str) -> tuple[Any, Any]:
    return (
        patch("sparkth.api.v1.auth.exchange_auth_code", new_callable=AsyncMock, return_value={"access_token": "x"}),
        patch(
            "sparkth.api.v1.auth.get_google_user_info",
            new_callable=AsyncMock,
            return_value={"id": google_id, "email": email, "name": "Google User"},
        ),
    )


async def test_google_signup_records_registration_and_login(client: AsyncClient, session: AsyncSession) -> None:
    from sparkth.core.models.whitelist import WhitelistedEmail

    email = f"{_uniq('g')}@example.com"
    session.add(WhitelistedEmail(value=email, entry_type="email", added_by_id=None))
    await session.commit()

    exchange, userinfo = _google_patches(email, _uniq("gid"))
    with exchange, userinfo:
        response = await client.get("/api/v1/auth/google/callback?code=x")
    assert response.status_code == 302

    user = (await session.exec(select(User).where(User.email == email))).one()
    (registered,) = await _events(session, "registered")
    assert registered.actor_id == str(user.id)
    assert registered.target_id == str(user.id)
    assert registered.new_values == {"method": "google"}

    (login,) = await _login_events(session)
    assert login.outcome == "success"
    assert login.actor_id == str(user.id)
    assert login.new_values is None


async def test_google_link_records_linked_and_login(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session)

    exchange, userinfo = _google_patches(user.email, _uniq("gid"))
    with exchange, userinfo:
        response = await client.get("/api/v1/auth/google/callback?code=x")
    assert response.status_code == 302

    (linked,) = await _events(session, "google_linked")
    assert linked.category == "auth"
    assert linked.outcome == "success"
    assert linked.actor_id == str(user.id)
    assert linked.target_type == "user"
    assert linked.target_id == str(user.id)
    assert await _events(session, "registered") == []

    (login,) = await _login_events(session)
    assert login.actor_id == str(user.id)
