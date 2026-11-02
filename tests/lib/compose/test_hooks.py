import gc
from collections.abc import Iterator

import pytest

from sparkth.lib.compose.exceptions import (
    DuplicateAgentName,
    InvalidAgentName,
    ReservedAgentName,
    UnknownAgentTool,
)
from sparkth.lib.compose.hooks import COMPOSE_AGENTS, Agent, enabled_agents, register_agent
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.plugins import SparkthPlugin

STUB = Agent("stub_hook", "Stub", "Stub description.", "Stub prompt")


async def stub_tool() -> str:
    """A tool the stub plugin owns."""
    return "ok"


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


def test_an_agent_of_a_disabled_plugin_is_left_out(stub_plugin: SparkthPlugin) -> None:
    assert STUB not in enabled_agents({"stub"})


def test_a_plugin_constructed_twice_offers_its_agent_once(stub_plugin: SparkthPlugin) -> None:
    """The loader and tests both construct plugins, so the same agent arrives from two instances."""
    second = SparkthPlugin("stub")
    register_agent(second, STUB)

    assert enabled_agents(set()).count(STUB) == 1


def test_a_different_agent_under_a_registered_name_is_refused(stub_plugin: SparkthPlugin) -> None:
    other = SparkthPlugin("other")

    with pytest.raises(DuplicateAgentName):
        register_agent(other, Agent(STUB.name, "Other", "Other description.", "Other prompt"))

    assert all(owner is not other for owner, _ in COMPOSE_AGENTS.iter_items())


def test_the_same_agent_from_another_plugin_is_refused(stub_plugin: SparkthPlugin) -> None:
    with pytest.raises(DuplicateAgentName):
        register_agent(SparkthPlugin("other"), STUB)


@pytest.mark.parametrize("name", ["compose", "operator"])
def test_a_reserved_name_is_refused(name: str) -> None:
    with pytest.raises(ReservedAgentName):
        register_agent(SparkthPlugin("other"), Agent(name, "Other", "Other description.", "Other prompt"))


@pytest.mark.parametrize("name", ["Stub", "1stub", "stub-agent", "stub agent", ""])
def test_a_name_that_cannot_be_a_tool_name_is_refused(name: str) -> None:
    with pytest.raises(InvalidAgentName):
        register_agent(SparkthPlugin("other"), Agent(name, "Other", "Other description.", "Other prompt"))


@pytest.fixture
def tooled_plugin() -> Iterator[SparkthPlugin]:
    """A plugin owning stub_tool; its entries go when the plugin is collected."""
    plugin = SparkthPlugin("tooled")
    MCP_TOOLS.add_item(plugin, Tool(stub_tool))
    yield plugin
    del plugin
    gc.collect()


def test_an_agent_may_use_its_own_plugins_tools(tooled_plugin: SparkthPlugin) -> None:
    agent = Agent("tooled", "Tooled", "Tooled description.", "Tooled prompt", tools=("stub_tool",))

    register_agent(tooled_plugin, agent)

    assert agent in enabled_agents(set())


def test_an_agent_may_not_use_another_plugins_tools(tooled_plugin: SparkthPlugin) -> None:
    with pytest.raises(UnknownAgentTool):
        register_agent(
            SparkthPlugin("other"),
            Agent("other", "Other", "Other description.", "Other prompt", tools=("stub_tool",)),
        )


def test_an_agent_named_like_a_registered_tool_is_refused(tooled_plugin: SparkthPlugin) -> None:
    with pytest.raises(DuplicateAgentName):
        register_agent(tooled_plugin, Agent("stub_tool", "Other", "Other description.", "Other prompt"))


def test_agents_follow_plugin_name_order(stub_plugin: SparkthPlugin) -> None:
    """The composed prompt must not depend on which plugin was imported first."""
    early = SparkthPlugin("aaa-early")
    first = Agent("early", "Early", "Early description.", "Early prompt")
    register_agent(early, first)

    agents = enabled_agents(set())

    assert agents.index(first) < agents.index(STUB)
