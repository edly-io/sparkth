import asyncio

import typer
from sqlmodel import select

from app.lib.db import session_scope
from app.lib.permissions import PermissionService, RoleNotFound
from app.models.user import User

app = typer.Typer(help="Role management commands")


@app.command()
def assign_role(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    role: str = typer.Argument(..., help="Role name to assign"),
    scope_type: str = typer.Option("global", "--scope-type"),
    scope_id: str | None = typer.Option(None, "--scope-id"),
) -> None:
    """Assign a role to a user, looked up by username or email, at an optional scope."""
    asyncio.run(_assign_role(identifier, role, scope_type, scope_id))


async def _assign_role(identifier: str, role: str, scope_type: str, scope_id: str | None) -> None:
    """Resolve the user, assign the role, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while
    the database layer is async; this is the awaited implementation. Exits non-zero
    if the user or the role does not exist.
    """
    async with session_scope() as session:
        user = (
            await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))
        ).first()
        if user is None or user.id is None:
            typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        try:
            await PermissionService(session).assign_role(user.id, role, scope_type, scope_id)
        except RoleNotFound:
            typer.secho(f"Role '{role}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        await session.commit()
        typer.secho(
            f"Assigned role '{role}' to {user.username} (scope: {scope_type}).",
            fg=typer.colors.GREEN,
        )
