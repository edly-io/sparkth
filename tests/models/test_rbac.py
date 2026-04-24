from typing import cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.rbac import Permission, RoleName, RolePermission, UserRole
from app.models.user import User


def test_role_name_enum_values() -> None:
    assert RoleName.SUPERUSER.value == "superuser"
    assert RoleName.ADMIN.value == "admin"
    assert RoleName.MEMBER.value == "member"
    assert len(RoleName) == 3


async def test_create_user_role(session: AsyncSession) -> None:
    user = User(name="Test", username="roleuser1", email="role1@test.com", hashed_password="fake")
    session.add(user)
    await session.flush()

    user_role = UserRole(user_id=cast(int, user.id), role=RoleName.ADMIN)
    session.add(user_role)
    await session.flush()

    assert user_role.id is not None
    assert user_role.user_id == user.id
    assert user_role.role == RoleName.ADMIN


async def test_user_role_unique_constraint(session: AsyncSession) -> None:
    user = User(name="Test", username="roleuser2", email="role2@test.com", hashed_password="fake")
    session.add(user)
    await session.flush()

    role1 = UserRole(user_id=cast(int, user.id), role=RoleName.MEMBER)
    session.add(role1)
    await session.flush()

    role2 = UserRole(user_id=cast(int, user.id), role=RoleName.MEMBER)
    session.add(role2)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_user_can_have_multiple_roles(session: AsyncSession) -> None:
    user = User(name="Test", username="roleuser3", email="role3@test.com", hashed_password="fake")
    session.add(user)
    await session.flush()

    role1 = UserRole(user_id=cast(int, user.id), role=RoleName.ADMIN)
    role2 = UserRole(user_id=cast(int, user.id), role=RoleName.MEMBER)
    session.add_all([role1, role2])
    await session.flush()

    assert role1.id is not None
    assert role2.id is not None
    assert role1.role != role2.role


async def test_create_permission(session: AsyncSession) -> None:
    perm = Permission(name="users:list", description="List all users")
    session.add(perm)
    await session.flush()

    assert perm.id is not None
    assert perm.name == "users:list"
    assert perm.description == "List all users"


async def test_permission_unique_name_constraint(session: AsyncSession) -> None:
    perm1 = Permission(name="users:manage", description="Manage users")
    session.add(perm1)
    await session.flush()

    perm2 = Permission(name="users:manage", description="Duplicate")
    session.add(perm2)
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_create_role_permission(session: AsyncSession) -> None:
    perm = Permission(name="users:read", description="Read user profiles")
    session.add(perm)
    await session.flush()

    role_perm = RolePermission(role=RoleName.ADMIN, permission_id=cast(int, perm.id))
    session.add(role_perm)
    await session.flush()

    assert role_perm.id is not None
    assert role_perm.role == RoleName.ADMIN
    assert role_perm.permission_id == perm.id


async def test_role_permission_unique_constraint(session: AsyncSession) -> None:
    perm = Permission(name="plugins:manage", description="Manage plugins")
    session.add(perm)
    await session.flush()

    rp1 = RolePermission(role=RoleName.ADMIN, permission_id=cast(int, perm.id))
    session.add(rp1)
    await session.flush()

    rp2 = RolePermission(role=RoleName.ADMIN, permission_id=cast(int, perm.id))
    session.add(rp2)
    with pytest.raises(IntegrityError):
        await session.flush()
