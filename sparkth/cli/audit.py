"""Audit trail maintenance commands: retention purge and GDPR erasure (issue #507).
Neither has a scheduler of its own; run ``audit purge`` from cron (daily is plenty).
Authored with LLM (Claude) assistance."""

import asyncio

import typer

from sparkth.lib.audit import erase_actor, purge_expired_events

app = typer.Typer(help="Audit trail maintenance commands")


@app.command("purge")
def purge_command() -> None:
    """Delete audit events older than their category's retention window.

    Windows come from AUDIT_RETENTION_DAYS and AUDIT_RETENTION_OVERRIDES; each slice
    that loses rows leaves an audit.retention_purged event behind. Idempotent.
    """
    deleted = asyncio.run(purge_expired_events())
    if not deleted:
        typer.secho("Nothing past retention; no audit events deleted.", fg=typer.colors.YELLOW)
        return
    for category, rows in deleted.items():
        typer.secho(f"{category}: deleted {rows} event(s).", fg=typer.colors.GREEN)


@app.command("erase-user")
def erase_user_command(
    user_id: int = typer.Argument(..., help="Database id of the user whose personal data to erase"),
) -> None:
    """Blank the personal data (username label, IP, user agent) on a user's audit events.

    The events themselves, their sealed content, and the pseudonymous user id stay, so
    the trail keeps its shape and its integrity. Leaves an audit.actor_erased event.
    """
    rows = asyncio.run(erase_actor(user_id))
    typer.secho(f"Erased personal data on {rows} audit event(s) of user {user_id}.", fg=typer.colors.GREEN)
