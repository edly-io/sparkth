"""Contract tests for emit_event — the producer-facing analytics writer.

emit_event exists to own one thing: acquiring an analytics session so producers
need no session plumbing. It deliberately catches nothing, so each case below
pins down which failure reaches the caller unchanged. The happy path proves it
still actually writes.
"""

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics.models import raw_events
from sparkth.lib.analytics import UnknownEventTypeError, emit_event


async def test_emits_a_row_for_a_registered_event(analytics_session: AsyncSession) -> None:
    await emit_event("user.logged_in", 1, {"username": "instructor"}, actor_id="7")

    row = (await analytics_session.execute(select(raw_events))).mappings().one()
    assert row["event_type"] == "user.logged_in"
    assert row["event_version"] == 1
    assert row["actor_id"] == "7"
    assert row["payload"] == {"username": "instructor"}


async def test_unknown_event_type_propagates(analytics_session: AsyncSession) -> None:
    with pytest.raises(UnknownEventTypeError):
        await emit_event("never.registered", 1, {})

    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    assert rows == []


async def test_invalid_payload_propagates(analytics_session: AsyncSession) -> None:
    # user.logged_in requires `username`; extra="forbid" also rejects unknown keys.
    with pytest.raises(ValidationError):
        await emit_event("user.logged_in", 1, {"wrong_field": "x"})

    rows = (await analytics_session.execute(select(raw_events))).mappings().all()
    assert rows == []


@pytest.mark.parametrize(
    "error",
    [SQLAlchemyError("insert failed"), RuntimeError("something unexpected")],
    ids=["sqlalchemy_error", "unexpected_error"],
)
async def test_gateway_failures_propagate(error: Exception) -> None:
    with (
        patch("sparkth.lib.analytics.ingest_event", side_effect=error),
        pytest.raises(type(error)),
    ):
        await emit_event("user.logged_in", 1, {"username": "instructor"})


async def test_session_acquisition_failure_propagates() -> None:
    """A dead analytics database reaches the caller rather than being hidden."""

    @asynccontextmanager
    async def _failing_scope(*args: Any, **kwargs: Any) -> Any:
        raise SQLAlchemyError("analytics database unreachable")
        yield  # pragma: no cover -- unreachable, makes this a generator

    with (
        patch("sparkth.lib.analytics.analytics_session_scope", _failing_scope),
        pytest.raises(SQLAlchemyError),
    ):
        await emit_event("user.logged_in", 1, {"username": "instructor"})
