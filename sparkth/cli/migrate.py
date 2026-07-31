"""One-shot database migration command.

Applies both Alembic lineages (app and analytics) and then backfills TimescaleDB
continuous aggregates, so a single command brings any environment's databases up to
date. Used natively via `make migrations` and inside the production compose stack
(see the "Production" section of README.md).
"""

import asyncio

import typer
from alembic import command
from alembic.config import Config

from sparkth.lib.analytics import backfill_continuous_aggregates


def migrate_command() -> None:
    """Apply all pending migrations and backfill continuous aggregates.

    Runs `alembic upgrade head` for the app database, then for the analytics
    database, then a full refresh of every registered TimescaleDB continuous
    aggregate (idempotent; a no-op on a non-PostgreSQL analytics database).
    Alembic config paths are resolved relative to the working directory, so run
    from the repository root (or /app inside the container).
    """
    typer.secho("Applying app database migrations...", fg=typer.colors.CYAN)
    command.upgrade(Config("alembic.ini"), "head")
    typer.secho("Applying analytics database migrations...", fg=typer.colors.CYAN)
    command.upgrade(Config("alembic_analytics.ini"), "head")

    refreshed = asyncio.run(backfill_continuous_aggregates())
    if refreshed is None:
        typer.secho(
            "Skipped aggregate backfill: analytics database is not PostgreSQL/TimescaleDB.",
            fg=typer.colors.YELLOW,
        )
    elif not refreshed:
        typer.secho("No continuous aggregates registered; nothing to backfill.", fg=typer.colors.YELLOW)
    else:
        typer.secho(f"Backfilled {len(refreshed)} aggregate(s): {', '.join(refreshed)}.", fg=typer.colors.GREEN)
