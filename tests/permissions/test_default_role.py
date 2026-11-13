import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.permissions.exceptions import RoleNotFound
from sparkth.core.permissions.models import Role, RoleAssignment
from sparkth.lib.permissions import DEFAULT_USER_ROLE, assign_default_role
from sparkth.lib.testing import make_role, make_user


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
