"""The audited tool-execution wrapper: every AI tool call is recorded as a
``tool.invoked`` event committed *before* the handler runs (a failed write
refuses the call, per ADR-0002 fail-closed semantics) plus a ``tool.completed``
or ``tool.failed`` outcome event, paired by a shared invocation target id."""

from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import OperationalError

from sparkth.core.audit.constants import REDACTED, TOOL_INVOCATION_TARGET_TYPE
from sparkth.core.audit.execution import AsyncToolHandler
from sparkth.lib.audit import audited_tool_handler, record_event_now
from sparkth.lib.audit.context import AuditSource, ai_audit_context
from sparkth.lib.audit.events import (
    AuditModelInfo,
    ToolCompletedAuditEvent,
    ToolFailedAuditEvent,
    ToolInvokedAuditEvent,
)
from sparkth.lib.audit.exceptions import AuditCaptureError
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

    with pytest.raises(AuditCaptureError):
        await wrapped()

    assert executed is False


async def test_completed_write_failure_raises_audit_capture_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool call whose outcome cannot be attested is an audit-infra failure,
    surfaced as the distinct capture error, not as a storage error the
    execution seams could mistake for an ordinary tool failure."""
    writes = 0

    async def flaky_write(event: Any) -> Any:
        nonlocal writes
        writes += 1
        if writes > 1:
            raise OperationalError("INSERT", {}, Exception("audit db down"))
        return None

    monkeypatch.setattr("sparkth.core.audit.execution.record_event_now", flaky_write)
    wrapped = audited_tool_handler(sample_tool)

    with pytest.raises(AuditCaptureError):
        await wrapped(course_id=1)


async def test_failed_write_failure_surfaces_the_handler_error(
    audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An audit-store outage after the handler raised must not replace the
    handler's exception: the invocation is already on record, and a missing
    outcome event is the crash-detection signal."""
    real_write = record_event_now
    writes = 0

    async def flaky_write(event: Any) -> Any:
        nonlocal writes
        writes += 1
        if writes > 1:
            raise OperationalError("INSERT", {}, Exception("audit db down"))
        return await real_write(event)

    monkeypatch.setattr("sparkth.core.audit.execution.record_event_now", flaky_write)

    async def exploding_tool() -> None:
        """Always fails."""
        raise RuntimeError("boom")

    wrapped = audited_tool_handler(exploding_tool)

    with pytest.raises(RuntimeError, match="boom"):
        await wrapped()

    rows = await audit_events()
    assert [(row.category, row.action) for row in rows] == [("tool", "invoked")]


def test_sync_handler_is_rejected_at_wrap_time() -> None:
    """A sync handler would record ``tool.invoked`` and then fail on ``await``
    at every call; the wrapper narrows the contract loudly instead."""

    def sync_tool(course_id: int) -> str:
        """Not a coroutine function."""
        return "ok"

    with pytest.raises(TypeError, match="async"):
        # The cast models how sync handlers slip through in practice: the
        # seams accept Callable[..., Any], so only the runtime guard catches it.
        audited_tool_handler(cast("AsyncToolHandler", sync_tool))


async def test_handler_error_detail_is_scrubbed(audit_events: AuditEventsFetcher) -> None:
    """Pydantic validation errors echo the failing input back; the recorded
    error detail must not carry it into the store."""

    class Course(BaseModel):
        course_id: int

    async def validating_tool(raw_id: str) -> Course:
        """Validates its input."""
        return Course.model_validate({"course_id": raw_id})

    wrapped = audited_tool_handler(validating_tool)

    with pytest.raises(ValidationError):
        await wrapped(raw_id="s3cret-value")

    failed = (await audit_events())[1]
    assert (failed.category, failed.action) == ("tool", "failed")
    assert failed.error_detail is not None
    assert "s3cret-value" not in failed.error_detail


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
