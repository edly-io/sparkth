from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkth.plugins.chat.constants import LMS_RULES
from sparkth.plugins.chat.lms_credentials import (
    _has_lms_tools,
    _lms_tool_prefixes,
    build_lms_credentials_message,
)
from sparkth.plugins.chat.tests.helpers import CANVAS_CONFIG, OPENEDX_CONFIG


def _make_tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _make_user_plugin(config: dict[str, Any]) -> MagicMock:
    up = MagicMock()
    up.config = config
    return up


class TestHasLmsTools:
    def test_empty_list_returns_false(self) -> None:
        assert _has_lms_tools([], _lms_tool_prefixes()) is False

    def test_non_lms_tools_return_false(self) -> None:
        tools = [_make_tool("google_drive_list"), _make_tool("chat_respond")]
        assert _has_lms_tools(tools, _lms_tool_prefixes()) is False

    def test_openedx_tool_returns_true(self) -> None:
        assert _has_lms_tools([_make_tool("openedx_authenticate")], _lms_tool_prefixes()) is True

    def test_canvas_tool_returns_true(self) -> None:
        assert _has_lms_tools([_make_tool("canvas_get_courses")], _lms_tool_prefixes()) is True

    def test_mixed_tools_returns_true(self) -> None:
        tools = [_make_tool("some_other_tool"), _make_tool("openedx_create_course_run")]
        assert _has_lms_tools(tools, _lms_tool_prefixes()) is True


_OPENEDX_PLUGIN_MAP = {"open-edx": _make_user_plugin(OPENEDX_CONFIG)}

_CANVAS_PLUGIN_MAP = {"canvas": _make_user_plugin(CANVAS_CONFIG)}

_BOTH_PLUGIN_MAP = {**_OPENEDX_PLUGIN_MAP, **_CANVAS_PLUGIN_MAP}


class TestBuildLmsCredentialsMessage:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    async def test_returns_none_when_tools_is_none(self, mock_session: AsyncMock) -> None:
        result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=None)
        assert result is None

    async def test_returns_none_when_tools_is_empty(self, mock_session: AsyncMock) -> None:
        result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=[])
        assert result is None

    async def test_returns_none_when_no_lms_tools(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("google_drive_list")]
        result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is None

    async def test_returns_hint_when_no_plugins_configured(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("openedx_authenticate")]
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value={}),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == LMS_RULES
        assert "My Plugins" in result

    async def test_openedx_credentials_included(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("openedx_authenticate")]
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_OPENEDX_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is not None
        assert "https://lms.example.com" in result
        assert "https://studio.example.com" in result
        assert "admin" in result
        assert "secret" in result

    async def test_canvas_settings_never_reach_the_message(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("canvas_get_courses")]
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_CANVAS_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is not None
        assert "token-abc123" not in result
        assert "https://canvas.example.com" not in result

    async def test_both_lms_credentials_included(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("openedx_create_course_run"), _make_tool("canvas_create_course")]
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_BOTH_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is not None
        assert "https://lms.example.com" in result

    async def test_rule_5_absent_when_no_credentials(self, mock_session: AsyncMock) -> None:
        """Rule 5 (use credentials automatically) must not appear when no credentials are configured."""
        tools = [_make_tool("openedx_authenticate")]
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value={}),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == LMS_RULES
        assert "5." not in result

    async def test_rule_5_present_when_credentials_configured(self, mock_session: AsyncMock) -> None:
        """Rule 5 must appear and credentials must follow it when configured."""
        tools = [_make_tool("openedx_authenticate")]
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_OPENEDX_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is not None
        assert "5." in result
        assert "https://lms.example.com" in result

    async def test_invalid_config_falls_back_to_hint(self, mock_session: AsyncMock) -> None:
        """A corrupt/incomplete stored config should not crash — returns the unconfigured hint."""
        tools = [_make_tool("openedx_authenticate")]
        plugin_map = {"open-edx": _make_user_plugin({"lms_url": "not-a-url"})}
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=plugin_map),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == LMS_RULES

    async def test_empty_config_falls_back_to_hint(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("openedx_authenticate")]
        plugin_map = {"open-edx": _make_user_plugin({})}
        with patch(
            "sparkth.lib.plugins.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=plugin_map),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == LMS_RULES

    async def test_credentials_of_an_lms_with_no_bound_tool_are_omitted(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("canvas_create_course")]
        with patch(
            "sparkth.plugins.chat.lms_credentials.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_BOTH_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(mock_session, 1, tools)

        assert result is not None
        assert "https://lms.example.com" not in result

    async def test_no_message_when_only_non_lms_tools_remain(self, mock_session: AsyncMock) -> None:
        result = await build_lms_credentials_message(mock_session, 1, [_make_tool("stub_build")])

        assert result is None
