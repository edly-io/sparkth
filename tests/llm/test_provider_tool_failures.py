"""How the chat tool loop classifies a call that never reached the tool."""

import logging
from typing import Any

import pytest
from langchain_core.tools import StructuredTool

from sparkth.lib.audit import ToolFailureKind
from sparkth.lib.plugins import PluginNotConfiguredError
from sparkth.llm.providers import AnthropicProvider


def _lookup_course_tool() -> StructuredTool:
    async def lookup_course(course_id: int) -> dict[str, Any]:
        """Look up a course."""
        return {"course_id": course_id}

    return StructuredTool.from_function(coroutine=lookup_course, name="lookup_course", description="Look up a course.")


async def test_invalid_arguments_are_a_validation_failure() -> None:
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-5")

    _result, failure = await provider._execute_tool("lookup_course", {"course_id": "abc"}, [_lookup_course_tool()])

    assert failure is ToolFailureKind.VALIDATION


async def _unconfigured_lms() -> dict[str, Any]:
    """Call an LMS the user has not set up."""
    raise PluginNotConfiguredError("Canvas")


async def test_missing_plugin_settings_log_a_warning_without_a_traceback(caplog: pytest.LogCaptureFixture) -> None:
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-5")
    tool = StructuredTool.from_function(coroutine=_unconfigured_lms, name="unconfigured_lms", description="An LMS.")

    with caplog.at_level(logging.DEBUG):
        result, failure = await provider._execute_tool("unconfigured_lms", {}, [tool])

    assert result == f"Error executing tool 'unconfigured_lms': {PluginNotConfiguredError('Canvas')}"
    assert failure is ToolFailureKind.UNKNOWN
    reports = [record for record in caplog.records if "unconfigured_lms" in record.getMessage()]
    assert [record.levelno for record in reports] == [logging.WARNING]
    assert reports[0].exc_info is None
    assert all(record.levelno < logging.ERROR for record in caplog.records)


async def test_a_tool_name_that_is_not_bound_is_a_validation_failure() -> None:
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-5")

    result, failure = await provider._execute_tool("no_such_tool", {}, [_lookup_course_tool()])

    assert failure is ToolFailureKind.VALIDATION
    assert "not found" in result
