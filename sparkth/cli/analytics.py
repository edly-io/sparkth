import asyncio

import typer

from sparkth.lib.analytics import ContinuousAggregateNotFound, backfill_continuous_aggregates

app = typer.Typer(help="Analytics maintenance commands")


@app.command("backfill-aggregates")
def backfill_aggregates_command(
    name: str | None = typer.Option(
        None,
        "--name",
        help="Refresh only this continuous aggregate (default: refresh all).",
    ),
) -> None:
    """Backfill the full history of TimescaleDB continuous aggregates.

    Run once after an aggregate's migration is applied on PostgreSQL/TimescaleDB:
    aggregates are created empty and their refresh policies only cover a trailing window,
    so without this one-off full refresh any pre-migration history is lost. Idempotent.
    On a non-PostgreSQL analytics database (SQLite in tests/e2e) it is a no-op.
    """
    try:
        refreshed = asyncio.run(backfill_continuous_aggregates(name))
    except ContinuousAggregateNotFound as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from None

    if refreshed is None:
        typer.secho(
            "Skipped: analytics database is not PostgreSQL/TimescaleDB; nothing to refresh.",
            fg=typer.colors.YELLOW,
        )
    elif not refreshed:
        typer.secho("No continuous aggregates registered; nothing to refresh.", fg=typer.colors.YELLOW)
    else:
        typer.secho(f"Refreshed {len(refreshed)} aggregate(s): {', '.join(refreshed)}.", fg=typer.colors.GREEN)
