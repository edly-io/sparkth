from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core_plugins.chat.lms_credentials import (
    _LMS_RULES,
    _has_lms_tools,
    build_lms_credentials_message,
)


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
        assert _has_lms_tools([]) is False

    def test_non_lms_tools_return_false(self) -> None:
        tools = [_make_tool("google_drive_list"), _make_tool("chat_respond")]
        assert _has_lms_tools(tools) is False

    def test_openedx_tool_returns_true(self) -> None:
        assert _has_lms_tools([_make_tool("openedx_authenticate")]) is True

    def test_canvas_tool_returns_true(self) -> None:
        assert _has_lms_tools([_make_tool("canvas_get_courses")]) is True

    def test_mixed_tools_returns_true(self) -> None:
        tools = [_make_tool("some_other_tool"), _make_tool("openedx_create_course_run")]
        assert _has_lms_tools(tools) is True


_OPENEDX_PLUGIN_MAP = {
    "open-edx": _make_user_plugin(
        {
            "lms_url": "https://lms.example.com",
            "studio_url": "https://studio.example.com",
            "lms_username": "admin",
            "lms_password": "secret",
        }
    )
}

_CANVAS_PLUGIN_MAP = {
    "canvas": _make_user_plugin(
        {
            "api_url": "https://canvas.example.com",
            "api_key": "token-abc123",
        }
    )
}

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
            "app.services.plugin.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value={}),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == _LMS_RULES
        assert "My Plugins" in result

    async def test_openedx_credentials_included(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("openedx_authenticate")]
        with patch(
            "app.services.plugin.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_OPENEDX_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is not None
        assert "https://lms.example.com" in result
        assert "https://studio.example.com" in result
        assert "admin" in result
        assert "secret" in result

    async def test_canvas_credentials_included(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("canvas_get_courses")]
        with patch(
            "app.services.plugin.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_CANVAS_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is not None
        assert "https://canvas.example.com" in result
        assert "token-abc123" in result
        assert "api_token" in result

    async def test_both_lms_credentials_included(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("openedx_create_course_run"), _make_tool("canvas_create_course")]
        with patch(
            "app.services.plugin.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=_BOTH_PLUGIN_MAP),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result is not None
        assert "https://lms.example.com" in result
        assert "https://canvas.example.com" in result

    async def test_rule_5_absent_when_no_credentials(self, mock_session: AsyncMock) -> None:
        """Rule 5 (use credentials automatically) must not appear when no credentials are configured."""
        tools = [_make_tool("openedx_authenticate")]
        with patch(
            "app.services.plugin.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value={}),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == _LMS_RULES
        assert "5." not in result

    async def test_rule_5_present_when_credentials_configured(self, mock_session: AsyncMock) -> None:
        """Rule 5 must appear and credentials must follow it when configured."""
        tools = [_make_tool("openedx_authenticate")]
        with patch(
            "app.services.plugin.PluginService.get_user_plugin_map",
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
            "app.services.plugin.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=plugin_map),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == _LMS_RULES

    async def test_empty_config_falls_back_to_hint(self, mock_session: AsyncMock) -> None:
        tools = [_make_tool("openedx_authenticate")]
        plugin_map = {"open-edx": _make_user_plugin({})}
        with patch(
            "app.services.plugin.PluginService.get_user_plugin_map",
            new=AsyncMock(return_value=plugin_map),
        ):
            result = await build_lms_credentials_message(session=mock_session, user_id=1, tools=tools)
        assert result == _LMS_RULES
