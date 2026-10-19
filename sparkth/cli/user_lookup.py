"""Resolve the user a CLI command names by username or email.
Authored with LLM (Claude) assistance."""

import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User


async def resolve_user(identifier: str, session: AsyncSession) -> tuple[int, User]:
    """Return ``(id, user)`` for the user whose username or email equals ``identifier``, or exit non-zero."""
    user = (await session.exec(select(User).where((User.username == identifier) | (User.email == identifier)))).first()
    if user is None or user.id is None:
        typer.secho(f"User '{identifier}' not found!", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    return user.id, user
