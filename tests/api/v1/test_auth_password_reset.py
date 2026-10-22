"""Tests for the self-service password reset: ``POST /auth/password-reset`` and
``POST /auth/password-reset/confirm``.

A request always answers 202 so it never reveals whether an account exists, and only
an account with a password gets a reset email. Confirming redeems the single-use
link, replaces the password and marks the email verified.

Every request for a known account lands an ``auth.password_reset_requested`` row,
and every confirmation an ``auth.password_reset`` row. A rejected link is recorded
in its own transaction so the evidence survives the 400, and a successful reset is
fail-closed: no audit row, no new password.
"""

import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.base import utc_now
from sparkth.core.models.password_reset import PasswordResetToken
from sparkth.core.models.user import User
from sparkth.core.security import get_password_hash, hash_token, verify_password
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.services.account import ResetEmail

REQUEST_URL = "/api/v1/auth/password-reset"
CONFIRM_URL = "/api/v1/auth/password-reset/confirm"
OLD = "Old-Passw0rd!"
NEW = "New-Passw0rd!"


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _user(session: AsyncSession, *, with_password: bool = True, email_verified: bool = True) -> User:
    username = _uniq("u")
    user = User(
        name="Rita",
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(OLD) if with_password else None,
        google_id=None if with_password else f"g-{username}",
        email_verified=email_verified,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def rate_limit_store(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Replace the rate-limit Redis with an in-memory shim, returning its store."""
    from sparkth.api.v1 import auth as auth_module

    store: dict[str, str] = {}

    class FakeRedis:
        async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
            if nx and key in store:
                return None
            store[key] = value
            return True

    @asynccontextmanager
    async def get_fake_redis() -> AsyncIterator[FakeRedis]:
        yield FakeRedis()

    monkeypatch.setattr(auth_module, "_get_rate_limit_redis", get_fake_redis)
    return store


@pytest.fixture
def mock_send() -> Iterator[AsyncMock]:
    with patch("sparkth.api.v1.auth.send_password_reset_email", new_callable=AsyncMock) as mock:
        yield mock


async def _request_token(client: AsyncClient, mock_send: AsyncMock, email: str) -> str:
    response = await client.post(REQUEST_URL, json={"email": email})
    assert response.status_code == 202, response.text
    assert mock_send.await_args is not None
    reset: ResetEmail = mock_send.await_args.args[0]
    return reset.raw_token


async def _stored_hash(session: AsyncSession, user: User) -> str | None:
    await session.refresh(user)
    return user.hashed_password


class TestRequest:
    async def test_sends_a_reset_email_to_an_account_with_a_password(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)

        response = await client.post(REQUEST_URL, json={"email": user.email})

        assert response.status_code == 202
        mock_send.assert_awaited_once()
        assert mock_send.await_args is not None
        reset: ResetEmail = mock_send.await_args.args[0]
        assert (reset.to, reset.name) == (user.email, "Rita")
        stored = (await session.exec(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))).one()
        assert stored.token_hash == hash_token(reset.raw_token)

    async def test_matches_the_email_case_insensitively(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)

        response = await client.post(REQUEST_URL, json={"email": user.email.upper()})

        assert response.status_code == 202
        mock_send.assert_awaited_once()

    async def test_unknown_email_answers_202_without_sending(self, client: AsyncClient, mock_send: AsyncMock) -> None:
        response = await client.post(REQUEST_URL, json={"email": "ghost@example.com"})

        assert response.status_code == 202
        mock_send.assert_not_awaited()

    async def test_account_without_password_answers_202_without_sending(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session, with_password=False)

        response = await client.post(REQUEST_URL, json={"email": user.email})

        assert response.status_code == 202
        mock_send.assert_not_awaited()

    async def test_a_second_request_within_the_cooldown_is_rate_limited(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)

        first = await client.post(REQUEST_URL, json={"email": user.email})
        second = await client.post(REQUEST_URL, json={"email": user.email})

        assert first.status_code == 202
        assert second.status_code == 429
        mock_send.assert_awaited_once()

    async def test_a_new_request_invalidates_the_previous_link(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, rate_limit_store: dict[str, str]
    ) -> None:
        user = await _user(session)
        first = await _request_token(client, mock_send, user.email)
        # Clearing the store lets the second request through the cooldown.
        rate_limit_store.clear()
        second = await _request_token(client, mock_send, user.email)

        stale = await client.post(CONFIRM_URL, json={"token": first, "new_password": NEW})
        fresh = await client.post(CONFIRM_URL, json={"token": second, "new_password": NEW})

        assert stale.status_code == 400
        assert fresh.status_code == 204

    async def test_rejects_a_malformed_email(self, client: AsyncClient, mock_send: AsyncMock) -> None:
        response = await client.post(REQUEST_URL, json={"email": "not-an-email"})

        assert response.status_code == 422
        mock_send.assert_not_awaited()


class TestConfirm:
    async def test_replaces_the_password(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)
        token = await _request_token(client, mock_send, user.email)

        response = await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        assert response.status_code == 204
        stored = await _stored_hash(session, user)
        assert stored is not None
        assert verify_password(NEW, stored)

    async def test_the_new_password_signs_in(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)
        token = await _request_token(client, mock_send, user.email)
        await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        old_login = await client.post("/api/v1/auth/login", json={"username": user.username, "password": OLD})
        new_login = await client.post("/api/v1/auth/login", json={"username": user.username, "password": NEW})

        assert old_login.status_code == 401
        assert new_login.status_code == 200

    async def test_marks_an_unverified_email_verified(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session, email_verified=False)
        token = await _request_token(client, mock_send, user.email)

        await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        await session.refresh(user)
        assert user.email_verified is True
        assert user.email_verified_at is not None

    async def test_a_link_works_only_once(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)
        token = await _request_token(client, mock_send, user.email)
        await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        again = await client.post(CONFIRM_URL, json={"token": token, "new_password": "An0ther-Pass!"})

        assert again.status_code == 400
        stored = await _stored_hash(session, user)
        assert stored is not None
        assert verify_password(NEW, stored)

    async def test_rejects_an_unknown_link(self, client: AsyncClient) -> None:
        response = await client.post(CONFIRM_URL, json={"token": "nope", "new_password": NEW})

        assert response.status_code == 400
        assert response.json()["detail"]

    async def test_rejects_an_expired_link(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)
        token = await _request_token(client, mock_send, user.email)
        stored = (await session.exec(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))).one()
        stored.expires_at = utc_now() - timedelta(minutes=1)
        session.add(stored)
        await session.commit()

        response = await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        assert response.status_code == 400
        assert await _stored_hash(session, user) == user.hashed_password
        assert verify_password(OLD, user.hashed_password or "")

    async def test_rejects_a_weak_password_and_keeps_the_link_usable(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock
    ) -> None:
        user = await _user(session)
        token = await _request_token(client, mock_send, user.email)

        weak = await client.post(CONFIRM_URL, json={"token": token, "new_password": "short"})
        strong = await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        assert weak.status_code == 422
        assert strong.status_code == 204


class TestAudit:
    async def test_request_records_a_success_against_the_account(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, audit_events: AuditEventsFetcher
    ) -> None:
        user = await _user(session)

        await client.post(REQUEST_URL, json={"email": user.email})

        (event,) = await audit_events()
        assert (event.category, event.action) == ("auth", "password_reset_requested")
        assert event.outcome == "success"
        assert event.actor_type == "anonymous"
        assert (event.target_type, event.target_id) == ("user", str(user.id))
        assert event.error_detail is None

    async def test_request_for_an_account_without_password_records_a_denial(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, audit_events: AuditEventsFetcher
    ) -> None:
        user = await _user(session, with_password=False)

        await client.post(REQUEST_URL, json={"email": user.email})

        (event,) = await audit_events()
        assert (event.category, event.action) == ("auth", "password_reset_requested")
        assert event.outcome == "denied"
        assert event.actor_type == "anonymous"
        assert (event.target_type, event.target_id) == ("user", str(user.id))
        assert event.error_detail == "account has no password"

    async def test_request_for_an_unknown_email_records_nothing(
        self, client: AsyncClient, mock_send: AsyncMock, audit_events: AuditEventsFetcher
    ) -> None:
        await client.post(REQUEST_URL, json={"email": "ghost@example.com"})

        assert await audit_events() == []

    async def test_a_rate_limited_request_records_nothing(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, audit_events: AuditEventsFetcher
    ) -> None:
        user = await _user(session)

        await client.post(REQUEST_URL, json={"email": user.email})
        await client.post(REQUEST_URL, json={"email": user.email})

        assert len(await audit_events()) == 1

    async def test_confirm_records_a_password_reset_by_the_user(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, audit_events: AuditEventsFetcher
    ) -> None:
        user = await _user(session)
        token = await _request_token(client, mock_send, user.email)

        await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        _, event = await audit_events()
        assert (event.category, event.action) == ("auth", "password_reset")
        assert event.outcome == "success"
        assert (event.actor_type, event.actor_id) == ("user", str(user.id))
        assert (event.target_type, event.target_id) == ("user", str(user.id))
        assert event.new_values == {"method": "email"}

    async def test_an_unknown_link_records_a_failure_that_survives_the_error(
        self, client: AsyncClient, audit_events: AuditEventsFetcher
    ) -> None:
        await client.post(CONFIRM_URL, json={"token": "nope", "new_password": NEW})

        (event,) = await audit_events()
        assert (event.category, event.action) == ("auth", "password_reset")
        assert event.outcome == "failure"
        assert event.actor_type == "anonymous"
        assert event.target_type is None
        assert event.error_detail == "token is invalid or already used"

    async def test_an_expired_link_records_a_failure(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, audit_events: AuditEventsFetcher
    ) -> None:
        user = await _user(session)
        token = await _request_token(client, mock_send, user.email)
        stored = (await session.exec(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))).one()
        stored.expires_at = utc_now() - timedelta(minutes=1)
        session.add(stored)
        await session.commit()

        await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        _, event = await audit_events()
        assert event.outcome == "failure"
        assert event.error_detail == "token has expired"

    async def test_audit_rows_never_carry_the_token_password_or_hash(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, audit_events: AuditEventsFetcher
    ) -> None:
        user = await _user(session)
        old_hash = user.hashed_password
        assert old_hash is not None
        token = await _request_token(client, mock_send, user.email)
        await client.post(CONFIRM_URL, json={"token": "bogus-token", "new_password": NEW})
        await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})
        new_hash = await _stored_hash(session, user)
        assert new_hash is not None

        events = await audit_events()
        assert len(events) == 3
        for event in events:
            for secret in [token, "bogus-token", hash_token(token), OLD, NEW, old_hash, new_hash, user.email]:
                assert secret.encode() not in event.canonical_bytes

    async def test_confirm_is_fail_closed_when_audit_write_fails(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = await _user(session)
        before = user.hashed_password
        token = await _request_token(client, mock_send, user.email)

        async def broken_record(*args: object, **kwargs: object) -> None:
            raise SQLAlchemyError("audit unavailable")

        monkeypatch.setattr("sparkth.services.account.password_reset.record_event", broken_record)

        with pytest.raises(SQLAlchemyError):
            await client.post(CONFIRM_URL, json={"token": token, "new_password": NEW})

        assert await _stored_hash(session, user) == before

    async def test_request_is_fail_closed_when_audit_write_fails(
        self, client: AsyncClient, session: AsyncSession, mock_send: AsyncMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user = await _user(session)

        async def broken_record(*args: object, **kwargs: object) -> None:
            raise SQLAlchemyError("audit unavailable")

        monkeypatch.setattr("sparkth.services.account.password_reset.record_event", broken_record)

        with pytest.raises(SQLAlchemyError):
            await client.post(REQUEST_URL, json={"email": user.email})

        mock_send.assert_not_awaited()
        tokens = (await session.exec(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))).all()
        assert tokens == []
