"""User-group management commands (issue #519): membership and group-role grants are
CLI-managed, mirroring how user-role assignment is CLI-only.
Authored with LLM (Claude) assistance."""

import asyncio

import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.db import session_scope
from sparkth.lib.permissions import (
    add_group_member,
    assign_role_to_group,
    get_group_by_name,
    get_permission_scope,
    remove_group_member,
    revoke_role_from_group,
)
from sparkth.lib.permissions.exceptions import (
    GroupNotFound,
    InvalidScopeObjectId,
    PermissionScopeNotFound,
    RoleNotFound,
)
from sparkth.lib.plugins import get_plugin_loader

app = typer.Typer(help="User-group management commands")


async def _resolve_user(identifier: str, session: AsyncSession) -> tuple[int, str]:
    """Return (id, username) of the user with the given username or email, or exit non-zero."""
    user = (await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))).first()
    if user is None or user.id is None:
        typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    return user.id, user.username


async def _resolve_group_id(group_name: str, session: AsyncSession) -> int:
    """Return the id of the group named ``group_name``, or exit non-zero if it is missing."""
    try:
        group = await get_group_by_name(group_name, session)
    except GroupNotFound:
        typer.secho(f"Group '{group_name}' not found!", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    if group.id is None:  # unreachable for a DB-loaded row; narrows the Optional for mypy
        raise typer.Exit(code=1)
    return group.id


@app.command("add-member")
def add_member(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    group: str = typer.Argument(..., help="Group name"),
) -> None:
    """Add a user, looked up by username or email, to a group."""
    asyncio.run(_add_member(identifier, group))


async def _add_member(identifier: str, group_name: str) -> None:
    """Resolve the user and group, add the membership, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while the
    database layer is async; this is the awaited implementation. Exits non-zero if the
    user or group is missing.
    """
    async with session_scope() as session:
        user_id, username = await _resolve_user(identifier, session)
        group_id = await _resolve_group_id(group_name, session)
        await add_group_member(user_id, group_id, session)
        await session.commit()
        typer.secho(f"Added {username} to group '{group_name}'.", fg=typer.colors.GREEN)


@app.command("remove-member")
def remove_member(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    group: str = typer.Argument(..., help="Group name"),
) -> None:
    """Remove a user, looked up by username or email, from a group."""
    asyncio.run(_remove_member(identifier, group))


async def _remove_member(identifier: str, group_name: str) -> None:
    """Resolve the user and group, soft-delete the active membership, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while the
    database layer is async; this is the awaited implementation. Exits non-zero if the
    user or group is missing; removing a user who is not a member is a no-op.
    """
    async with session_scope() as session:
        user_id, username = await _resolve_user(identifier, session)
        group_id = await _resolve_group_id(group_name, session)
        await remove_group_member(user_id, group_id, session)
        await session.commit()
        typer.secho(f"Removed {username} from group '{group_name}'.", fg=typer.colors.GREEN)


@app.command("assign-role-to-group")
def assign_role_to_group_command(
    group: str = typer.Argument(..., help="Group name"),
    role: str = typer.Argument(..., help="Role name to assign"),
    scope: str = typer.Option("global", "--scope"),
    scope_object_id: str | None = typer.Option(None, "--scope-object-id"),
) -> None:
    """Assign a role to every member of a group at an optional scope."""
    asyncio.run(_assign_role_to_group(group, role, scope, scope_object_id))


async def _assign_role_to_group(group_name: str, role: str, scope: str, scope_object_id: str | None) -> None:
    """Resolve the group and scope, assign the role to the group, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while the
    database layer is async; this is the awaited implementation. Exits non-zero if the
    group or role is missing, the scope kind is unknown, or the scope and object id
    contradict each other (enforced by the engine's assign_role_to_group).
    """
    # Load plugins first so plugin-declared scope kinds are registered before validation,
    # and a mistyped --scope fails loudly instead of persisting a no-op assignment.
    get_plugin_loader()
    try:
        permission_scope = get_permission_scope(scope)
    except PermissionScopeNotFound:
        typer.secho(f"Unknown scope kind: '{scope}'", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    async with session_scope() as session:
        group_id = await _resolve_group_id(group_name, session)
        try:
            await assign_role_to_group(group_id, role, permission_scope, scope_object_id, session)
        except RoleNotFound:
            typer.secho(f"Role '{role}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        except InvalidScopeObjectId:
            typer.secho(
                f"Invalid --scope-object-id for scope '{scope}': "
                "objectless scopes take no object id; object-bearing scopes require one.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1) from None
        await session.commit()
        typer.secho(f"Assigned role '{role}' to group '{group_name}' (scope: {scope}).", fg=typer.colors.GREEN)


@app.command("revoke-role-from-group")
def revoke_role_from_group_command(
    group: str = typer.Argument(..., help="Group name"),
    role: str = typer.Argument(..., help="Role name to revoke"),
    scope: str = typer.Option("global", "--scope"),
    scope_object_id: str | None = typer.Option(None, "--scope-object-id"),
) -> None:
    """Revoke a role from a group at an optional scope (a no-op when not assigned there)."""
    asyncio.run(_revoke_role_from_group(group, role, scope, scope_object_id))


async def _revoke_role_from_group(group_name: str, role: str, scope: str, scope_object_id: str | None) -> None:
    """Resolve the group and scope, revoke the role from the group, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while the
    database layer is async; this is the awaited implementation. Exits non-zero if the
    group is missing or the scope kind is unknown. Revoking a role that is not assigned
    at the exact scope is a no-op, mirroring the engine's revoke_role_from_group.
    """
    # Load plugins first so plugin-declared scope kinds are registered before validation,
    # and a mistyped --scope fails loudly instead of silently revoking nothing.
    get_plugin_loader()
    try:
        permission_scope = get_permission_scope(scope)
    except PermissionScopeNotFound:
        typer.secho(f"Unknown scope kind: '{scope}'", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    async with session_scope() as session:
        group_id = await _resolve_group_id(group_name, session)
        await revoke_role_from_group(group_id, role, permission_scope, scope_object_id, session)
        await session.commit()
        typer.secho(f"Revoked role '{role}' from group '{group_name}' (scope: {scope}).", fg=typer.colors.GREEN)
