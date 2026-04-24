from typing import cast

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.rbac import Permission, RoleName, RolePermission
from app.models.user import User
from app.services.rbac import (
    assign_role,
    get_role_permissions,
    get_user_roles,
    has_permission,
    has_role,
    is_superuser,
    remove_role,
    seed_default_permissions,
)


async def _create_user(session: AsyncSession, username: str, email: str) -> User:
    user = User(name="Test", username=username, email=email, hashed_password="fake")
    session.add(user)
    await session.flush()
    return user


async def _seed_permission(session: AsyncSession, name: str, description: str = "test") -> Permission:
    perm = Permission(name=name, description=description)
    session.add(perm)
    await session.flush()
    return perm


async def _assign_perm_to_role(session: AsyncSession, role: RoleName, permission_id: int) -> None:
    rp = RolePermission(role=role.value, permission_id=permission_id)
    session.add(rp)
    await session.flush()


async def test_assign_role(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role1", "svc_role1@test.com")
    result = await assign_role(session, cast(int, user.id), RoleName.ADMIN)

    assert result.user_id == user.id
    assert result.role == RoleName.ADMIN.value


async def test_assign_duplicate_role_is_idempotent(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role2", "svc_role2@test.com")
    first = await assign_role(session, cast(int, user.id), RoleName.MEMBER)
    second = await assign_role(session, cast(int, user.id), RoleName.MEMBER)

    assert first.id == second.id


async def test_remove_role(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role3", "svc_role3@test.com")
    await assign_role(session, cast(int, user.id), RoleName.ADMIN)

    await remove_role(session, cast(int, user.id), RoleName.ADMIN)

    roles = await get_user_roles(session, cast(int, user.id))
    assert RoleName.ADMIN not in roles


async def test_remove_nonexistent_role(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role4", "svc_role4@test.com")
    # Should not raise
    await remove_role(session, cast(int, user.id), RoleName.SUPERUSER)


async def test_get_user_roles(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role5", "svc_role5@test.com")
    await assign_role(session, cast(int, user.id), RoleName.ADMIN)
    await assign_role(session, cast(int, user.id), RoleName.MEMBER)

    roles = await get_user_roles(session, cast(int, user.id))
    assert set(roles) == {RoleName.ADMIN, RoleName.MEMBER}


async def test_has_role_true(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role6", "svc_role6@test.com")
    await assign_role(session, cast(int, user.id), RoleName.ADMIN)

    assert await has_role(session, cast(int, user.id), RoleName.ADMIN) is True


async def test_has_role_false(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role7", "svc_role7@test.com")

    assert await has_role(session, cast(int, user.id), RoleName.ADMIN) is False


async def test_is_superuser_true(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role8", "svc_role8@test.com")
    await assign_role(session, cast(int, user.id), RoleName.SUPERUSER)

    assert await is_superuser(session, cast(int, user.id)) is True


async def test_is_superuser_false(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_role9", "svc_role9@test.com")
    await assign_role(session, cast(int, user.id), RoleName.MEMBER)

    assert await is_superuser(session, cast(int, user.id)) is False


async def test_has_permission_superuser_bypasses_all(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_perm1", "svc_perm1@test.com")
    await assign_role(session, cast(int, user.id), RoleName.SUPERUSER)

    # Superuser has any permission, even ones that don't exist
    assert await has_permission(session, cast(int, user.id), "anything:at_all") is True


async def test_has_permission_admin_with_assigned_perm(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_perm2", "svc_perm2@test.com")
    await assign_role(session, cast(int, user.id), RoleName.ADMIN)

    perm = await _seed_permission(session, "users:list_svc", "List users")
    await _assign_perm_to_role(session, RoleName.ADMIN, cast(int, perm.id))

    assert await has_permission(session, cast(int, user.id), "users:list_svc") is True


async def test_has_permission_member_denied(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_perm3", "svc_perm3@test.com")
    await assign_role(session, cast(int, user.id), RoleName.MEMBER)

    perm = await _seed_permission(session, "users:manage_svc", "Manage users")
    await _assign_perm_to_role(session, RoleName.ADMIN, cast(int, perm.id))

    assert await has_permission(session, cast(int, user.id), "users:manage_svc") is False


async def test_has_permission_no_roles_denied(session: AsyncSession) -> None:
    user = await _create_user(session, "svc_perm4", "svc_perm4@test.com")

    assert await has_permission(session, cast(int, user.id), "users:list") is False


async def test_get_role_permissions(session: AsyncSession) -> None:
    perm1 = await _seed_permission(session, "test:perm_a", "Perm A")
    perm2 = await _seed_permission(session, "test:perm_b", "Perm B")
    await _assign_perm_to_role(session, RoleName.ADMIN, cast(int, perm1.id))
    await _assign_perm_to_role(session, RoleName.ADMIN, cast(int, perm2.id))

    perms = await get_role_permissions(session, RoleName.ADMIN)
    assert "test:perm_a" in perms
    assert "test:perm_b" in perms


async def test_seed_default_permissions(session: AsyncSession) -> None:
    await seed_default_permissions(session)

    # Verify expected permissions exist
    perms = await get_role_permissions(session, RoleName.ADMIN)
    assert "users:list" in perms
    assert "users:read" in perms
    assert "users:manage" in perms
    assert "users:assign_role" in perms
    assert "plugins:manage" in perms
