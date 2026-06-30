import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.permissions import utils as permissions_utils
from app.core.permissions.exceptions import RoleNotFound
from app.core.permissions.models import Role, RoleAssignment, RolePermission
from app.lib.permissions import Permission, assign_role, can, has_role, revoke_role
from app.lib.permissions.scopes import GLOBAL, PermissionScope
from app.models.user import User


def test_global_scope_name() -> None:
    assert GLOBAL.name == "global"


def test_role_not_found_carries_name() -> None:
    exc = RoleNotFound("teacher")
    assert exc.role_name == "teacher"
    assert "teacher" in str(exc)


async def test_role_assignment_global_scope_round_trips(session: AsyncSession) -> None:
    role = Role(name="grader")
    session.add(role)
    await session.flush()
    assert role.id is not None

    assignment = RoleAssignment(user_id=1, role_id=role.id, scope=GLOBAL.name, scope_object_id=None)
    session.add(assignment)
    await session.flush()

    assert assignment.id is not None
    assert assignment.scope == GLOBAL.name
    assert assignment.scope_object_id is None
    assert assignment.is_deleted is False


async def test_role_assignment_non_global_scope_round_trips(session: AsyncSession) -> None:
    role = Role(name="grader")
    session.add(role)
    await session.flush()
    assert role.id is not None

    assignment = RoleAssignment(user_id=1, role_id=role.id, scope="course", scope_object_id="42")
    session.add(assignment)
    await session.flush()

    assert assignment.id is not None
    assert assignment.scope == "course"
    assert assignment.scope_object_id == "42"


async def test_global_scope_with_object_id_is_rejected(session: AsyncSession) -> None:
    role = Role(name="grader")
    session.add(role)
    await session.flush()
    assert role.id is not None

    # The scope CHECK constraint rejects a global scope carrying an object id. The
    # savepoint isolates the rollback from the fixture's outer transaction.
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(RoleAssignment(user_id=1, role_id=role.id, scope=GLOBAL.name, scope_object_id="42"))
            await session.flush()


async def test_non_global_scope_without_object_id_is_rejected(session: AsyncSession) -> None:
    role = Role(name="grader")
    session.add(role)
    await session.flush()
    assert role.id is not None

    # The scope CHECK constraint rejects a non-global scope that omits its object id.
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(RoleAssignment(user_id=1, role_id=role.id, scope="course", scope_object_id=None))
            await session.flush()


async def test_role_permission_round_trips(session: AsyncSession) -> None:
    role = Role(name="grader")
    session.add(role)
    await session.flush()
    assert role.id is not None

    session.add(RolePermission(role_id=role.id, permission="assignment.grade"))
    await session.flush()


async def make_user(session: AsyncSession, username: str) -> User:
    user = User(
        name="T",
        username=username,
        email=f"{username}@example.com",
        hashed_password="x",
    )
    session.add(user)
    await session.flush()
    return user


async def make_role(session: AsyncSession, name: str, permissions: list[str]) -> Role:
    role = Role(name=name)
    session.add(role)
    await session.flush()
    assert role.id is not None
    for permission in permissions:
        session.add(RolePermission(role_id=role.id, permission=permission))
    await session.flush()
    return role


async def test_can_denies_without_assignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_can_allows_with_assigned_role(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and role.id is not None
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is True


async def test_can_denies_permission_at_other_scope(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and role.id is not None
    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope="course", scope_object_id="1"))
    await session.flush()
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_assign_role_creates_assignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", ["assignment.grade"])
    assignment = await assign_role(user.id, "grader", GLOBAL, None, session)
    assert assignment.id is not None
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is True


async def test_assign_role_unknown_role_raises(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    with pytest.raises(RoleNotFound):
        await assign_role(user.id, "nope", GLOBAL, None, session)


async def test_assign_role_recovers_from_concurrent_insert(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate the check-then-insert race: a concurrent request already created the
    # assignment, but this call's existence check misses it (the TOCTOU window), so it
    # tries to insert and hits the unique index. assign_role must recover by re-querying
    # and returning the existing row, not surface the IntegrityError as a 500.
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", [])
    assert user.id is not None and role.id is not None
    existing = RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None)
    session.add(existing)
    await session.flush()

    real_find = permissions_utils._find_active_assignment
    calls = {"n": 0}

    async def find_missing_first(
        user_id: int,
        role_id: int,
        permission_scope: PermissionScope,
        scope_object_id: str | None,
        db: AsyncSession,
    ) -> RoleAssignment | None:
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # the existence check misses, as if the concurrent row isn't visible yet
        return await real_find(user_id, role_id, permission_scope, scope_object_id, db)

    monkeypatch.setattr(permissions_utils, "_find_active_assignment", find_missing_first)

    result = await assign_role(user.id, "grader", GLOBAL, None, session)

    assert result.id == existing.id


async def test_revoke_role_revokes_access(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", ["assignment.grade"])
    await assign_role(user.id, "grader", GLOBAL, None, session)
    await revoke_role(user.id, "grader", GLOBAL, None, session)
    assert await can(user, Permission("assignment.grade"), GLOBAL, None, session) is False


async def test_revoke_role_noop_when_no_assignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", ["assignment.grade"])
    await revoke_role(user.id, "grader", GLOBAL, None, session)


async def test_has_role_false_without_assignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    await make_role(session, "admin", [])
    assert await has_role(user, "admin", GLOBAL, None, session) is False


async def test_has_role_true_when_assigned(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "admin", [])
    await assign_role(user.id, "admin", GLOBAL, None, session)
    assert await has_role(user, "admin", GLOBAL, None, session) is True


async def test_has_role_is_scope_specific(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", [])
    await assign_role(user.id, "grader", PermissionScope("course"), "1", session)
    # The same role at a different scope must not satisfy the global check.
    assert await has_role(user, "grader", GLOBAL, None, session) is False
    assert await has_role(user, "grader", PermissionScope("course"), "1", session) is True


async def test_has_role_false_after_revoke(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "admin", [])
    await assign_role(user.id, "admin", GLOBAL, None, session)
    await revoke_role(user.id, "admin", GLOBAL, None, session)
    assert await has_role(user, "admin", GLOBAL, None, session) is False


def test_facade_exposes_public_surface() -> None:
    from app.core.permissions.hooks import PERMISSION_SCOPES, PERMISSIONS
    from app.core.permissions.scopes import GLOBAL, PermissionScope
    from app.lib import permissions as facade
    from app.lib.permissions import scopes as scopes_facade

    assert facade.can is can
    assert facade.assign_role is assign_role
    assert facade.revoke_role is revoke_role
    assert facade.has_role is has_role
    assert issubclass(facade.RoleNotFound, Exception)
    # Plugins author against the facade for the hooks they register through.
    assert facade.PERMISSIONS is PERMISSIONS
    assert facade.PERMISSION_SCOPES is PERMISSION_SCOPES
    # The scope class and the GLOBAL root are re-exported from the app.lib.permissions.scopes
    # submodule (not the package facade), so plugins import them from there.
    assert scopes_facade.PermissionScope is PermissionScope
    assert scopes_facade.GLOBAL is GLOBAL


async def test_assign_role_is_idempotent(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    assert user.id is not None
    await make_role(session, "grader", ["assignment.grade"])

    first = await assign_role(user.id, "grader", GLOBAL, None, session)
    second = await assign_role(user.id, "grader", GLOBAL, None, session)

    assert first.id == second.id
    active = (
        await session.exec(
            select(RoleAssignment).where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.is_deleted == False,
            )
        )
    ).all()
    assert len(active) == 1


async def test_duplicate_active_global_assignment_is_rejected(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and role.id is not None

    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()

    # Savepoint so the expected violation rolls back without poisoning the
    # fixture's outer transaction.
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))


async def test_soft_deleted_assignment_does_not_block_reassignment(session: AsyncSession) -> None:
    user = await make_user(session, "alice")
    role = await make_role(session, "grader", ["assignment.grade"])
    assert user.id is not None and role.id is not None

    revoked = RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None)
    session.add(revoked)
    await session.flush()
    revoked.soft_delete()
    session.add(revoked)
    await session.flush()

    session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope=GLOBAL.name, scope_object_id=None))
    await session.flush()
