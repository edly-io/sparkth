import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import aiosmtplib
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.email_verification import EmailVerificationToken
from sparkth.core.models.user import User
from sparkth.services import email_verification as svc
from sparkth.services.email_verification import (
    EmailVerificationService,
    TokenExpiredError,
    TokenInvalidError,
)


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_user(session: AsyncSession, *, verified: bool = False) -> User:
    suffix = _uniq("u")
    user = User(
        name="Alice",
        username=suffix,
        email=f"{suffix}@example.com",
        hashed_password="x",
        email_verified=verified,
    )
    session.add(user)
    await session.flush()
    return user


class TestCreateToken:
    async def test_returns_raw_token_and_stores_hash(self, session: AsyncSession) -> None:
        user = await _create_user(session)
        assert user.id is not None

        raw = await EmailVerificationService.create_token(session, user_id=user.id)

        assert isinstance(raw, str) and len(raw) >= 30
        result = await session.exec(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
        rows = list(result.all())
        assert len(rows) == 1
        assert rows[0].token_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert rows[0].used_at is None
        # SQLite drops tzinfo on round-trip; coerce to UTC for the comparison
        expires_at = rows[0].expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        assert expires_at > datetime.now(timezone.utc)

    async def test_invalidates_prior_unused_tokens(self, session: AsyncSession) -> None:
        user = await _create_user(session)
        assert user.id is not None

        await EmailVerificationService.create_token(session, user_id=user.id)
        await EmailVerificationService.create_token(session, user_id=user.id)

        result = await session.exec(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
        rows = list(result.all())
        assert len(rows) == 2
        unused = [r for r in rows if r.used_at is None]
        assert len(unused) == 1, "Only the latest token should remain unused"


class TestVerifyToken:
    async def test_marks_user_verified_and_token_used(self, session: AsyncSession) -> None:
        user = await _create_user(session)
        assert user.id is not None
        raw = await EmailVerificationService.create_token(session, user_id=user.id)

        verified_user = await EmailVerificationService.verify_token(session, raw_token=raw)

        assert verified_user.id == user.id
        assert verified_user.email_verified is True
        assert verified_user.email_verified_at is not None

        result = await session.exec(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
        rows = list(result.all())
        assert rows[0].used_at is not None

    async def test_unknown_token_raises_invalid(self, session: AsyncSession) -> None:
        with pytest.raises(TokenInvalidError):
            await EmailVerificationService.verify_token(session, raw_token="nope")

    async def test_used_token_raises_invalid(self, session: AsyncSession) -> None:
        user = await _create_user(session)
        assert user.id is not None
        raw = await EmailVerificationService.create_token(session, user_id=user.id)
        await EmailVerificationService.verify_token(session, raw_token=raw)

        with pytest.raises(TokenInvalidError):
            await EmailVerificationService.verify_token(session, raw_token=raw)

    async def test_expired_token_raises_expired(self, session: AsyncSession) -> None:
        user = await _create_user(session)
        assert user.id is not None
        raw = await EmailVerificationService.create_token(session, user_id=user.id)

        result = await session.exec(select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
        token = result.one()
        token.expires_at = datetime.now(timezone.utc).replace(year=2000)
        session.add(token)
        await session.flush()

        with pytest.raises(TokenExpiredError):
            await EmailVerificationService.verify_token(session, raw_token=raw)


class TestRequestResend:
    async def test_returns_none_for_unknown_email(self, session: AsyncSession) -> None:
        result = await EmailVerificationService.request_resend(session, email="ghost@example.com")
        assert result is None

    async def test_returns_none_for_already_verified(self, session: AsyncSession) -> None:
        user = await _create_user(session, verified=True)
        result = await EmailVerificationService.request_resend(session, email=user.email)
        assert result is None

    async def test_returns_raw_token_and_name_for_unverified(self, session: AsyncSession) -> None:
        user = await _create_user(session, verified=False)
        result = await EmailVerificationService.request_resend(session, email=user.email)
        assert result is not None
        raw, name = result
        assert len(raw) >= 30
        assert name == user.name


class TestSendVerificationEmail:
    async def test_calls_send_email_with_link_and_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(svc.settings, "FRONTEND_BASE_URL", "https://app.test")
        monkeypatch.setattr(svc.settings, "EMAIL_VERIFICATION_TOKEN_TTL_HOURS", 24)
        mock = AsyncMock()
        monkeypatch.setattr(svc, "send_email", mock)

        await svc.send_verification_email(
            to="alice@example.com",
            name="Alice",
            raw_token="abc123",
        )

        mock.assert_awaited_once()
        assert mock.await_args is not None
        kwargs = mock.await_args.kwargs
        assert kwargs["to"] == "alice@example.com"
        assert "Alice" in kwargs["text_body"]
        assert "https://app.test/verify-email/?token=abc123" in kwargs["text_body"]
        assert "https://app.test/verify-email/?token=abc123" in kwargs["html_body"]
        assert "24" in kwargs["text_body"]

    async def test_strips_trailing_slash_in_frontend_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(svc.settings, "FRONTEND_BASE_URL", "https://app.test/")
        mock = AsyncMock()
        monkeypatch.setattr(svc, "send_email", mock)

        await svc.send_verification_email(to="a@b.com", name="A", raw_token="t")

        assert mock.await_args is not None
        text_body = mock.await_args.kwargs["text_body"]
        assert "https://app.test/verify-email/?token=t" in text_body
        assert "https://app.test//verify-email" not in text_body

    async def test_escapes_name_in_html_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User-controlled name must not be able to inject HTML into the email."""
        monkeypatch.setattr(svc.settings, "FRONTEND_BASE_URL", "https://app.test")
        mock = AsyncMock()
        monkeypatch.setattr(svc, "send_email", mock)

        await svc.send_verification_email(
            to="evil@example.com",
            name='<script>alert("xss")</script><a href="http://evil">click</a>',
            raw_token="t",
        )

        assert mock.await_args is not None
        html_body = mock.await_args.kwargs["html_body"]
        # No raw script tag, no raw injected anchor
        assert "<script>" not in html_body
        assert '<a href="http://evil">' not in html_body
        # The escaped form should be present
        assert "&lt;script&gt;" in html_body

    async def test_swallows_and_logs_runtime_error_when_smtp_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Background task must not propagate RuntimeError from send_email."""
        send_mock = AsyncMock(side_effect=RuntimeError("SMTP not configured: set SMTP_HOST"))
        monkeypatch.setattr(svc, "send_email", send_mock)
        log_mock = MagicMock()
        monkeypatch.setattr(svc, "logger", log_mock)

        # Must not raise.
        await svc.send_verification_email(to="x@example.com", name="X", raw_token="t")

        log_mock.exception.assert_called_once()
        args = log_mock.exception.call_args.args
        assert "x@example.com" in args

    async def test_swallows_and_logs_smtp_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Background task must not propagate aiosmtplib.SMTPException either."""
        send_mock = AsyncMock(side_effect=aiosmtplib.SMTPException("connection refused"))
        monkeypatch.setattr(svc, "send_email", send_mock)
        log_mock = MagicMock()
        monkeypatch.setattr(svc, "logger", log_mock)

        # Must not raise.
        await svc.send_verification_email(to="y@example.com", name="Y", raw_token="t")

        log_mock.exception.assert_called_once()
        args = log_mock.exception.call_args.args
        assert "y@example.com" in args
