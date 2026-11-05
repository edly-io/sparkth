"""How an agent's tools are categorised in analytics."""

from dataclasses import replace

from sparkth.lib.mcp.hooks import Tool
from sparkth.plugins.compose.constants import UNKNOWN_TOOL_CATEGORY
from sparkth.plugins.compose.tests.conftest import STUB_AGENT, registered_agent
from sparkth.plugins.compose.tools import tool_category


async def stub_build() -> str:
    """Build it."""
    return "built"


class TestToolCategory:
    def test_an_agents_tool_is_in_the_category_it_was_built_with(self) -> None:
        with registered_agent("stub", replace(STUB_AGENT, tools=(Tool(stub_build, "building"),))):
            assert tool_category("stub_build") == "building"

    def test_an_agents_tool_without_a_category_is_in_the_agents(self) -> None:
        with registered_agent("stub", replace(STUB_AGENT, tools=(Tool(stub_build),))):
            assert tool_category("stub_build") == STUB_AGENT.name

    def test_a_tool_nothing_contributed_is_in_the_unknown_category(self) -> None:
        assert tool_category("never_registered") == UNKNOWN_TOOL_CATEGORY
