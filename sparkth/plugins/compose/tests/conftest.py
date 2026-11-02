"""Fixtures shared by the Compose plugin's tests."""

import gc
from collections.abc import AsyncIterator, Iterator

import pytest

from sparkth.lib.compose.hooks import Agent, register_agent
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.compose.detached import join_live_tasks

STUB_AGENT = Agent("stub", "Stub agent", "Stub scope text.", "STUB SECTION")


@pytest.fixture(autouse=True)
async def drain_detached_emits() -> AsyncIterator[None]:
    """Join the detached tasks a request leaves running, before the engine goes.

    Otherwise one can still be writing when the fixtures tear the database down, surfacing as
    an error in whatever test runs next. Autouse: any test driving a turn can leak one.
    """
    yield
    await join_live_tasks()


@pytest.fixture
def stub_agent() -> Iterator[Agent]:
    """A second enabled agent beside course design, gone when its plugin is collected."""
    plugin = SparkthPlugin("stub")
    register_agent(plugin, STUB_AGENT)
    yield STUB_AGENT
    del plugin
    gc.collect()
