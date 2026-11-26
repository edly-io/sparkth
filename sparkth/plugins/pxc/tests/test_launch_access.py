"""Which account a launch token is checked for, and how long an answer holds."""

import pytest
from pxc.lib.permission import Permission
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.lib.models import User
from sparkth.lib.testing import AuditEventsFetcher, grant_permissions
from sparkth.plugins.pxc import launch_access
from sparkth.plugins.pxc.constants import (
    PXC_LMS_USERNAME,
    PXC_PREVIEW_ACTIVITY_INSTANCE,
    PXC_PREVIEW_COURSE_ID,
    PXC_PREVIEW_USER_PREFIX,
)
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcActivityNotPermitted
from sparkth.plugins.pxc.launch_access import require_launch_access
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.tokens import LaunchClaims

BOTH = ["pxc.activity.play", "pxc.activity.edit"]


def _lms_claims(activity: str, level: str = "play") -> LaunchClaims:
    return LaunchClaims(activity, "instance-1", "course-1", "learner-7", Permission(level))


def _preview_claims(activity: PxcActivity, user: User, level: str = "play") -> LaunchClaims:
    return LaunchClaims(
        str(activity.id),
        PXC_PREVIEW_ACTIVITY_INSTANCE,
        PXC_PREVIEW_COURSE_ID,
        f"{PXC_PREVIEW_USER_PREFIX}{user.id}",
        Permission(level),
    )


async def _make_lms_account(session: AsyncSession, permissions: list[str], scope_object_id: str | None) -> User:
    """The LMS account holding ``permissions`` at one owner's user scope, or at global when given no owner."""
    account = User(name="PXC LMS", username=PXC_LMS_USERNAME, email="pxc_lms@sparkth.invalid")
    session.add(account)
    await session.commit()
    scope = "global" if scope_object_id is None else "user"
    await grant_permissions(session, account, permissions, scope, scope_object_id)
    return account


async def test_the_lms_account_launches_a_bundled_activity_at_both_levels(lms_account: User) -> None:
    await require_launch_access(_lms_claims("mcq", "play"))
    await require_launch_access(_lms_claims("mcq", "edit"))


async def test_a_launch_is_refused_when_the_lms_account_does_not_exist(audit_events: AuditEventsFetcher) -> None:
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_lms_claims("mcq"))
    events = await audit_events()
    assert [(e.action, e.target_id, e.error_detail) for e in events] == [
        ("denied", "pxc.activity.play", "scope=global")
    ]


async def test_an_lms_account_with_play_alone_cannot_edit(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    account = await _make_lms_account(session, ["pxc.activity.play"], None)
    await require_launch_access(_lms_claims("mcq", "play"))
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_lms_claims("mcq", "edit"))
    event = (await audit_events())[-1]
    assert (event.target_id, event.actor_id, event.actor_label) == ("pxc.activity.edit", str(account.id), "pxc_lms")


async def test_an_lms_account_with_edit_alone_still_plays(session: AsyncSession) -> None:
    await _make_lms_account(session, ["pxc.activity.edit"], None)
    await require_launch_access(_lms_claims("mcq", "play"))
    await require_launch_access(_lms_claims("mcq", "edit"))


async def test_a_generated_activity_is_checked_at_its_owners_scope(
    session: AsyncSession, authors: tuple[User, User], authored_activity: PxcActivity, audit_events: AuditEventsFetcher
) -> None:
    owner, other = authors
    await _make_lms_account(session, BOTH, str(other.id))
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_lms_claims(str(authored_activity.id)))
    assert (await audit_events())[-1].error_detail == f"scope=user:{owner.id}"


async def test_an_lms_grant_at_the_owners_scope_launches_that_owners_activity(
    session: AsyncSession, authors: tuple[User, User], authored_activity: PxcActivity
) -> None:
    owner, _ = authors
    await _make_lms_account(session, BOTH, str(owner.id))
    await require_launch_access(_lms_claims(str(authored_activity.id)))
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_lms_claims("mcq"))


async def test_a_preview_token_is_checked_for_its_user(
    authors: tuple[User, User], authored_activity: PxcActivity, audit_events: AuditEventsFetcher
) -> None:
    owner, other = authors
    await require_launch_access(_preview_claims(authored_activity, owner))
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_preview_claims(authored_activity, other))
    event = (await audit_events())[-1]
    assert (event.actor_id, event.actor_label) == (str(other.id), "other")


async def test_a_previewer_granted_play_opens_the_play_level(
    session: AsyncSession, authors: tuple[User, User], authored_activity: PxcActivity
) -> None:
    owner, other = authors
    await grant_permissions(session, other, ["pxc.activity.play"], "user", str(owner.id))
    await require_launch_access(_preview_claims(authored_activity, other, "play"))
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_preview_claims(authored_activity, other, "edit"))


async def test_a_soft_deleted_account_holds_nothing(session: AsyncSession, lms_account: User) -> None:
    lms_account.is_deleted = True
    session.add(lms_account)
    await session.commit()
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_lms_claims("mcq"))


async def test_a_soft_deleted_previewer_holds_nothing(
    session: AsyncSession, authors: tuple[User, User], authored_activity: PxcActivity
) -> None:
    owner, _ = authors
    owner.is_deleted = True
    session.add(owner)
    await session.commit()
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_preview_claims(authored_activity, owner))


async def test_a_generated_activity_with_no_row_is_not_found(
    lms_account: User, audit_events: AuditEventsFetcher
) -> None:
    with pytest.raises(PxcActivityNotFound):
        await require_launch_access(_lms_claims(str(uuid7())))
    assert await audit_events() == []


async def test_a_preview_token_with_a_malformed_learner_id_is_refused(
    authors: tuple[User, User], authored_activity: PxcActivity
) -> None:
    claims = LaunchClaims(
        str(authored_activity.id), PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID, "sparkth-abc", Permission.play
    )
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(claims)


async def test_a_preview_token_cannot_borrow_the_lms_accounts_cached_answer(lms_account: User) -> None:
    await require_launch_access(_lms_claims("mcq"))
    borrowed = LaunchClaims(
        "mcq", PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID, PXC_LMS_USERNAME, Permission.play
    )
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(borrowed)


async def test_an_answer_is_reused_for_sixty_seconds(
    session: AsyncSession, lms_account: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(launch_access, "monotonic", lambda: clock[0])
    await require_launch_access(_lms_claims("mcq"))
    lms_account.is_deleted = True
    session.add(lms_account)
    await session.commit()
    clock[0] += 59
    await require_launch_access(_lms_claims("mcq"))
    clock[0] += 2
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_lms_claims("mcq"))


async def test_a_refusal_is_recorded_once_per_window(
    audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = [1000.0]
    monkeypatch.setattr(launch_access, "monotonic", lambda: clock[0])
    for _ in range(2):
        with pytest.raises(PxcActivityNotPermitted):
            await require_launch_access(_lms_claims("mcq"))
    assert len(await audit_events()) == 1
    clock[0] += 61
    with pytest.raises(PxcActivityNotPermitted):
        await require_launch_access(_lms_claims("mcq"))
    assert len(await audit_events()) == 2
