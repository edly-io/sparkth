"""Self-service password change, recorded as ``auth.password_changed``."""

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.security import get_password_hash, verify_password
from sparkth.lib.audit import record_event, record_event_now
from sparkth.lib.audit.events import AuditChange, AuditOutcome, AuditTarget, PasswordChangedAuditEvent
from sparkth.lib.i18n import _
from sparkth.lib.log import get_logger
from sparkth.services.account.exceptions import IncorrectPassword, PasswordNotSet

logger = get_logger(__name__)


def _create_audit_snapshot() -> dict[str, str]:
    return {"method": "self_service"}


async def change_password(session: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    """Replace ``user``'s password after checking ``current_password``, then commit.

    The success is recorded in ``session`` so it commits with the new hash. A refusal
    is recorded with ``record_event_now`` so it survives the error response, then
    raised: ``PasswordNotSet`` when the account has no password (SSO only), and
    ``IncorrectPassword`` when ``current_password`` does not match. ``new_password``
    is expected to have passed the complexity rules already.
    """
    target = AuditTarget(type="user", id=str(user.id))

    if user.hashed_password is None:
        logger.warning("Password change refused for user %s: account has no password", user.id)
        await record_event_now(
            PasswordChangedAuditEvent(
                outcome=AuditOutcome.DENIED, target=target, error_detail="account has no password"
            )
        )
        raise PasswordNotSet(_("SSO based sign-ins cannot update passwords."))

    if not verify_password(current_password, user.hashed_password):
        logger.info("Password change rejected for user %s: incorrect current password", user.id)
        await record_event_now(
            PasswordChangedAuditEvent(
                outcome=AuditOutcome.FAILURE, target=target, error_detail="incorrect current password"
            )
        )
        raise IncorrectPassword(_("Your current password is incorrect."))

    user.hashed_password = get_password_hash(new_password)
    # updated_at has a default_factory but no onupdate, so the bump is manual.
    user.update_timestamp()
    session.add(user)
    await record_event(
        session,
        PasswordChangedAuditEvent(
            outcome=AuditOutcome.SUCCESS, target=target, change=AuditChange(new=_create_audit_snapshot())
        ),
    )
    await session.commit()
