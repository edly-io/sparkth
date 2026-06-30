import asyncio

import typer
from sqlmodel import select

from app.lib.db import session_scope
from app.lib.permissions import PermissionScopeNotFound, RoleNotFound

# Aliased to avoid colliding with this module's own ``assign_role`` Typer command.
from app.lib.permissions import assign_role as grant_role
from app.lib.permissions.registry import PermissionScopesRegistry
from app.lib.permissions.scopes import GLOBAL
from app.lib.plugins import get_plugin_loader
from app.models.user import User

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

    Separate from the Typer command because Typer entrypoints are synchronous while
    the database layer is async; this is the awaited implementation. Exits non-zero
    if the user or role is missing, or the scope and scope object id contradict each
    other — a non-global scope without an object id, or the global scope with one.
    """
    if scope != GLOBAL.name and scope_object_id is None:
        typer.secho("--scope-object-id is required for non-global scopes", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if scope == GLOBAL.name and scope_object_id is not None:
        typer.secho("--scope-object-id is not allowed for the global scope", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    # Validate the scope kind against the registered vocabulary so a mistyped --scope
    # fails loudly instead of persisting a no-op assignment.
    get_plugin_loader()
    try:
        permission_scope = PermissionScopesRegistry().get(scope)
    except PermissionScopeNotFound:
        typer.secho(f"Unknown scope kind: '{scope}'", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    async with session_scope() as session:
        user = (
            await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))
        ).first()
        if user is None or user.id is None:
            typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        try:
            await grant_role(user.id, role, permission_scope, scope_object_id, session)
        except RoleNotFound:
            typer.secho(f"Role '{role}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        await session.commit()
        typer.secho(
            f"Assigned role '{role}' to {user.username} (scope: {scope}).",
            fg=typer.colors.GREEN,
        )
