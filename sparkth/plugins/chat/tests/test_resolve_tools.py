"""Which tools a turn is given: whatever the request asks for, from every plugin."""

from unittest.mock import MagicMock

from sparkth.plugins.chat.routes.utils import resolve_tools
from sparkth.plugins.chat.schemas import ChatCompletionRequest, ChatMessage


def _tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


_TOOLS = [_tool("openedx_create_xblock"), _tool("stub_build")]


def _registry() -> MagicMock:
    registry = MagicMock()
    registry.get_all_tools.return_value = _TOOLS
    registry.get_tools_by_names.side_effect = lambda names: [tool for tool in _TOOLS if tool.name in names]
    return registry


def _request(tools: str | list[str]) -> ChatCompletionRequest:
    return ChatCompletionRequest(llm_config_id=1, messages=[ChatMessage(role="user", content="hi")], tools=tools)


async def test_a_wildcard_binds_every_plugins_tools() -> None:
    tools = await resolve_tools(_request("*"), _registry())

    assert [tool.name for tool in tools or []] == ["openedx_create_xblock", "stub_build"]


async def test_named_tools_are_bound_by_name() -> None:
    tools = await resolve_tools(_request(["stub_build"]), _registry())

    assert [tool.name for tool in tools or []] == ["stub_build"]


async def test_disabled_tools_stay_disabled() -> None:
    assert await resolve_tools(_request("none"), _registry()) is None
    assert await resolve_tools(_request([]), _registry()) is None
