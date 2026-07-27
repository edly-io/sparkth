"""User-group management commands (issue #519): membership and group-role grants are
CLI-managed, mirroring how user-role assignment is CLI-only.
Authored with LLM (Claude) assistance."""

import asyncio

import typer
from sqlmodel import select

from sparkth.core.models.user import User
from sparkth.lib.db import session_scope
from sparkth.lib.permissions import add_group_member, assign_role_to_group, get_group_by_name, get_permission_scope
from sparkth.lib.permissions.exceptions import (
    GroupNotFound,
    InvalidScopeObjectId,
    PermissionScopeNotFound,
    RoleNotFound,
)
from sparkth.lib.plugins import get_plugin_loader

app = typer.Typer(help="User-group management commands")


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
        user = (
            await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))
        ).first()
        if user is None or user.id is None:
            typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        try:
            group = await get_group_by_name(group_name, session)
        except GroupNotFound:
            typer.secho(f"Group '{group_name}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        if group.id is None:
            typer.secho(f"Group '{group_name}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        await add_group_member(user.id, group.id, session)
        await session.commit()
        typer.secho(f"Added {user.username} to group '{group_name}'.", fg=typer.colors.GREEN)


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
        try:
            group = await get_group_by_name(group_name, session)
        except GroupNotFound:
            typer.secho(f"Group '{group_name}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        if group.id is None:
            typer.secho(f"Group '{group_name}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        try:
            await assign_role_to_group(group.id, role, permission_scope, scope_object_id, session)
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
