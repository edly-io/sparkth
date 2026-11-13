from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.cli import users
from sparkth.core.models.user import User
from sparkth.core.permissions.exceptions import RoleNotFound
from sparkth.core.permissions.models import Role, RoleAssignment
from sparkth.lib.permissions import DEFAULT_USER_ROLE, assign_default_role
from sparkth.lib.testing import make_role, make_user
from sparkth.services.whitelist import WhitelistService


async def test_assign_default_role_grants_at_the_users_own_scope(session: AsyncSession) -> None:
    await make_role(session, DEFAULT_USER_ROLE, [])
    user = await make_user(session, "alice")
    assert user.id is not None

    assignment = await assign_default_role(user.id, session)

    assert assignment.scope == "user"
    assert assignment.scope_object_id == str(user.id)
    role = (await session.exec(select(Role).where(Role.name == DEFAULT_USER_ROLE))).one()
    assert assignment.role_id == role.id


async def test_assign_default_role_fails_when_the_role_is_missing(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None

    with pytest.raises(RoleNotFound):
        await assign_default_role(user.id, session)
    assert (await session.exec(select(RoleAssignment))).all() == []


async def _seed_role_and_bystander(session: AsyncSession) -> None:
    """Seed the role and an earlier account, so the account under test is not the first user."""
    await make_role(session, DEFAULT_USER_ROLE, [])
    await make_user(session, "bystander")
    await session.commit()


async def _active_assignments(session: AsyncSession, username: str) -> tuple[User, list[RoleAssignment]]:
    user = (await session.exec(select(User).where(User.username == username))).one()
    assignments = (
        await session.exec(
            select(RoleAssignment)
            .join(Role, col(Role.id) == col(RoleAssignment.role_id))
            .where(
                RoleAssignment.user_id == user.id,
                Role.name == DEFAULT_USER_ROLE,
                RoleAssignment.is_deleted == False,
            )
        )
    ).all()
    return user, list(assignments)


async def test_registration_gives_the_account_the_default_role(client: AsyncClient, session: AsyncSession) -> None:
    await _seed_role_and_bystander(session)
    await WhitelistService.add_entry(session, value="newbie@example.com", added_by_id=1)

    with patch("sparkth.api.v1.auth.settings.REGISTRATION_ENABLED", True):
        response = await client.post(
            "/api/v1/auth/register",
            json={"name": "New", "username": "newbie", "email": "newbie@example.com", "password": "Sup3rSecret!"},
        )

    assert response.status_code == 200
    user, assignments = await _active_assignments(session, "newbie")
    assert [(a.scope, a.scope_object_id) for a in assignments] == [("user", str(user.id))]


async def test_google_signup_gives_the_account_the_default_role(client: AsyncClient, session: AsyncSession) -> None:
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
    assert [(a.scope, a.scope_object_id) for a in assignments] == [("user", str(user.id))]


async def test_cli_create_user_gives_the_account_the_default_role(session: AsyncSession) -> None:
    await _seed_role_and_bystander(session)

    await users._create_user("carol", "carol@example.com", "s3cret", None, True)

    user, assignments = await _active_assignments(session, "carol")
    assert [(a.scope, a.scope_object_id) for a in assignments] == [("user", str(user.id))]
