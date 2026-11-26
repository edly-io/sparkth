"""The permission check for actions on one user's activities."""

from typing import cast

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.lib.models import User
from sparkth.lib.testing import (
    AuditEventsFetcher,
    assign_through_group,
    grant_global_permission,
    grant_permissions,
    make_role,
)
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcActivityNotPermitted
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.permissions import (
    PXC_ACTIVITY_DELETE,
    PXC_ACTIVITY_EDIT,
    PXC_ACTIVITY_PLACE,
    PXC_ACTIVITY_PLAY,
    PXC_ACTIVITY_READ,
    PXC_ACTIVITY_UPDATE,
    get_launch_permissions,
    get_permitted_activity,
    has_activity_permission,
    has_launch_permission,
    record_launch_denial,
    require_activity_permission,
)
from sparkth.plugins.pxc.tests.conftest import act_as, assert_activity_permission_denied

PXC_ACTIVITY_PERMISSIONS = (PXC_ACTIVITY_READ, PXC_ACTIVITY_UPDATE, PXC_ACTIVITY_DELETE, PXC_ACTIVITY_PLACE)


async def test_an_author_holds_every_activity_permission_at_their_own_scope(
    session: AsyncSession, authors: tuple[User, User]
) -> None:
    owner, _ = authors
    for permission in PXC_ACTIVITY_PERMISSIONS:
        await require_activity_permission(session, permission, cast(int, owner.id), cast(int, owner.id))


async def test_another_user_is_refused_and_the_refusal_is_recorded(
    session: AsyncSession, authors: tuple[User, User], audit_events: AuditEventsFetcher
) -> None:
    owner, other = authors
    with pytest.raises(PxcActivityNotPermitted):
        await require_activity_permission(session, PXC_ACTIVITY_READ, cast(int, owner.id), cast(int, other.id))
    await assert_activity_permission_denied(audit_events, "pxc.activity.read", owner.id)


async def test_a_grant_at_the_owners_scope_covers_only_the_permission_it_holds(
    session: AsyncSession, authors: tuple[User, User]
) -> None:
    owner, other = authors
    await grant_permissions(session, other, ["pxc.activity.read"], "user", str(owner.id))
    assert await has_activity_permission(session, PXC_ACTIVITY_READ, cast(int, owner.id), cast(int, other.id))
    assert not await has_activity_permission(session, PXC_ACTIVITY_UPDATE, cast(int, owner.id), cast(int, other.id))


async def test_a_global_grant_covers_every_owner(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, other = authors
    await grant_global_permission(session, cast(int, other.id), "pxc.activity.delete")
    assert await has_activity_permission(session, PXC_ACTIVITY_DELETE, cast(int, owner.id), cast(int, other.id))


async def test_a_caller_with_no_account_holds_nothing(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, _ = authors
    assert not await has_activity_permission(session, PXC_ACTIVITY_READ, cast(int, owner.id), 999)


async def test_checking_without_requiring_records_nothing(
    session: AsyncSession, authors: tuple[User, User], audit_events: AuditEventsFetcher
) -> None:
    owner, other = authors
    await has_activity_permission(session, PXC_ACTIVITY_READ, cast(int, owner.id), cast(int, other.id))
    assert await audit_events() == []


async def test_a_permitted_caller_gets_the_activity_the_id_names(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])

    activity = await get_permitted_activity(str(authored_activity.id), PXC_ACTIVITY_READ)

    assert activity.id == authored_activity.id


async def test_a_caller_without_the_permission_is_refused_and_the_refusal_recorded(
    authored_activity: PxcActivity, authors: tuple[User, User], audit_events: AuditEventsFetcher
) -> None:
    act_as(authors[1])

    with pytest.raises(PxcActivityNotPermitted):
        await get_permitted_activity(str(authored_activity.id), PXC_ACTIVITY_UPDATE)

    await assert_activity_permission_denied(audit_events, "pxc.activity.update", authored_activity.owner_user_id)


async def test_an_id_that_names_no_activity_is_not_found_and_records_nothing(
    authors: tuple[User, User], audit_events: AuditEventsFetcher
) -> None:
    act_as(authors[0])

    with pytest.raises(PxcActivityNotFound):
        await get_permitted_activity(str(uuid7()), PXC_ACTIVITY_READ)

    assert await audit_events() == []


def test_a_level_names_the_permissions_that_allow_it() -> None:
    assert get_launch_permissions("edit") == (PXC_ACTIVITY_EDIT,)
    assert get_launch_permissions("play") == (PXC_ACTIVITY_PLAY, PXC_ACTIVITY_EDIT)
    assert get_launch_permissions("view") == (PXC_ACTIVITY_PLAY, PXC_ACTIVITY_EDIT)


def test_an_unknown_level_is_refused_rather_than_served_on_the_play_permission() -> None:
    with pytest.raises(ValueError, match="author"):
        get_launch_permissions("author")


async def test_play_alone_opens_the_play_level_only(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, other = authors
    owner_id, other_id = cast(int, owner.id), cast(int, other.id)
    await grant_permissions(session, other, ["pxc.activity.play"], "user", str(owner_id))
    assert await has_launch_permission(session, "play", owner_id, other_id)
    assert not await has_launch_permission(session, "edit", owner_id, other_id)


async def test_edit_opens_both_levels(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, other = authors
    owner_id, other_id = cast(int, owner.id), cast(int, other.id)
    await grant_permissions(session, other, ["pxc.activity.edit"], "user", str(owner_id))
    assert await has_launch_permission(session, "play", owner_id, other_id)
    assert await has_launch_permission(session, "edit", owner_id, other_id)


async def test_the_management_permissions_open_no_level(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, other = authors
    owner_id, other_id = cast(int, owner.id), cast(int, other.id)
    await grant_permissions(session, other, ["pxc.activity.read", "pxc.activity.update"], "user", str(owner_id))
    assert not await has_launch_permission(session, "play", owner_id, other_id)
    assert not await has_launch_permission(session, "edit", owner_id, other_id)


async def test_an_activity_with_no_owner_is_checked_at_global(
    session: AsyncSession, authors: tuple[User, User]
) -> None:
    owner, other = authors
    other_id = cast(int, other.id)
    await grant_permissions(session, other, ["pxc.activity.play"], "user", str(owner.id))
    assert not await has_launch_permission(session, "play", None, other_id)
    await grant_global_permission(session, other_id, "pxc.activity.play")
    assert await has_launch_permission(session, "play", None, other_id)


async def test_a_caller_with_no_account_opens_no_level(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, _ = authors
    assert not await has_launch_permission(session, "play", cast(int, owner.id), 999)


async def test_a_grant_held_through_a_group_opens_the_level(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, other = authors
    role = await make_role(session, "pxc-players", ["pxc.activity.play"])
    await assign_through_group(session, other, role, "user", str(owner.id))
    assert await has_launch_permission(session, "play", cast(int, owner.id), cast(int, other.id))


async def test_a_refused_play_launch_is_recorded_as_a_denial_of_play(
    authors: tuple[User, User], audit_events: AuditEventsFetcher
) -> None:
    owner, _ = authors
    await record_launch_denial("play", cast(int, owner.id))
    await assert_activity_permission_denied(audit_events, "pxc.activity.play", owner.id)


async def test_a_denial_for_an_activity_with_no_owner_names_the_global_scope(
    audit_events: AuditEventsFetcher,
) -> None:
    await record_launch_denial("edit", None)
    event = (await audit_events())[-1]
    assert (event.target_id, event.error_detail) == ("pxc.activity.edit", "scope=global")
