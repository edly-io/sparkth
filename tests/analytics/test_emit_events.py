"""Contract tests for emit_events — the batching counterpart to emit_event.

emit_events exists for one reason: a producer with a variable number of related
events (a chat completion and one event per tool it executed, say) should not pay
a session acquisition per event, nor land half a group. These tests pin the session
count, the ordering, and the all-or-nothing guarantee — the last of which is what a
consumer relies on when it assumes a completion never appears without the tool
events belonging to it.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.analytics import PendingEvent, UnknownEventTypeError, emit_events
from sparkth.lib.db import analytics_session_scope


def _login(username: str) -> PendingEvent:
    """A valid event of the one type core registers, so these tests need no plugin."""
    return PendingEvent(event_type="user.logged_in", version=1, payload={"username": username}, actor_id="7")


async def _landed(analytics_session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    return [dict(row) for row in rows]


async def test_lands_every_event_in_order(analytics_session: AsyncSession) -> None:
    await emit_events([_login("first"), _login("second"), _login("third")])

    assert [row["payload"]["username"] for row in await _landed(analytics_session)] == [
        "first",
        "second",
        "third",
    ]


async def test_uses_one_session_for_the_whole_group(analytics_session: AsyncSession) -> None:
    """The reason this function exists: N events, one session — not N.

    Asserted on the session scope rather than on timing, so the guarantee holds
    whatever the analytics database is.
    """
    real_scope = analytics_session_scope
    opened = 0

    @asynccontextmanager
    async def counting_scope(*args: Any, **kwargs: Any) -> AsyncGenerator[AsyncSession, None]:
        nonlocal opened
        opened += 1
        async with real_scope(*args, **kwargs) as session:
            yield session

    with patch("sparkth.lib.analytics.analytics_session_scope", counting_scope):
        await emit_events([_login("a"), _login("b"), _login("c"), _login("d")])

    assert opened == 1
    assert len(await _landed(analytics_session)) == 4


async def test_an_empty_group_opens_no_session(analytics_session: AsyncSession) -> None:
    """A completion that ran no tools still calls this; it must not cost a connection."""
    with patch("sparkth.lib.analytics.analytics_session_scope") as scope:
        await emit_events([])

    scope.assert_not_called()
    assert await _landed(analytics_session) == []


async def test_unknown_event_type_propagates(analytics_session: AsyncSession) -> None:
    with pytest.raises(UnknownEventTypeError):
        await emit_events([PendingEvent(event_type="never.registered", version=1, payload={})])

    assert await _landed(analytics_session) == []


async def test_invalid_payload_propagates(analytics_session: AsyncSession) -> None:
    # user.logged_in requires `username`; extra="forbid" also rejects unknown keys.
    with pytest.raises(ValidationError):
        await emit_events([PendingEvent(event_type="user.logged_in", version=1, payload={"wrong_field": "x"})])

    assert await _landed(analytics_session) == []


async def test_a_failure_part_way_lands_nothing(analytics_session: AsyncSession) -> None:
    """The group is one transaction, so a bad event anywhere in it rolls back the rest.

    This is the guarantee consumers lean on: a chat completion never lands without
    the tool events that belong to it, and never the other way round.
    """
    with pytest.raises(ValidationError):
        await emit_events(
            [
                _login("first"),
                PendingEvent(event_type="user.logged_in", version=1, payload={"wrong_field": "x"}),
                _login("never reached"),
            ]
        )

    assert await _landed(analytics_session) == []
