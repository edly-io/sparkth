"""How a chat turn classifies a tool call that failed, and what it shows of its agent's text afterwards."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from pydantic import TypeAdapter

from sparkth.lib.audit import ToolFailureKind
from sparkth.lib.llm import get_provider
from sparkth.lib.mcp.exceptions import ToolFailure
from sparkth.lib.mcp.hooks import Tool
from sparkth.lib.plugins import PluginNotConfiguredError
from sparkth.lib.testing import ScriptedChatModel
from sparkth.plugins.compose.constants import TOOL_FAILED_UNEXPECTEDLY
from sparkth.plugins.compose.llm import complete_turn
from sparkth.plugins.compose.tests.conftest import STUB_AGENT
from sparkth.plugins.compose.tests.helpers import handing_off_to


async def lookup_course(course_id: int) -> dict[str, Any]:
    """Look up a course."""
    return {"course_id": course_id}


async def unconfigured_lms() -> dict[str, Any]:
    """Call an LMS the user has not set up."""
    raise PluginNotConfiguredError("Canvas")


async def convert_course_id(course_id: str) -> dict[str, Any]:
    """Look up a course whose id the handler converts itself."""
    return {"course_id": TypeAdapter(int).validate_python(course_id)}


# What a crash inside a tool says: where in the server it happened and what it was reading.
CRASH_DETAIL = "KeyError: 'sandbox.js' in /srv/sparkth/plugins/pxc/builder.py"

# What a tool says when it turns work down on purpose, written for the agent to act on.
REPORTED_FAILURE = "The quiz has no questions. Add at least one and build it again."


async def crashing_tool() -> dict[str, Any]:
    """Fail in a way its author never planned for."""
    raise RuntimeError(CRASH_DETAIL)


async def rejecting_tool() -> dict[str, Any]:
    """Turn the work down and say what to fix."""
    raise ToolFailure(REPORTED_FAILURE)


async def _first_execution(
    handler: Callable[..., Awaitable[dict[str, Any]]],
    tool_name: str,
    args: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """The recorded execution of the one call to ``tool_name`` that a non-streamed turn makes, on an agent whose
    own tool is ``handler``."""
    provider = get_provider("anthropic", "test-key", "claude-sonnet-5")
    call = AIMessage(content="", tool_calls=[{"name": tool_name, "args": args, "id": "call_1"}])
    model = ScriptedChatModel(messages=iter([call, AIMessage("done")]), disable_streaming=True)
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: model)

    response = await complete_turn(
        [{"role": "user", "content": "go"}],
        [],
        provider,
        50,
        planner_setup=handing_off_to(replace(STUB_AGENT, tools=(Tool(handler),))),
    )

    execution: dict[str, Any] = response["metadata"]["tool_executions"][0]
    return execution


async def test_invalid_arguments_are_a_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:

    execution = await _first_execution(lookup_course, "lookup_course", {"course_id": "abc"}, monkeypatch)

    assert execution["failure"] is ToolFailureKind.VALIDATION


async def test_a_rejected_call_warns_with_the_tool_name_and_never_the_arguments(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:

    with caplog.at_level(logging.DEBUG):
        await _first_execution(lookup_course, "lookup_course", {"course_id": "private-course-text"}, monkeypatch)

    warnings = [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert [record.getMessage() for record in warnings] == ["Tool 'lookup_course' call was rejected"]
    details = [record for record in caplog.records if record.levelno == logging.DEBUG]
    assert any("private-course-text" in record.getMessage() for record in details)


async def test_a_tool_name_that_is_not_bound_is_a_validation_failure(monkeypatch: pytest.MonkeyPatch) -> None:

    execution = await _first_execution(lookup_course, "no_such_tool", {}, monkeypatch)

    assert execution["failure"] is ToolFailureKind.VALIDATION


async def test_missing_plugin_settings_log_a_warning_without_a_traceback(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:

    with caplog.at_level(logging.DEBUG):
        execution = await _first_execution(unconfigured_lms, "unconfigured_lms", {}, monkeypatch)

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


async def test_a_validation_error_raised_inside_a_handler_is_an_unknown_failure(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model's arguments were valid, so the failure is the handler's own, not the model's to fix."""

    with caplog.at_level(logging.DEBUG):
        execution = await _first_execution(convert_course_id, "convert_course_id", {"course_id": "abc"}, monkeypatch)

    assert execution["failure"] is ToolFailureKind.UNKNOWN
    assert execution["output"] == TOOL_FAILED_UNEXPECTEDLY.format(name="convert_course_id")
    errors = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    assert errors == ["Tool 'convert_course_id' raised a validation error inside its handler"]


async def test_a_tool_that_crashes_tells_the_model_nothing_of_the_cause(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the model is told it may repeat to the author, so the cause stays in the log."""

    with caplog.at_level(logging.ERROR):
        execution = await _first_execution(crashing_tool, "crashing_tool", {}, monkeypatch)

    assert execution["output"] == TOOL_FAILED_UNEXPECTEDLY.format(name="crashing_tool")
    assert execution["failure"] is ToolFailureKind.UNKNOWN
    assert any(CRASH_DETAIL in record.getMessage() for record in caplog.records)


async def test_a_failure_a_tool_reports_reaches_the_model_as_the_tool_wrote_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent needs it to fix its work and try again."""

    execution = await _first_execution(rejecting_tool, "rejecting_tool", {}, monkeypatch)

    assert REPORTED_FAILURE in execution["output"]
    assert execution["failure"] is ToolFailureKind.UNKNOWN


# What an agent writes around its calls to a tool that keeps turning its work down.
BEFORE_ANY_FAILURE = "Building your quiz now."
BETWEEN_ATTEMPTS = "I need to fix the context handling in sandbox.js."
CLOSING_REPLY = "I couldn't build the quiz. Shall I try a simpler one?"


async def _reply_of_a_turn_whose_tool_fails(monkeypatch: pytest.MonkeyPatch) -> str:
    """The reply of a non-streamed turn whose agent calls a failing tool twice, writing around each call, and
    then answers."""
    provider = get_provider("anthropic", "test-key", "claude-sonnet-5")
    calls = [
        AIMessage(text, tool_calls=[{"name": "rejecting_tool", "args": {}, "id": call_id}])
        for text, call_id in ((BEFORE_ANY_FAILURE, "call_1"), (BETWEEN_ATTEMPTS, "call_2"))
    ]
    model = ScriptedChatModel(messages=iter([*calls, AIMessage(CLOSING_REPLY)]), disable_streaming=True)
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: model)

    response = await complete_turn(
        [{"role": "user", "content": "go"}],
        [],
        provider,
        50,
        planner_setup=handing_off_to(replace(STUB_AGENT, tools=(Tool(rejecting_tool),))),
    )

    reply: str = response["content"]
    return reply


async def test_what_an_agent_writes_before_retrying_a_failed_tool_never_shows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It is the agent working out its fix, which can name what the failure named."""

    reply = await _reply_of_a_turn_whose_tool_fails(monkeypatch)

    assert BETWEEN_ATTEMPTS not in reply


async def test_an_agent_still_answers_after_its_tool_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = await _reply_of_a_turn_whose_tool_fails(monkeypatch)

    assert reply == f"{BEFORE_ANY_FAILURE}\n\n{CLOSING_REPLY}"
