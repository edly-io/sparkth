import gc
from collections.abc import Iterator
from dataclasses import replace

import pytest

from sparkth.lib.compose.exceptions import (
    DuplicateAgentName,
    DuplicateAgentTool,
    InvalidAgentName,
    ReservedAgentName,
)
from sparkth.lib.compose.hooks import COMPOSE_AGENTS, Agent, enabled_agents, register_agent
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.plugins import SparkthPlugin

STUB = Agent("stub_hook", "Stub", "Stub description.", "Stub prompt")


async def stub_tool() -> str:
    """A tool the stub plugin owns."""
    return "ok"


def _tooled_agent() -> Agent:
    """An agent of the tooled plugin with its tool built afresh, as a plugin's ``__init__`` might."""
    return Agent("tooled", "Tooled", "Tooled description.", "Tooled prompt", tools=(Tool(stub_tool),))


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


@pytest.mark.parametrize("name", ["compose", "operator", "refuse"])
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


def test_an_agent_may_use_a_tool_its_plugin_also_gives_the_mcp_server(tooled_plugin: SparkthPlugin) -> None:
    shared = next(tool for owner, tool in MCP_TOOLS.iter_items() if owner is tooled_plugin)
    agent = Agent("tooled", "Tooled", "Tooled description.", "Tooled prompt", tools=(shared,))

    register_agent(tooled_plugin, agent)

    assert agent in enabled_agents(set())


def test_an_agent_may_use_a_tool_no_mcp_client_sees() -> None:
    plugin = SparkthPlugin("tooled")
    agent = _tooled_agent()

    register_agent(plugin, agent)

    assert agent in enabled_agents(set())
    assert all(tool.name != "stub_tool" for _owner, tool in MCP_TOOLS.iter_items())


def test_a_plugin_building_its_agents_tools_each_time_offers_its_agent_once() -> None:
    """A tool built twice is a different object, so agents compare without their tools."""
    first = SparkthPlugin("tooled")
    register_agent(first, _tooled_agent())
    second = SparkthPlugin("tooled")
    register_agent(second, _tooled_agent())

    assert [agent.name for agent in enabled_agents(set())].count("tooled") == 1


def test_an_agent_with_two_tools_of_one_name_is_refused() -> None:
    agent = replace(_tooled_agent(), tools=(Tool(stub_tool), Tool(stub_tool)))

    with pytest.raises(DuplicateAgentTool):
        register_agent(SparkthPlugin("tooled"), agent)


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
