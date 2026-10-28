"""Chat turns are an audited seam: each tool call is recorded with source ``chat`` and the
model that requested it."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from sqlalchemy.exc import OperationalError

from sparkth.lib.audit import audited_tool
from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG
from sparkth.lib.audit.exceptions import AuditCaptureError
from sparkth.lib.llm import BaseChatProvider, get_provider
from sparkth.lib.testing import AuditEventsFetcher, ScriptedChatModel
from sparkth.plugins.chat.llm import _reported_failure, complete_turn, stream_turn

MODEL_METADATA = {"model": "claude-sonnet-5-20250929"}
TURN = [{"role": "user", "content": "look up course 5"}]


async def lookup_course(course_id: int) -> dict[str, Any]:
    """Look up a course."""
    return {"course_id": course_id}


async def broken_write(event: Any) -> Any:
    """An audit store that refuses every write."""
    raise OperationalError("INSERT", {}, Exception("audit db down"))


def _lookup_course_tool() -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=audited_tool(lookup_course),
        name="lookup_course",
        description="Look up a course.",
        tags=[AUDIT_AT_HANDLER_TAG],
    )


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> BaseChatProvider:
    provider = get_provider("anthropic", "test-key", "claude-sonnet-5")
    call = AIMessage(
        content="",
        tool_calls=[{"name": "lookup_course", "args": {"course_id": 5}, "id": "call_1"}],
        response_metadata=MODEL_METADATA,
    )
    model = ScriptedChatModel(messages=iter([call, AIMessage(content="done", response_metadata=MODEL_METADATA)]))
    monkeypatch.setattr(provider, "_create_llm", lambda streaming=False, callbacks=None: model)
    return provider


async def test_a_completed_turn_records_its_tool_calls_with_chat_source_and_model_identity(
    audit_events: AuditEventsFetcher, provider: BaseChatProvider
) -> None:
    response = await complete_turn(TURN, [_lookup_course_tool()], provider, 50)

    assert response["content"] == "done"
    invoked, completed = await audit_events()
    for row in (invoked, completed):
        assert row.source == "chat"
        assert row.tool_name == "lookup_course"
        assert row.model_provider == "anthropic"
        assert row.model_name == "claude-sonnet-5"
        assert row.model_version == "claude-sonnet-5-20250929"
    assert invoked.tool_args == {"course_id": 5}


async def test_a_streamed_turn_records_its_tool_calls(
    audit_events: AuditEventsFetcher, provider: BaseChatProvider
) -> None:
    events = [event async for event in stream_turn(TURN, [_lookup_course_tool()], provider, 50)]

    assert {"type": "tool_start", "name": "lookup_course"} in events
    invoked, completed = await audit_events()
    assert (invoked.category, invoked.action) == ("tool", "invoked")
    assert (completed.category, completed.action) == ("tool", "completed")
    assert invoked.source == "chat"
    assert invoked.model_provider == "anthropic"


async def test_audit_capture_outage_is_a_hard_failure_not_a_tool_error_string(
    provider: BaseChatProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fail-closed capture refusal must surface past the chat turn's broad
    tool-error handling instead of degrading into a model-visible error string
    that leaves no record and no surfaced failure."""
    monkeypatch.setattr("sparkth.core.audit.execution.record_event_now", broken_write)

    with pytest.raises(AuditCaptureError):
        await complete_turn(TURN, [_lookup_course_tool()], provider, 50)


def test_deeply_nested_json_result_is_not_classified_as_a_failure() -> None:
    assert _reported_failure("[" * 100_000 + "]" * 100_000) is None
