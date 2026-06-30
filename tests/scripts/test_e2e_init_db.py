"""Tests for scripts/e2e_init_db.py, the ephemeral E2E schema builder."""

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel

from scripts.e2e_init_db import init_schema


def _table_names(sync_conn: Connection) -> set[str]:
    return set(inspect(sync_conn).get_table_names())


async def _created_tables(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(_table_names)


async def test_init_schema_builds_the_whole_declared_schema(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'e2e.db'}")
    await init_schema(engine)
    created = await _created_tables(engine)
    # create_all must materialise every table the app declares (core models
    # plus every plugin's, registered by init_schema via get_plugin_loader).
    assert created == set(SQLModel.metadata.tables)
    assert created  # guard against a no-op / empty metadata
    await engine.dispose()


async def test_init_schema_is_idempotent(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'e2e.db'}")
    await init_schema(engine)
    await init_schema(engine)  # second run is a no-op, must not raise
    assert await _created_tables(engine)
    await engine.dispose()
