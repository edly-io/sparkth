from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.cli import users
from sparkth.core.models.user import User
from sparkth.core.permissions.constants import DEFAULT_ROLES
from sparkth.core.permissions.exceptions import RoleNotFound
from sparkth.core.permissions.models import Role, RoleAssignment
from sparkth.lib.permissions import PLUGIN_USE, PLUGIN_USER_ROLE, SPARKTH_USER_ROLE, assign_default_roles, can
from sparkth.lib.permissions.scopes import GLOBAL, PLUGIN, USER, build_scope_path
from sparkth.lib.testing import make_role, make_user
from sparkth.services.whitelist import WhitelistService


async def test_assign_default_roles_grants_both_roles(session: AsyncSession) -> None:
    await make_role(session, SPARKTH_USER_ROLE, [])
    await make_role(session, PLUGIN_USER_ROLE, [PLUGIN_USE.name])
    user = await make_user(session, "alice")
    assert user.id is not None

    assignments = await assign_default_roles(user.id, session)

    names = {role.id: role.name for role in (await session.exec(select(Role))).all()}
    assert [
        (names[assignment.role_id], assignment.scope, assignment.scope_object_id) for assignment in assignments
    ] == [
        (SPARKTH_USER_ROLE, USER.name, str(user.id)),
        (PLUGIN_USER_ROLE, GLOBAL.name, None),
    ]


async def test_assign_default_roles_gives_exactly_the_default_roles(session: AsyncSession) -> None:
    await make_role(session, SPARKTH_USER_ROLE, [])
    await make_role(session, PLUGIN_USER_ROLE, [PLUGIN_USE.name])
    user = await make_user(session, "alice")
    assert user.id is not None

    assignments = await assign_default_roles(user.id, session)

    names = {role.id: role.name for role in (await session.exec(select(Role))).all()}
    assert {names[assignment.role_id] for assignment in assignments} == DEFAULT_ROLES


async def test_a_role_is_default_only_when_every_account_is_given_it() -> None:
    assert {name for name in DEFAULT_ROLES if Role(name=name).is_default} == DEFAULT_ROLES
    assert Role(name="admin").is_default is False


async def test_assign_default_roles_fails_when_plugin_user_is_missing(session: AsyncSession) -> None:
    await make_role(session, SPARKTH_USER_ROLE, [])
    user = await make_user(session, "alice")
    assert user.id is not None

    with pytest.raises(RoleNotFound):
        await assign_default_roles(user.id, session)


async def test_assign_default_roles_fails_when_no_role_is_seeded(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None

    with pytest.raises(RoleNotFound):
        await assign_default_roles(user.id, session)
    assert (await session.exec(select(RoleAssignment))).all() == []


async def test_default_roles_let_a_user_use_any_plugin(session: AsyncSession) -> None:
    await make_role(session, SPARKTH_USER_ROLE, [])
    await make_role(session, PLUGIN_USER_ROLE, [PLUGIN_USE.name])
    user = await make_user(session, "alice")
    assert user.id is not None
    await assign_default_roles(user.id, session)

    assert await can(user, PLUGIN_USE, PLUGIN, build_scope_path(PLUGIN, "slack"), session)


async def _seed_role_and_bystander(session: AsyncSession) -> None:
    """Seed the role and an earlier account, so the account under test is not the first user."""
    await make_role(session, SPARKTH_USER_ROLE, [])
    await make_role(session, PLUGIN_USER_ROLE, [PLUGIN_USE.name])
    await make_user(session, "bystander")
    await session.commit()


async def _active_assignments(session: AsyncSession, username: str) -> tuple[User, list[tuple[str, str, str | None]]]:
    user = (await session.exec(select(User).where(User.username == username))).one()
    rows = (
        await session.exec(
            select(Role.name, RoleAssignment.scope, RoleAssignment.scope_object_id)
            .join(Role, col(Role.id) == col(RoleAssignment.role_id))
            .where(RoleAssignment.user_id == user.id, RoleAssignment.is_deleted == False)
            .order_by(col(RoleAssignment.id))
        )
    ).all()
    return user, [(name, scope, object_id) for name, scope, object_id in rows]


def _default_roles(user: User) -> list[tuple[str, str, str | None]]:
    return [(SPARKTH_USER_ROLE, USER.name, str(user.id)), (PLUGIN_USER_ROLE, GLOBAL.name, None)]


async def test_registration_gives_the_account_the_default_roles(client: AsyncClient, session: AsyncSession) -> None:
    await _seed_role_and_bystander(session)
    await WhitelistService.add_entry(session, value="newbie@example.com", added_by_id=1)

    with patch("sparkth.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "New", "username": "newbie", "email": "newbie@example.com", "password": "Sup3rSecret!"},
        )

    assert response.status_code == 200
    user, assignments = await _active_assignments(session, "newbie")
    assert assignments == _default_roles(user)


async def test_google_signup_gives_the_account_the_default_roles(client: AsyncClient, session: AsyncSession) -> None:
    await _seed_role_and_bystander(session)
    await WhitelistService.add_entry(session, value="gus@example.com", added_by_id=1)

    with (
        patch("sparkth.api.v1.auth.exchange_auth_code", new_callable=AsyncMock, return_value={"access_token": "x"}),
        patch(
            "sparkth.api.v1.auth.get_google_user_info",
            new_callable=AsyncMock,
            return_value={"id": "gid-1", "email": "gus@example.com", "name": "Gus"},
        ),
    ):
        response = await client.get("/api/v1/auth/google/callback?code=x")

    assert response.status_code == 302
    user, assignments = await _active_assignments(session, "gus")
    assert assignments == _default_roles(user)


async def test_cli_create_user_gives_the_account_the_default_roles(session: AsyncSession) -> None:
    await _seed_role_and_bystander(session)

    await users._create_user("carol", "carol@example.com", "s3cret", None, True)

    user, assignments = await _active_assignments(session, "carol")
    assert assignments == _default_roles(user)
