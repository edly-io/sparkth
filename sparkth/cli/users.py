import asyncio

import typer
from sqlmodel import select

from sparkth.cli.audit_context import cli_audit_context
from sparkth.cli.user_lookup import resolve_user
from sparkth.core.models.base import utc_now
from sparkth.core.models.user import User
from sparkth.core.security import get_password_hash
from sparkth.lib.audit import record_event
from sparkth.lib.audit.events import (
    AuditChange,
    AuditOutcome,
    AuditTarget,
    PasswordResetAuditEvent,
    RegisteredAuditEvent,
)
from sparkth.lib.db import session_scope

app = typer.Typer(help="User management commands")


def _create_audit_snapshot() -> dict[str, str]:
    return {"method": "cli"}


def _cli_change(user: User) -> tuple[AuditTarget, AuditChange]:
    return AuditTarget(type="user", id=str(user.id)), AuditChange(new=_create_audit_snapshot())


@app.command()
def create_user(
    username: str = typer.Option(..., "--username", "-u", prompt=True),
    email: str = typer.Option(..., "--email", "-e", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, confirmation_prompt=True),
    name: str | None = typer.Option(None, "--name", "-n"),
    email_verified: bool = typer.Option(False, "--email-verified", is_flag=True),
) -> None:
    asyncio.run(_create_user(username, email, password, name, email_verified))


async def _create_user(
    username: str,
    email: str,
    password: str,
    name: str | None,
    email_verified: bool,
) -> None:
    """Create a user, recording ``auth.registered`` (method ``cli``) in the same transaction."""
    with cli_audit_context():
        await _create_user_in_session(username, email, password, name, email_verified)


async def _create_user_in_session(
    username: str,
    email: str,
    password: str,
    name: str | None,
    email_verified: bool,
) -> None:
    async with session_scope() as session:
        existing = (await session.exec(select(User).where((User.username == username) | (User.email == email)))).first()
        if existing:
            typer.secho(
                f"User with username '{username}' or email '{email}' already exists!",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            name=name or username,
            email_verified=email_verified,
            email_verified_at=utc_now() if email_verified else None,
        )
        session.add(user)
        # Flush to assign user.id, which the audit target needs.
        await session.flush()

        target, change = _cli_change(user)
        await record_event(session, RegisteredAuditEvent(outcome=AuditOutcome.SUCCESS, target=target, change=change))
        await session.commit()
        await session.refresh(user)

        typer.secho("User created successfully!", fg=typer.colors.GREEN)
        typer.echo(f"ID: {user.id}")
        typer.echo(f"UUID: {user.uuid}")
        typer.echo(f"Username: {user.username}")
        typer.echo(f"Email: {user.email}")


@app.command()
def reset_password(
    identifier: str = typer.Argument(..., help="Username or email of the user"),
    new_password: str = typer.Option(
        ...,
        "--new-password",
        "-p",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    ),
) -> None:
    asyncio.run(_reset_password(identifier, new_password))


async def _reset_password(identifier: str, new_password: str) -> None:
    """Replace a user's password, recording ``auth.password_reset`` in the same transaction."""
    with cli_audit_context():
        await _reset_password_in_session(identifier, new_password)


async def _reset_password_in_session(identifier: str, new_password: str) -> None:
    async with session_scope() as session:
        _, user = await resolve_user(identifier, session)

        if user.is_deleted:
            typer.secho(
                "This user is soft-deleted. Restore first if needed.",
                fg=typer.colors.YELLOW,
            )

        user.hashed_password = get_password_hash(new_password)
        user.update_timestamp()
        session.add(user)
        target, change = _cli_change(user)
        await record_event(session, PasswordResetAuditEvent(outcome=AuditOutcome.SUCCESS, target=target, change=change))
        await session.commit()

        typer.secho(
            f"Password reset successfully for user: {user.username}",
            fg=typer.colors.GREEN,
        )
