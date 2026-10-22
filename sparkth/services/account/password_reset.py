"""Self-service password reset through an emailed, single-use link.

``request_password_reset`` issues the link and ``reset_password`` redeems it. Requests
are recorded as ``auth.password_reset_requested`` and redemptions as
``auth.password_reset`` with the ``email`` method. Sending the email and rate limiting
requests are the caller's job: the route does both.
"""

import secrets
from dataclasses import dataclass
from datetime import timedelta
from html import escape as html_escape

import aiosmtplib
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.config import get_settings
from sparkth.core.email import send_email
from sparkth.core.models.base import utc_now
from sparkth.core.models.password_reset import PasswordResetToken
from sparkth.core.models.user import User
from sparkth.core.security import get_password_hash, hash_token
from sparkth.lib.audit import record_event, record_event_now
from sparkth.lib.audit.context import AnonymousActor, UserActor
from sparkth.lib.audit.events import (
    AuditChange,
    AuditOutcome,
    AuditTarget,
    PasswordResetAuditEvent,
    PasswordResetRequestedAuditEvent,
)
from sparkth.lib.i18n import _
from sparkth.lib.log import get_logger
from sparkth.services.account.exceptions import ResetLinkExpired, ResetLinkInvalid

settings = get_settings()
logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ResetEmail:
    """A reset link ready to send: the recipient, their name, and the raw token.

    The raw token exists in plaintext only here and in the email; the database keeps
    its hash.
    """

    to: str
    name: str
    raw_token: str


def _create_audit_snapshot() -> dict[str, str]:
    return {"method": "email"}


async def request_password_reset(session: AsyncSession, email: str) -> ResetEmail | None:
    """Issue a reset link for the account with ``email``, then commit.

    ``email`` is expected to be normalized (trimmed, lowercased) already. Returns the
    link to send, or ``None`` when there is nothing to send: no account has that email
    (nothing is recorded), or the account has no password because it signs in with SSO
    only (recorded as ``denied``). Issuing a link cancels any earlier unused one, so
    only the newest link works.
    """
    user = (await session.exec(select(User).where(User.email == email))).one_or_none()
    if user is None or user.id is None:
        return None

    target = AuditTarget(type="user", id=str(user.id))
    if user.hashed_password is None:
        logger.info("Password reset refused for user %s: account has no password", user.id)
        await record_event(
            session,
            PasswordResetRequestedAuditEvent(
                outcome=AuditOutcome.DENIED,
                actor=AnonymousActor(),
                target=target,
                error_detail="account has no password",
            ),
        )
        await session.commit()
        return None

    now = utc_now()
    pending = await session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id, col(PasswordResetToken.used_at).is_(None)
        )
    )
    for prior in pending.all():
        prior.used_at = now
        session.add(prior)

    raw_token = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES),
        )
    )
    await record_event(
        session,
        PasswordResetRequestedAuditEvent(outcome=AuditOutcome.SUCCESS, actor=AnonymousActor(), target=target),
    )
    await session.commit()
    return ResetEmail(to=user.email, name=user.name, raw_token=raw_token)


async def _refuse_link(error_detail: str) -> None:
    """Record a refused link in its own transaction, so it survives the error response."""
    logger.info("Password reset link refused: %s", error_detail)
    await record_event_now(
        PasswordResetAuditEvent(outcome=AuditOutcome.FAILURE, actor=AnonymousActor(), error_detail=error_detail)
    )


async def reset_password(session: AsyncSession, raw_token: str, new_password: str) -> None:
    """Redeem the reset link ``raw_token``, setting ``new_password``, then commit.

    The link is used up, and the email is marked verified because following the link
    proves the user owns the inbox. Raises ``ResetLinkInvalid`` for an unknown, used or
    replaced link and ``ResetLinkExpired`` for one past its expiry; both are recorded
    first. ``new_password`` is expected to have passed the complexity rules already.
    """
    token = (
        await session.exec(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(raw_token)))
    ).one_or_none()
    if token is None or token.used_at is not None:
        await _refuse_link("token is invalid or already used")
        raise ResetLinkInvalid(_("This password reset link is invalid or has already been used."))
    now = utc_now()
    if token.expires_at < now:
        await _refuse_link("token has expired")
        raise ResetLinkExpired(_("This password reset link has expired. Request a new one."))

    user = (await session.exec(select(User).where(User.id == token.user_id))).one()
    user.hashed_password = get_password_hash(new_password)
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = now
    # updated_at has a default_factory but no onupdate, so the bump is manual.
    user.update_timestamp()
    token.used_at = now
    session.add(user)
    session.add(token)
    await record_event(
        session,
        PasswordResetAuditEvent(
            outcome=AuditOutcome.SUCCESS,
            actor=UserActor(id=str(user.id), label=user.username),
            target=AuditTarget(type="user", id=str(user.id)),
            change=AuditChange(new=_create_audit_snapshot()),
        ),
    )
    await session.commit()


def _build_reset_url(raw_token: str) -> str:
    # The trailing slash is the canonical form under Next's `trailingSlash: true`; the
    # statically exported frontend redirects `/reset-password` and drops the query.
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/reset-password/?token={raw_token}"


def _render_email(reset: ResetEmail) -> tuple[str, str]:
    url = _build_reset_url(reset.raw_token)
    greeting = _("Hi {name},").format(name=reset.name)
    instruction = _("We received a request to reset your Sparkth password. Click the link below to choose a new one:")
    expiry = _("This link expires in {minutes} minutes.").format(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES)
    footer = _("If you didn't ask to reset your password, you can ignore this email.")
    link_label = _("Reset my password")
    text = f"{greeting}\n\n{instruction}\n\n{url}\n\n{expiry}\n\n{footer}\n"
    html = (
        f"<p>{html_escape(greeting)}</p>"
        f"<p>{html_escape(instruction)}</p>"
        f'<p><a href="{html_escape(url, quote=True)}">{html_escape(link_label)}</a></p>'
        f"<p>{html_escape(expiry)}</p>"
        f"<p>{html_escape(footer)}</p>"
    )
    return text, html


async def send_password_reset_email(reset: ResetEmail) -> None:
    """Email the reset link. Runs as a background task after the 202, so a send
    failure is logged rather than raised: nobody is left to receive the error."""
    text_body, html_body = _render_email(reset)
    try:
        await send_email(
            to=reset.to,
            subject=_("Reset your Sparkth password"),
            html_body=html_body,
            text_body=text_body,
        )
    except RuntimeError, aiosmtplib.SMTPException:
        logger.exception("Failed to send password reset email to %s", reset.to)
