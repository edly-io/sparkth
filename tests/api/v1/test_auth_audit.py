"""Login is the first audit capture seam: every attempt (success, bad
credentials, unverified email) must land an auth.login row, and the write is
fail-closed: no audit record, no token."""

import uuid

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
