"""Which of a turn's tools each agent runs with."""

from langchain_core.tools import BaseTool, StructuredTool

from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.tools import agent_tools


async def _done() -> str:
    return "done"


def _tool(name: str) -> BaseTool:
    return StructuredTool.from_function(coroutine=_done, name=name, description=f"{name} it.")


ENABLED = [_tool(name) for name in ("stub_build", "canvas_create_course", "openedx_create_xblock")]


class TestOwnTools:
    def test_an_agent_runs_with_its_agent_tools_only(self) -> None:
        agent = Agent("stub", "Stub", "Stub scope.", "Stub prompt.", tools=("stub_build",))

        assert [tool.name for tool in agent_tools(agent, ENABLED)] == ["stub_build"]

    def test_a_named_tool_the_turn_did_not_enable_is_left_out(self) -> None:
        agent = Agent("stub", "Stub", "Stub scope.", "Stub prompt.", tools=("stub_build",))

        assert agent_tools(agent, []) == []

    def test_an_agents_langchain_tools_run_whatever_the_request_enables(self) -> None:
        private = _tool("stub_private")
        agent = Agent("stub", "Stub", "Stub scope.", "Stub prompt.", langchain_tools=(private,))

        assert agent_tools(agent, []) == [private]
