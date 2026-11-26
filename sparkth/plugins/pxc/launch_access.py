"""The permission check for a launch whose token carries no Sparkth session.

A preview token names the Sparkth user it was minted for, so it is checked for that user. Every other
token comes from the LMS, whose learners and authors have no Sparkth account, so it is checked for the
built-in LMS account. An answer is reused for a short time, so checking the same launch again within it
reads nothing.
"""

from time import monotonic
from typing import cast

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.audit.context import UserActor, bind_audit_actor
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.lib.models import User
from sparkth.plugins.pxc.activities import activity_names, parse_activity_id
from sparkth.plugins.pxc.constants import (
    PXC_LAUNCH_ANSWER_TTL_SECONDS,
    PXC_LMS_USERNAME,
    PXC_PREVIEW_COURSE_ID,
    PXC_PREVIEW_USER_PREFIX,
)
from sparkth.plugins.pxc.exceptions import PxcActivityNotPermitted
from sparkth.plugins.pxc.permissions import get_launch_permissions, has_launch_permission, record_launch_denial
from sparkth.plugins.pxc.store import get_activity
from sparkth.plugins.pxc.tokens import LaunchClaims

logger = get_logger(__name__)

# Whether a launch was permitted, and when that was decided, by (is a preview, who, level, activity).
# ponytail: entries are never evicted; cap it if previewers times activities grows large.
_LAUNCH_ANSWERS: dict[tuple[bool, str, str, str], tuple[float, bool]] = {}


def _get_preview_user_id(learner_id: str) -> int | None:
    """Return the Sparkth user id a preview token's learner id names, or None if it names none."""
    digits = learner_id.removeprefix(PXC_PREVIEW_USER_PREFIX)
    if digits == learner_id or not (digits.isascii() and digits.isdecimal()):
        return None
    return int(digits)


async def _get_launch_account(session: AsyncSession, claims: LaunchClaims) -> User | None:
    """Return the account this token is checked for, or None when there is none or it is soft-deleted."""
    if claims.course_id == PXC_PREVIEW_COURSE_ID:
        user_id = _get_preview_user_id(claims.user_id)
        account = None if user_id is None else await session.get(User, user_id)
    else:
        # TODO: map each LMS account to its own Sparkth account, one to one, and check that account.
        account = (await session.exec(select(User).where(User.username == PXC_LMS_USERNAME))).first()
    if account is None or account.is_deleted:
        return None
    return account


async def _get_activity_owner_id(session: AsyncSession, activity: str) -> int | None:
    """Return the id of the user who owns the activity, or None for a bundled one.

    Raises:
        PxcActivityNotFound: if the name is not a bundled activity and no generated activity has that id.
    """
    if activity in activity_names():
        return None
    return (await get_activity(session, parse_activity_id(activity))).owner_user_id


async def _check_launch(claims: LaunchClaims) -> bool:
    """Whether the token's account may launch the activity at the token's level; a refusal is recorded.

    Raises:
        PxcActivityNotFound: if the token names no activity.
    """
    level = claims.permission.value
    async with session_scope() as session:
        owner_user_id = await _get_activity_owner_id(session, claims.activity)
        account = await _get_launch_account(session, claims)
        if account is not None and await has_launch_permission(session, level, owner_user_id, cast(int, account.id)):
            return True
        if account is not None:
            bind_audit_actor(UserActor(str(account.id), account.username))
        logger.warning(
            "PXC launch at level %s of activity %s denied for account %s",
            level,
            claims.activity,
            None if account is None else account.id,
        )
        await record_launch_denial(level, owner_user_id)
        return False


async def require_launch_access(claims: LaunchClaims) -> None:
    """Require the token's account to hold a permission that allows the launch, reusing a recent answer.

    A preview token is answered for the user it names, and every other token for the LMS account. A
    refusal is recorded once per answer, not on each reuse.

    Raises:
        PxcActivityNotFound: if the token names no activity; nothing is remembered.
        PxcActivityNotPermitted: if the account holds no permission that allows the launch.
    """
    level = claims.permission.value
    is_preview = claims.course_id == PXC_PREVIEW_COURSE_ID
    key = (is_preview, claims.user_id if is_preview else PXC_LMS_USERNAME, level, claims.activity)
    now = monotonic()
    # ponytail: requests for one key arriving before its first answer is stored each run the check and each
    # record a denial; share one in-flight answer per key if that matters.
    answer = _LAUNCH_ANSWERS.get(key)
    if answer is None or now - answer[0] >= PXC_LAUNCH_ANSWER_TTL_SECONDS:
        answer = (now, await _check_launch(claims))
        _LAUNCH_ANSWERS[key] = answer
    if not answer[1]:
        needed = get_launch_permissions(level)[0]
        raise PxcActivityNotPermitted(f"You are not allowed to do this; it needs the {needed.name} permission.")
