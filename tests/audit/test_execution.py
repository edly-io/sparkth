"""The audited tool-execution wrapper: every AI tool call is recorded as a
``tool.invoked`` event committed *before* the handler runs (a failed write
refuses the call, per ADR-0002 fail-closed semantics) plus a ``tool.completed``
or ``tool.failed`` outcome event, paired by a shared invocation target id."""

from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from sparkth.core.audit.constants import REDACTED, TOOL_INVOCATION_TARGET_TYPE
from sparkth.lib.audit import audited_tool_handler
from sparkth.lib.audit.context import AuditSource, ai_audit_context
from sparkth.lib.audit.events import (
    AuditModelInfo,
    ToolCompletedAuditEvent,
    ToolFailedAuditEvent,
    ToolInvokedAuditEvent,
)
from sparkth.lib.audit.hooks import AUDIT_EVENTS
from sparkth.lib.mcp.hooks import generate_input_schema
from sparkth.lib.testing import AuditEventsFetcher


async def sample_tool(course_id: int, title: str = "untitled") -> dict[str, Any]:
    """Create a sample course."""
    return {"course_id": course_id, "title": title}


def test_tool_event_types_are_registered() -> None:
    assert AUDIT_EVENTS.resolve("tool.invoked") is ToolInvokedAuditEvent
    assert AUDIT_EVENTS.resolve("tool.completed") is ToolCompletedAuditEvent
    assert AUDIT_EVENTS.resolve("tool.failed") is ToolFailedAuditEvent


async def test_success_records_invoked_and_completed_pair(audit_events: AuditEventsFetcher) -> None:
    wrapped = audited_tool_handler(sample_tool)

    result = await wrapped(course_id=7, title="Algebra")

    assert result == {"course_id": 7, "title": "Algebra"}
    invoked, completed = await audit_events()
    assert (invoked.category, invoked.action) == ("tool", "invoked")
    assert (completed.category, completed.action) == ("tool", "completed")
    assert invoked.outcome == "success"
    assert completed.outcome == "success"
    assert invoked.tool_name == "sample_tool"
    assert completed.tool_name == "sample_tool"
    assert invoked.tool_args == {"course_id": 7, "title": "Algebra"}
    # The pair shares one invocation id so a crash mid-execution is detectable
    # as an invoked event with no matching outcome event.
    assert invoked.target_type == TOOL_INVOCATION_TARGET_TYPE
    assert completed.target_type == TOOL_INVOCATION_TARGET_TYPE
    assert invoked.target_id is not None
    assert invoked.target_id == completed.target_id


async def test_failure_records_failed_event_and_reraises(audit_events: AuditEventsFetcher) -> None:
    async def exploding_tool(course_id: int) -> None:
        """Always fails."""
        raise RuntimeError("boom")

    wrapped = audited_tool_handler(exploding_tool)

    with pytest.raises(RuntimeError, match="boom"):
        await wrapped(course_id=1)

    invoked, failed = await audit_events()
    assert (invoked.category, invoked.action) == ("tool", "invoked")
    assert (failed.category, failed.action) == ("tool", "failed")
    assert failed.outcome == "failure"
    assert failed.error_detail is not None
    assert "boom" in failed.error_detail
    assert invoked.target_id == failed.target_id


async def test_invoked_write_failure_refuses_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    executed = False

    async def side_effect_tool() -> str:
        """Records that it ran."""
        nonlocal executed
        executed = True
        return "ran"

    async def broken_write(event: Any) -> Any:
        raise OperationalError("INSERT", {}, Exception("audit db down"))

    monkeypatch.setattr("sparkth.core.audit.execution.record_event_now", broken_write)
    wrapped = audited_tool_handler(side_effect_tool)

    with pytest.raises(OperationalError):
        await wrapped()

    assert executed is False


async def test_positional_args_are_recorded_by_parameter_name(audit_events: AuditEventsFetcher) -> None:
    wrapped = audited_tool_handler(sample_tool)

    await wrapped(3, "Physics")

    invoked = (await audit_events())[0]
    assert invoked.tool_args == {"course_id": 3, "title": "Physics"}


async def test_secret_args_are_redacted(audit_events: AuditEventsFetcher) -> None:
    async def authed_tool(auth: dict[str, Any], course_id: int) -> str:
        """Tool taking a credentials payload."""
        return "ok"

    wrapped = audited_tool_handler(authed_tool)

    await wrapped(auth={"api_url": "https://x", "token": "s3cret"}, course_id=1)

    invoked = (await audit_events())[0]
    assert invoked.tool_args is not None
    assert invoked.tool_args["auth"] == REDACTED
    assert invoked.tool_args["course_id"] == 1


async def test_pydantic_args_are_dumped_and_redacted(audit_events: AuditEventsFetcher) -> None:
    class Credentials(BaseModel):
        username: str
        password: str

    class Payload(BaseModel):
        name: str
        auth: Credentials

    async def model_tool(payload: Payload) -> str:
        """Tool taking a Pydantic payload."""
        return "ok"

    wrapped = audited_tool_handler(model_tool)

    await wrapped(payload=Payload(name="course", auth=Credentials(username="u", password="p")))

    invoked = (await audit_events())[0]
    assert invoked.tool_args == {"payload": {"name": "course", "auth": REDACTED}}


async def test_model_identity_and_source_come_from_ai_audit_context(audit_events: AuditEventsFetcher) -> None:
    wrapped = audited_tool_handler(sample_tool)
    model = AuditModelInfo(provider="anthropic", name="claude-sonnet-5", version="claude-sonnet-5-20250929")

    with ai_audit_context(source=AuditSource.CHAT, model=model):
        await wrapped(course_id=1)

    invoked, completed = await audit_events()
    for row in (invoked, completed):
        assert row.source == "chat"
        assert row.model_provider == "anthropic"
        assert row.model_name == "claude-sonnet-5"
        assert row.model_version == "claude-sonnet-5-20250929"


async def test_without_ai_context_model_columns_stay_empty(audit_events: AuditEventsFetcher) -> None:
    wrapped = audited_tool_handler(sample_tool)

    await wrapped(course_id=1)

    invoked = (await audit_events())[0]
    assert invoked.model_provider is None
    assert invoked.model_name is None
    assert invoked.model_version is None


def test_wrapper_marks_handler_as_audited() -> None:
    wrapped = audited_tool_handler(sample_tool)
    assert getattr(wrapped, "__audit_wrapped__", False) is True


def test_wrapper_preserves_handler_identity_and_schema() -> None:
    """ADR-0002 schema-identity regression: the generated input schema must be
    byte-identical after wrapping, or every tool's LLM-facing contract drifts."""
    wrapped = audited_tool_handler(sample_tool)

    assert wrapped.__name__ == "sample_tool"
    assert wrapped.__doc__ == sample_tool.__doc__
    assert generate_input_schema(wrapped) == generate_input_schema(sample_tool)


def test_wrapping_twice_is_idempotent() -> None:
    wrapped = audited_tool_handler(sample_tool)
    assert audited_tool_handler(wrapped) is wrapped
