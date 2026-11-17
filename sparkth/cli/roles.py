import asyncio

import typer

from sparkth.cli.audit_context import cli_audit_context
from sparkth.cli.scope_lookup import resolve_scope, validate_scope_object
from sparkth.cli.user_lookup import resolve_user
from sparkth.lib.db import session_scope

# Aliased to avoid colliding with this module's own ``assign_role`` Typer command.
from sparkth.lib.permissions import assign_role as grant_role
from sparkth.lib.permissions import revoke_role
from sparkth.lib.permissions.exceptions import InvalidScopeObjectId, RoleNotFound

app = typer.Typer(help="Role management commands")


@app.command("assign-role")
def assign_role(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    role: str = typer.Argument(..., help="Role name to assign"),
    scope: str = typer.Option("global", "--scope"),
    scope_object_id: str | None = typer.Option(None, "--scope-object-id"),
) -> None:
    """Assign a role to a user, looked up by username or email, at an optional scope."""
    asyncio.run(_assign_role(identifier, role, scope, scope_object_id))


async def _assign_role(identifier: str, role: str, scope: str, scope_object_id: str | None) -> None:
    """Resolve the user, assign the role, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while the
    database layer is async; this is the awaited implementation. Exits non-zero if the user or
    role is missing, the scope kind is unknown, the plugin scope names a plugin that is not loaded,
    or the scope and object id contradict each other (an objectless scope given an object id, or an
    object-bearing scope given none — enforced by the engine's assign_role).
    """
    permission_scope = resolve_scope(scope)
    validate_scope_object(permission_scope, scope_object_id)
    where = f"{scope}:{scope_object_id}" if scope_object_id else scope
    with cli_audit_context():
        async with session_scope() as session:
            user_id, user = await resolve_user(identifier, session)
            try:
                await grant_role(user_id, role, permission_scope, scope_object_id, session)
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
            typer.secho(
                f"Assigned role '{role}' to {user.username} (scope: {where}).",
                fg=typer.colors.GREEN,
            )


@app.command("revoke-role")
def revoke_role_command(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    role: str = typer.Argument(..., help="Role name to revoke"),
    scope: str = typer.Option("global", "--scope"),
    scope_object_id: str | None = typer.Option(None, "--scope-object-id"),
) -> None:
    """Revoke a user's role assignment at an optional scope (a no-op when not assigned there)."""
    asyncio.run(_revoke_role(identifier, role, scope, scope_object_id))


async def _revoke_role(identifier: str, role: str, scope: str, scope_object_id: str | None) -> None:
    """Resolve the user and scope, revoke the role assignment, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while the
    database layer is async; this is the awaited implementation. Exits non-zero if the user is
    missing, the scope kind is unknown, or the scope and object id contradict each other. A user
    who holds no such assignment at the exact scope (an unknown role name included) gets a
    "nothing revoked" notice and a zero exit. Built-in roles can be revoked like any other role.
    """
    permission_scope = resolve_scope(scope)
    where = f"{scope}:{scope_object_id}" if scope_object_id else scope
    with cli_audit_context():
        async with session_scope() as session:
            user_id, user = await resolve_user(identifier, session)
            try:
                revoked = await revoke_role(user_id, role, permission_scope, scope_object_id, session)
            except InvalidScopeObjectId:
                typer.secho(
                    f"Invalid --scope-object-id for scope '{scope}': "
                    "objectless scopes take no object id; object-bearing scopes require one.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1) from None
            await session.commit()
            if revoked:
                typer.secho(f"Revoked role '{role}' from {user.username} (scope: {where}).", fg=typer.colors.GREEN)
            else:
                typer.secho(
                    f"{user.username} holds no '{role}' assignment at {where}; nothing revoked.",
                    fg=typer.colors.YELLOW,
                )
