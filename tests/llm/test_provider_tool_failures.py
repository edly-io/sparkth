"""How a chat turn classifies a tool call that failed."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from sparkth.lib.audit import ToolFailureKind
from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.plugins import PluginNotConfiguredError
from sparkth.lib.testing import ScriptedChatModel
from sparkth.llm.providers import AnthropicProvider


async def lookup_course(course_id: int) -> dict[str, Any]:
    """Look up a course."""
    return {"course_id": course_id}


async def unconfigured_lms() -> dict[str, Any]:
    """Call an LMS the user has not set up."""
    raise PluginNotConfiguredError("Canvas")


def _tool(handler: Callable[..., Awaitable[dict[str, Any]]], description: str) -> StructuredTool:
    return StructuredTool.from_function(coroutine=handler, description=description, tags=[AUDIT_AT_HANDLER_TAG])


async def _first_execution(
    tool: StructuredTool, tool_name: str, args: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> dict[str, Any]:
    """The recorded execution of the one call a non-streamed turn makes to ``tool_name``."""
    provider = AnthropicProvider("test-key", "claude-sonnet-5")
    call = AIMessage(content="", tool_calls=[{"name": tool_name, "args": args, "id": "call_1"}])
    model = ScriptedChatModel(messages=iter([call, AIMessage("done")]))
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: model)

    response = await provider.send_message([{"role": "user", "content": "go"}], tools=[tool])

    execution: dict[str, Any] = response["metadata"]["tool_executions"][0]
    return execution


async def test_invalid_arguments_are_a_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool(lookup_course, "Look up a course.")

    execution = await _first_execution(tool, "lookup_course", {"course_id": "abc"}, monkeypatch)

    assert execution["failure"] is ToolFailureKind.VALIDATION


async def test_a_tool_name_that_is_not_bound_is_a_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool(lookup_course, "Look up a course.")

    execution = await _first_execution(tool, "no_such_tool", {}, monkeypatch)

    assert execution["failure"] is ToolFailureKind.VALIDATION


async def test_missing_plugin_settings_log_a_warning_without_a_traceback(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = _tool(unconfigured_lms, "An LMS.")

    with caplog.at_level(logging.DEBUG):
        execution = await _first_execution(tool, "unconfigured_lms", {}, monkeypatch)

    assert execution["output"] == f"Error executing tool 'unconfigured_lms': {PluginNotConfiguredError('Canvas')}"
    assert execution["failure"] is ToolFailureKind.UNKNOWN
    reports = [
        record
        for record in caplog.records
        if record.levelno >= logging.WARNING and "unconfigured_lms" in record.getMessage()
    ]
    assert [record.levelno for record in reports] == [logging.WARNING]
    assert reports[0].exc_info is None
    assert all(record.levelno < logging.ERROR for record in caplog.records)
