"""Fixtures shared by the chat plugin's tests."""

import gc
from collections.abc import AsyncIterator, Iterator

import pytest

from sparkth.lib.chat.hooks import CHAT_RESPONSIBILITIES, ChatResponsibility
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.chat.detached import join_live_tasks

STUB_JOB = ChatResponsibility("stub-job", "Stub scope text.", "STUB SYSTEM PROMPT", frozenset({"stub-tools"}))


@pytest.fixture(autouse=True)
async def drain_detached_emits() -> AsyncIterator[None]:
    """Join the detached tasks a request leaves running, before the engine goes.

    Otherwise one can still be writing when the fixtures tear the database down, surfacing as
    an error in whatever test runs next. Autouse: any test driving a turn can leak one.
    """
    yield
    await join_live_tasks()


@pytest.fixture
def stub_job() -> Iterator[ChatResponsibility]:
    """A second enabled job beside course-design, gone when its plugin is collected."""
    plugin = SparkthPlugin("stub")
    CHAT_RESPONSIBILITIES.add_item(plugin, STUB_JOB)
    yield STUB_JOB
    del plugin
    gc.collect()
