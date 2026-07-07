"""Build the full application schema on the configured database.

The local Playwright E2E suite runs against an ephemeral SQLite database that
cannot be migrated (the RAG migration needs pgvector, and others need Postgres
enum types), so the schema is created with SQLModel.metadata.create_all, the
same way the unit-test suite builds its schema.

Metadata is populated exactly as app/migrations/env.py does it: `from sparkth.core.models
import *` registers the core tables and get_plugin_loader() registers the plugin
tables, so SQLModel.metadata is complete before create_all runs.
"""

import asyncio

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import SQLModel

from sparkth.core.db import dispose_engine, get_engine
from sparkth.core.models import *  # noqa: F403
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import get_plugin_loader

logger = get_logger(__name__)


async def init_schema(engine: AsyncEngine) -> None:
    """Create every application table on `engine`. Idempotent."""
    get_plugin_loader()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    except SQLAlchemyError:
        logger.exception("Failed to create the E2E schema")
        raise
    logger.info("E2E schema ready (%d tables)", len(SQLModel.metadata.tables))


def main() -> None:
    async def _run() -> None:
        try:
            await init_schema(get_engine())
        finally:
            # Dispose so aiosqlite's connection worker thread exits; otherwise the
            # process hangs at interpreter shutdown waiting to join it.
            await dispose_engine()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
