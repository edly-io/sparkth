"""Which tools a turn is given: whatever the request asks for, from every plugin that is on and allowed."""

from unittest.mock import MagicMock

from sparkth.lib.testing import AuditEventsFetcher
from sparkth.plugins.compose.routes.utils import record_named_tool_denials, resolve_tools
from sparkth.plugins.compose.schemas import ChatCompletionRequest, ChatMessage


def _tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


_TOOLS = [_tool("openedx_create_xblock"), _tool("stub_build")]


def _registry() -> MagicMock:
    registry = MagicMock()
    registry.get_all_tools.return_value = _TOOLS
    registry.plugin_for.side_effect = {"openedx_create_xblock": "openedx", "stub_build": "stub"}.get
    registry.get_tools_by_names.side_effect = lambda names: [tool for tool in _TOOLS if tool.name in names]
    return registry


def _request(tools: str | list[str]) -> ChatCompletionRequest:
    return ChatCompletionRequest(llm_config_id=1, messages=[ChatMessage(role="user", content="hi")], tools=tools)


async def test_a_wildcard_binds_every_plugins_tools() -> None:
    tools = await resolve_tools(_request("*"), _registry(), set(), None)

    assert [tool.name for tool in tools or []] == ["openedx_create_xblock", "stub_build"]


async def test_named_tools_are_bound_by_name() -> None:
    tools = await resolve_tools(_request(["stub_build"]), _registry(), set(), None)

    assert [tool.name for tool in tools or []] == ["stub_build"]


async def test_disabled_tools_stay_disabled() -> None:
    assert await resolve_tools(_request("none"), _registry(), set(), None) is None
    assert await resolve_tools(_request([]), _registry(), set(), None) is None


async def test_a_wildcard_drops_the_tools_of_a_disabled_plugin() -> None:
    tools = await resolve_tools(_request("*"), _registry(), {"stub"}, None)

    assert [tool.name for tool in tools or []] == ["openedx_create_xblock"]


async def test_a_named_tool_of_a_disabled_plugin_is_dropped() -> None:
    tools = await resolve_tools(_request(["stub_build", "openedx_create_xblock"]), _registry(), {"stub"}, None)

    assert [tool.name for tool in tools or []] == ["openedx_create_xblock"]


async def test_a_wildcard_drops_the_tools_of_a_plugin_that_is_not_allowed() -> None:
    tools = await resolve_tools(_request("*"), _registry(), set(), {"openedx"})

    assert [tool.name for tool in tools or []] == ["openedx_create_xblock"]


async def test_a_named_tool_of_a_plugin_that_is_not_allowed_is_dropped() -> None:
    tools = await resolve_tools(_request(["stub_build", "openedx_create_xblock"]), _registry(), set(), {"openedx"})

    assert [tool.name for tool in tools or []] == ["openedx_create_xblock"]


async def test_an_allowed_plugin_that_is_disabled_keeps_none_of_its_tools() -> None:
    tools = await resolve_tools(_request("*"), _registry(), {"stub"}, {"stub", "openedx"})

    assert [tool.name for tool in tools or []] == ["openedx_create_xblock"]


async def test_two_named_tools_of_one_plugin_record_one_denial(audit_events: AuditEventsFetcher) -> None:
    registry = _registry()
    registry.plugin_for.side_effect = {"stub_build": "stub", "stub_run": "stub"}.get

    await record_named_tool_denials(_request(["stub_build", "stub_run"]), registry, set(), {"openedx"})

    assert [event.error_detail for event in await audit_events()] == ["scope=plugin:stub"]


async def test_a_named_tool_no_plugin_gave_records_no_denial(audit_events: AuditEventsFetcher) -> None:
    await record_named_tool_denials(_request(["unknown_tool"]), _registry(), set(), {"openedx"})

    assert await audit_events() == []
