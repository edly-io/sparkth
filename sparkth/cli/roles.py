import asyncio

import typer

from sparkth.cli.audit_context import cli_audit_context
from sparkth.cli.user_lookup import resolve_user
from sparkth.lib.db import session_scope

# Aliased to avoid colliding with this module's own ``assign_role`` Typer command.
from sparkth.lib.permissions import assign_role as grant_role
from sparkth.lib.permissions import get_permission_scope, revoke_role
from sparkth.lib.permissions.exceptions import InvalidScopeObjectId, PermissionScopeNotFound, RoleNotFound
from sparkth.lib.permissions.scopes import PermissionScope
from sparkth.lib.plugins import get_plugin_loader

app = typer.Typer(help="Role management commands")


def _get_scope_or_exit(scope: str) -> PermissionScope:
    """Return the registered scope kind named ``scope``, or exit non-zero if it is unknown.

    Loads the plugins first so plugin-declared scope kinds are registered, which makes a
    mistyped ``--scope`` fail loudly instead of persisting or revoking a no-op.
    """
    get_plugin_loader()
    try:
        return get_permission_scope(scope)
    except PermissionScopeNotFound:
        typer.secho(f"Unknown scope kind: '{scope}'", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None


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
    role is missing, the scope kind is unknown, or the scope and object id contradict each other
    (an objectless scope given an object id, or an object-bearing scope given none — enforced by
    the engine's assign_role).
    """
    permission_scope = _get_scope_or_exit(scope)
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
                f"Assigned role '{role}' to {user.username} (scope: {scope}).",
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
    missing or the scope kind is unknown. Revoking a role the user does not hold at the exact
    scope (including an unknown role name or a mismatched object id) is a no-op, as in the
    engine's revoke_role. Built-in roles can be revoked from a user like any other role.
    """
    permission_scope = _get_scope_or_exit(scope)
    with cli_audit_context():
        async with session_scope() as session:
            user_id, user = await resolve_user(identifier, session)
            await revoke_role(user_id, role, permission_scope, scope_object_id, session)
            await session.commit()
            typer.secho(
                f"Revoked role '{role}' from {user.username} (scope: {scope}).",
                fg=typer.colors.GREEN,
            )
