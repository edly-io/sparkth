import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.email_verification import EmailVerificationToken
from app.models.user import User
from app.services.email_verification import (
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

    async def test_returns_raw_token_for_unverified(self, session: AsyncSession) -> None:
        user = await _create_user(session, verified=False)
        raw = await EmailVerificationService.request_resend(session, email=user.email)
        assert raw is not None and len(raw) >= 30
