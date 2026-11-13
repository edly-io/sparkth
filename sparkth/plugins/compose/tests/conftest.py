"""Fixtures shared by the Compose plugin's tests."""

import gc
from collections.abc import AsyncIterator, Iterator

import pytest

from sparkth.core.permissions.models import Role
from sparkth.lib.compose.hooks import Agent, register_agent
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.compose.detached import join_live_tasks

STUB_AGENT = Agent("stub", "Stub agent", "Stub scope text.", "STUB SECTION")
OTHER_AGENT = Agent("other", "Other agent", "Other scope text.", "OTHER SECTION")


@pytest.fixture(autouse=True)
def _every_user_holds_default_role(default_user_role: Role) -> None:  # noqa: PT004
    """Give the signed-in test user the default role, so the gated routes pass for their own records."""


@pytest.fixture(autouse=True)
async def drain_detached_emits() -> AsyncIterator[None]:
    """Join the detached tasks a request leaves running, before the engine goes.

    Otherwise one can still be writing when the fixtures tear the database down, surfacing as
    an error in whatever test runs next. Autouse: any test driving a turn can leak one.
    """
    yield
    await join_live_tasks()


def registered_agent(plugin_name: str, agent: Agent) -> Iterator[Agent]:
    """Register ``agent`` on a throwaway plugin; the entry goes when the plugin is collected."""
    plugin = SparkthPlugin(plugin_name)
    register_agent(plugin, agent)
    yield agent
    del plugin
    gc.collect()


@pytest.fixture
def stub_agent() -> Iterator[Agent]:
    """An enabled agent, gone when its plugin is collected."""
    yield from registered_agent("stub", STUB_AGENT)


@pytest.fixture
def other_agent() -> Iterator[Agent]:
    """An enabled agent of a second plugin, gone when its plugin is collected."""
    yield from registered_agent("other", OTHER_AGENT)
