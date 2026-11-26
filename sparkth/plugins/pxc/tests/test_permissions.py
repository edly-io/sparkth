"""The permission check for actions on one user's activities."""

from typing import cast

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.lib.models import User
from sparkth.lib.testing import AuditEventsFetcher, grant_global_permission, grant_permissions
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcActivityNotPermitted
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.permissions import (
    PXC_ACTIVITY_DELETE,
    PXC_ACTIVITY_PLACE,
    PXC_ACTIVITY_READ,
    PXC_ACTIVITY_UPDATE,
    get_permitted_activity,
    has_activity_permission,
    require_activity_permission,
)
from sparkth.plugins.pxc.tests.conftest import act_as, assert_activity_permission_denied

ALL_FOUR = (PXC_ACTIVITY_READ, PXC_ACTIVITY_UPDATE, PXC_ACTIVITY_DELETE, PXC_ACTIVITY_PLACE)


async def test_an_author_holds_every_activity_permission_at_their_own_scope(
    session: AsyncSession, authors: tuple[User, User]
) -> None:
    owner, _ = authors
    for permission in ALL_FOUR:
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
    await session.commit()
    assert await has_activity_permission(session, PXC_ACTIVITY_READ, cast(int, owner.id), cast(int, other.id))
    assert not await has_activity_permission(session, PXC_ACTIVITY_UPDATE, cast(int, owner.id), cast(int, other.id))


async def test_a_global_grant_covers_every_owner(session: AsyncSession, authors: tuple[User, User]) -> None:
    owner, other = authors
    await grant_global_permission(session, cast(int, other.id), "pxc.activity.delete")
    await session.commit()
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
