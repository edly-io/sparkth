"""Organization-structure membership commands: seating users in units is CLI-managed, mirroring the
CLI-only posture of user-role assignment and group membership.
Authored with LLM (Claude) assistance."""

import asyncio

import typer
from sqlmodel import select

from sparkth.core.models.user import User
from sparkth.lib.db import session_scope
from sparkth.lib.organization import (
    OrganizationalUnitNotFound,
    add_organization_member,
    get_organizational_unit,
    remove_organization_member,
)

app = typer.Typer(help="Organization-tree membership commands")


@app.command("add-member")
def add_member(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    organizational_unit_id: int = typer.Argument(..., help="Organizational unit id (names are only sibling-unique)"),
) -> None:
    """Seat a user, looked up by username or email, in an organizational unit."""
    asyncio.run(_add_member(identifier, organizational_unit_id))


async def _add_member(identifier: str, organizational_unit_id: int) -> None:
    """Resolve the user and unit, add the membership, and commit the change.

    Separate from the Typer command because Typer entrypoints are synchronous while the
    database layer is async. Exits non-zero if the user or unit is missing.
    """
    async with session_scope() as session:
        user = (
            await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))
        ).first()
        if user is None or user.id is None:
            typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        try:
            unit = await get_organizational_unit(organizational_unit_id, session)
        except OrganizationalUnitNotFound:
            typer.secho(f"Organizational unit '{organizational_unit_id}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        await add_organization_member(user.id, organizational_unit_id, session)
        await session.commit()
        typer.secho(
            f"Added {user.username} to organizational unit '{unit.name}' ({organizational_unit_id}).",
            fg=typer.colors.GREEN,
        )


@app.command("remove-member")
def remove_member(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    organizational_unit_id: int = typer.Argument(..., help="Organizational unit id"),
) -> None:
    """Remove a user, looked up by username or email, from an organizational unit."""
    asyncio.run(_remove_member(identifier, organizational_unit_id))


async def _remove_member(identifier: str, organizational_unit_id: int) -> None:
    """Resolve the user and unit, soft-delete the membership, and commit the change.

    Exits non-zero if the user or unit is missing; removing a non-member is a no-op.
    """
    async with session_scope() as session:
        user = (
            await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))
        ).first()
        if user is None or user.id is None:
            typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        try:
            unit = await get_organizational_unit(organizational_unit_id, session)
        except OrganizationalUnitNotFound:
            typer.secho(f"Organizational unit '{organizational_unit_id}' not found!", fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        await remove_organization_member(user.id, organizational_unit_id, session)
        await session.commit()
        typer.secho(
            f"Removed {user.username} from organizational unit '{unit.name}' ({organizational_unit_id}).",
            fg=typer.colors.GREEN,
        )
