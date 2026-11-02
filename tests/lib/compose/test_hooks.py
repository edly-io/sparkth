import gc
from collections.abc import Iterator

import pytest

from sparkth.lib.compose.exceptions import DuplicateAgentTitle
from sparkth.lib.compose.hooks import COMPOSE_AGENTS, Agent, enabled_agents, register_agent
from sparkth.lib.plugins import SparkthPlugin

STUB = Agent("Stub", "Stub description.", "Stub prompt")


@pytest.fixture
def stub_plugin() -> Iterator[SparkthPlugin]:
    """A plugin registering STUB; its weakly-keyed entry goes when the plugin is collected."""
    plugin = SparkthPlugin("stub")
    register_agent(plugin, STUB)
    yield plugin
    del plugin
    gc.collect()


def test_a_registered_agent_is_enabled(stub_plugin: SparkthPlugin) -> None:
    assert STUB in enabled_agents(set())


def test_a_agent_of_a_disabled_plugin_is_left_out(stub_plugin: SparkthPlugin) -> None:
    assert STUB not in enabled_agents({"stub"})


def test_a_plugin_constructed_twice_offers_its_agent_once(stub_plugin: SparkthPlugin) -> None:
    """The loader and tests both construct plugins, so the same agent arrives from two instances."""
    second = SparkthPlugin("stub")
    register_agent(second, STUB)

    assert enabled_agents(set()).count(STUB) == 1


def test_a_different_agent_under_a_registered_title_is_refused(stub_plugin: SparkthPlugin) -> None:
    other = SparkthPlugin("other")

    with pytest.raises(DuplicateAgentTitle):
        register_agent(other, Agent(STUB.title, "Other description.", "Other prompt"))

    assert all(owner is not other for owner, _ in COMPOSE_AGENTS.iter_items())


def test_agents_follow_plugin_name_order(stub_plugin: SparkthPlugin) -> None:
    """The composed prompt must not depend on which plugin was imported first."""
    early = SparkthPlugin("aaa-early")
    first = Agent("Early", "Early description.", "Early prompt")
    register_agent(early, first)

    agents = enabled_agents(set())

    assert agents.index(first) < agents.index(STUB)
