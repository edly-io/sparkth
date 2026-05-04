import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.models.email_verification import EmailVerificationToken
from app.models.user import User

settings = get_settings()


class TokenInvalidError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _as_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware in UTC.

    SQLite stores DateTime(timezone=True) columns as naive strings, so values
    loaded back may have lost their tzinfo. Treat naive values as UTC.
    """
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class EmailVerificationService:
    @staticmethod
    async def create_token(session: AsyncSession, *, user_id: int) -> str:
        """Generate a new verification token, invalidating any prior unused tokens.

        Returns the raw token (the only place it ever exists in plaintext).
        """
        now = datetime.now(timezone.utc)

        result = await session.exec(
            select(EmailVerificationToken).where(
                (EmailVerificationToken.user_id == user_id) & (EmailVerificationToken.used_at.is_(None))  # type: ignore[union-attr]
            )
        )
        for prior in result.all():
            prior.used_at = now
            session.add(prior)

        raw = secrets.token_urlsafe(32)
        token = EmailVerificationToken(
            user_id=user_id,
            token_hash=_hash_token(raw),
            expires_at=now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_TTL_HOURS),
        )
        session.add(token)
        await session.flush()
        return raw

    @staticmethod
    async def verify_token(session: AsyncSession, *, raw_token: str) -> User:
        token_hash = _hash_token(raw_token)
        result = await session.exec(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        )
        token = result.one_or_none()
        if token is None or token.used_at is not None:
            raise TokenInvalidError("Token is invalid or already used")
        if _as_utc(token.expires_at) < datetime.now(timezone.utc):
            raise TokenExpiredError("Token has expired")

        user_result = await session.exec(select(User).where(User.id == token.user_id))
        user = user_result.one()

        now = datetime.now(timezone.utc)
        user.email_verified = True
        user.email_verified_at = now
        token.used_at = now
        session.add(user)
        session.add(token)
        await session.flush()
        return user

    @staticmethod
    async def request_resend(session: AsyncSession, *, email: str) -> str | None:
        """Issue a fresh token for the given email.

        Returns None if the user doesn't exist or is already verified.
        Caller is responsible for rate-limiting and for actually sending the email.
        """
        result = await session.exec(select(User).where(User.email == email))
        user = result.one_or_none()
        if user is None or user.email_verified or user.id is None:
            return None
        return await EmailVerificationService.create_token(session, user_id=user.id)
