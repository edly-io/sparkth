"""Fixtures shared by the chat plugin's tests."""

from collections.abc import AsyncIterator

import pytest

from sparkth.plugins.chat.detached import join_live_tasks


@pytest.fixture(autouse=True)
async def drain_detached_emits() -> AsyncIterator[None]:
    """Join the detached tasks a request leaves running, before the engine goes.

    Otherwise one can still be writing when the fixtures tear the database down, surfacing as
    an error in whatever test runs next. Autouse: any test driving a turn can leak one.
    """
    yield
    await join_live_tasks()
