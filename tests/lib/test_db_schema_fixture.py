"""The ``_db_schema`` fixture in sparkth.lib.testing, which gives each test its database schema."""

import asyncio
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select

import sparkth.lib.testing as testing
from sparkth.core.analytics.db import get_analytics_engine
from sparkth.lib.db import analytics_session_scope, session_scope


def _creates_of(engine: AsyncEngine, table: str) -> list[str]:
    """Every statement ``engine`` runs from here on that creates ``table``."""
    creates: list[str] = []

    def record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if f"CREATE TABLE {table} " in statement:
            creates.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    return creates


async def _query_in_a_session() -> None:
    async with session_scope() as session:
        await session.exec(select(1))


async def _query_in_an_analytics_session() -> None:
    async with analytics_session_scope() as session:
        await session.execute(text("SELECT 1"))


async def test_sessions_opened_at_once_load_the_schema_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two sessions opened together load the schema once."""
    real_image = testing._get_schema_image
    loads: list[bytes] = []

    def counting_image() -> bytes:
        loads.append(real_image())
        return loads[-1]

    monkeypatch.setattr(testing, "_get_schema_image", counting_image)

    await asyncio.gather(_query_in_a_session(), _query_in_a_session())

    assert len(loads) == 1


async def test_analytics_sessions_opened_at_once_create_the_schema_once() -> None:
    """Two analytics sessions opened together create the schema once."""
    creates = _creates_of(get_analytics_engine(), "raw_events")

    await asyncio.gather(_query_in_an_analytics_session(), _query_in_an_analytics_session())

    assert len(creates) == 1
