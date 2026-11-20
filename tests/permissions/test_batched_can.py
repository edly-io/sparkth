"""Engine tests: batched_can answering many permission checks with one grants query.
Authored with LLM (Claude) assistance."""

from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.permissions import (
    GROUP_READ,
    GROUP_UPDATE,
    PermissionCheckQuery,
    batched_can,
    can,
    get_accessible_scope_object_ids,
)
from sparkth.lib.permissions.scopes import (
    GLOBAL,
    GROUP,
    ROLE,
    WHITELIST,
    ObjectlessPermissionScope,
    PermissionScope,
)
from sparkth.lib.testing import add_role_assignment, assign_through_group, make_role, make_user

SCOPE_CHECKS: list[tuple[PermissionScope, str | None]] = [
    (GROUP, "group:7"),
    (GROUP, "group:8"),
    (GROUP, None),
    (ROLE, None),
    (GLOBAL, None),
    (WHITELIST, None),
    (WHITELIST, "whitelist:x"),
]


async def _grant_group_read(
    session: AsyncSession, user: User, scope_name: str, object_id: str | None, via_group: bool
) -> None:
    """Grant ``group.read`` to ``user`` at the scope, by their own assignment or through a group."""
    role = await make_role(session, "reader", [GROUP_READ.name])
    if via_group:
        await assign_through_group(session, user, role, scope_name, object_id)
    else:
        await add_role_assignment(session, user, role, scope_name, object_id)


async def _answer_one_check(session: AsyncSession, user: User, scope: PermissionScope, scope_path: str | None) -> bool:
    """Answer one ``group.read`` check with the single-object check or, for any object, the accessible-ids lookup."""
    if scope_path is None and not isinstance(scope, ObjectlessPermissionScope):
        object_ids = await get_accessible_scope_object_ids(user, GROUP_READ, scope, session)
        return object_ids is None or bool(object_ids)
    return await can(user, GROUP_READ, scope, scope_path, session)


@pytest.mark.parametrize(
    ("scope_name", "object_id", "via_group"),
    [
        pytest.param(GROUP.name, "7", False, id="own-at-object"),
        pytest.param(GROUP.name, "7", True, id="group-at-object"),
        pytest.param(GLOBAL.name, None, False, id="own-global"),
        pytest.param(GLOBAL.name, None, True, id="group-global"),
        pytest.param(ROLE.name, "5", False, id="other-scope"),
        pytest.param(WHITELIST.name, None, False, id="objectless-child"),
    ],
)
async def test_matches_the_single_checks(
    session: AsyncSession, scope_name: str, object_id: str | None, via_group: bool
) -> None:
    user = await make_user(session, "alice")
    await _grant_group_read(session, user, scope_name, object_id, via_group)

    answers = await batched_can(
        user, [PermissionCheckQuery(GROUP_READ, scope, path) for scope, path in SCOPE_CHECKS], session
    )

    assert answers == [await _answer_one_check(session, user, scope, path) for scope, path in SCOPE_CHECKS]


async def test_user_without_grants_is_denied_every_check(session: AsyncSession) -> None:
    user = await make_user(session, "alice")

    answers = await batched_can(
        user, [PermissionCheckQuery(GROUP_READ, scope, path) for scope, path in SCOPE_CHECKS], session
    )

    assert answers == [False] * len(SCOPE_CHECKS)


async def test_answers_follow_check_order_and_repeat_duplicates(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    await _grant_group_read(session, user, GROUP.name, "7", False)

    answers = await batched_can(
        user,
        [
            PermissionCheckQuery(GROUP_READ, GROUP, "group:8"),
            PermissionCheckQuery(GROUP_READ, GROUP, "group:7"),
            PermissionCheckQuery(GROUP_READ, GROUP, "group:7"),
            PermissionCheckQuery(GROUP_READ, GROUP, None),
        ],
        session,
    )

    assert answers == [False, True, True, True]


async def test_grant_for_one_check_does_not_answer_another(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    await _grant_group_read(session, user, WHITELIST.name, None, False)

    answers = await batched_can(
        user,
        [PermissionCheckQuery(GROUP_READ, WHITELIST, None), PermissionCheckQuery(GROUP_READ, GROUP, None)],
        session,
    )

    assert answers == [True, False]


async def test_grant_of_another_permission_does_not_answer(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "updater", [GROUP_UPDATE.name])
    await add_role_assignment(session, user, role, GLOBAL.name, None)

    answers = await batched_can(
        user, [PermissionCheckQuery(GROUP_READ, GROUP, None), PermissionCheckQuery(GROUP_UPDATE, GROUP, None)], session
    )

    assert answers == [False, True]


async def test_soft_deleted_grants_answer_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    own_role = await make_role(session, "own-reader", [GROUP_READ.name])
    group_role = await make_role(session, "group-reader", [GROUP_READ.name])
    assignment = await add_role_assignment(session, user, own_role, GROUP.name, "7")
    membership, _ = await assign_through_group(session, user, group_role, GROUP.name, "8")
    assignment.soft_delete()
    membership.soft_delete()
    await session.flush()

    answers = await batched_can(
        user,
        [
            PermissionCheckQuery(GROUP_READ, GROUP, "group:7"),
            PermissionCheckQuery(GROUP_READ, GROUP, "group:8"),
            PermissionCheckQuery(GROUP_READ, GROUP, None),
        ],
        session,
    )

    assert answers == [False, False, False]


async def test_runs_one_query_for_many_checks(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    await _grant_group_read(session, user, GROUP.name, "7", False)

    with patch.object(session, "exec", wraps=session.exec) as spy:
        await batched_can(
            user, [PermissionCheckQuery(GROUP_READ, scope, path) for scope, path in SCOPE_CHECKS], session
        )

    assert spy.call_count == 1


async def test_no_checks_returns_an_empty_list_without_a_query(session: AsyncSession) -> None:
    user = await make_user(session, "alice")

    with patch.object(session, "exec", wraps=session.exec) as spy:
        assert await batched_can(user, [], session) == []

    assert spy.call_count == 0


async def test_soft_deleted_group_role_assignment_answers_nothing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "reader", [GROUP_READ.name])
    _, assignment = await assign_through_group(session, user, role, GROUP.name, "7")
    assignment.soft_delete()
    await session.flush()

    answers = await batched_can(
        user,
        [PermissionCheckQuery(GROUP_READ, GROUP, "group:7"), PermissionCheckQuery(GROUP_READ, GROUP, None)],
        session,
    )

    assert answers == [False, False]
