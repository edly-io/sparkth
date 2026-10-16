"""Resolve the user a CLI command names by username or email.
Authored with LLM (Claude) assistance."""

import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User


async def resolve_user(identifier: str, session: AsyncSession) -> User:
    """Return the user whose username or email equals ``identifier``.

    Exits non-zero when no user matches, or when ``identifier`` is one user's username and
    another user's email, so a command never acts on whichever row the database returns first.
    """
    users = (await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))).all()
    if not users:
        typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if len(users) > 1:
        typer.secho(
            f"'{identifier}' matches more than one user (one's username, another's email); use their other identifier.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    return users[0]
