"""Framework-level audit capture: the process-global LangChain callback
handler records a fail-closed ``tool.invoked`` / ``tool.completed`` /
``tool.failed`` pair around every tool execution LangChain performs, so agent
tools need no per-tool wrapping. Runs tagged ``AUDIT_AT_HANDLER_TAG`` are
skipped: their executions are already recorded at the handler level."""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.callbacks.manager import AsyncCallbackManager
from langchain_core.tools import StructuredTool
from sqlalchemy.exc import OperationalError

from sparkth.core.audit.callbacks import audit_tool_callbacks
from sparkth.core.audit.constants import REDACTED, TOOL_INVOCATION_TARGET_TYPE
from sparkth.lib.audit import record_event_now
from sparkth.lib.audit.callbacks import AUDIT_AT_HANDLER_TAG, AuditToolCallbackHandler
from sparkth.lib.audit.context import AuditSource, ai_audit_context
from sparkth.lib.audit.events import AuditModelInfo
from sparkth.lib.audit.exceptions import AuditCaptureError
from sparkth.lib.testing import AuditEventsFetcher


@pytest.fixture(autouse=True)
def active_audit_callbacks() -> Iterator[AuditToolCallbackHandler]:
    """Activate the handler through its contextvar, the production mechanism."""
    handler = AuditToolCallbackHandler()
    token = audit_tool_callbacks.set(handler)
    try:
        yield handler
    finally:
        audit_tool_callbacks.reset(token)


async def sample_tool(course_id: int, title: str = "untitled") -> dict[str, Any]:
    """Create a sample course."""
    return {"course_id": course_id, "title": title}


def _tool(coroutine: Any, tags: list[str] | None = None) -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=coroutine,
        name=coroutine.__name__,
        description=(coroutine.__doc__ or "").strip(),
        tags=tags,
    )


async def test_tool_run_records_invoked_and_completed_pair(audit_events: AuditEventsFetcher) -> None:
    result = await _tool(sample_tool).ainvoke({"course_id": 7, "title": "Algebra"})

    assert result == {"course_id": 7, "title": "Algebra"}
    invoked, completed = await audit_events()
    assert (invoked.category, invoked.action) == ("tool", "invoked")
    assert (completed.category, completed.action) == ("tool", "completed")
    assert invoked.tool_name == "sample_tool"
    assert invoked.tool_args == {"course_id": 7, "title": "Algebra"}
    assert invoked.target_type == TOOL_INVOCATION_TARGET_TYPE
    # The pair shares one invocation id so a crash mid-execution is detectable
    # as an invoked event with no matching outcome event.
    assert invoked.target_id is not None
    assert invoked.target_id == completed.target_id


async def test_tool_error_records_failed_event_and_reraises(audit_events: AuditEventsFetcher) -> None:
    async def exploding_tool(course_id: int) -> None:
        """Always fails."""
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await _tool(exploding_tool).ainvoke({"course_id": 1})

    invoked, failed = await audit_events()
    assert (invoked.category, invoked.action) == ("tool", "invoked")
    assert (failed.category, failed.action) == ("tool", "failed")
    assert failed.outcome == "failure"
    assert failed.error_detail is not None
    assert "boom" in failed.error_detail
    assert invoked.target_id == failed.target_id


async def test_invoked_write_failure_aborts_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail-closed: if ``tool.invoked`` cannot be committed, the tool must
    never execute, matching the handler-level wrapper's semantics."""
    executed = False

    async def side_effect_tool() -> str:
        """Records that it ran."""
        nonlocal executed
        executed = True
        return "ran"

    async def broken_write(event: Any) -> Any:
        raise OperationalError("INSERT", {}, Exception("audit db down"))

    monkeypatch.setattr("sparkth.core.audit.callbacks.record_event_now", broken_write)

    with pytest.raises(AuditCaptureError):
        await _tool(side_effect_tool).ainvoke({})

    assert executed is False


async def test_completed_write_failure_raises_audit_capture_error(monkeypatch: pytest.MonkeyPatch) -> None:
    writes = 0

    async def flaky_write(event: Any) -> Any:
        nonlocal writes
        writes += 1
        if writes > 1:
            raise OperationalError("INSERT", {}, Exception("audit db down"))
        return None

    monkeypatch.setattr("sparkth.core.audit.callbacks.record_event_now", flaky_write)

    with pytest.raises(AuditCaptureError):
        await _tool(sample_tool).ainvoke({"course_id": 1})


async def test_failed_write_failure_surfaces_the_tool_error(
    audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An audit-store outage after the tool raised must not replace the tool's
    exception: the invocation is already on record, and a missing outcome
    event is the crash-detection signal."""
    real_write = record_event_now
    writes = 0

    async def flaky_write(event: Any) -> Any:
        nonlocal writes
        writes += 1
        if writes > 1:
            raise OperationalError("INSERT", {}, Exception("audit db down"))
        return await real_write(event)

    monkeypatch.setattr("sparkth.core.audit.callbacks.record_event_now", flaky_write)

    async def exploding_tool() -> None:
        """Always fails."""
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await _tool(exploding_tool).ainvoke({})

    rows = await audit_events()
    assert [(row.category, row.action) for row in rows] == [("tool", "invoked")]


async def test_runs_tagged_audited_at_handler_are_skipped(audit_events: AuditEventsFetcher) -> None:
    """Tools whose executions are already recorded at the handler level (the
    chat registry's hook-wrapped handlers) carry the tag so the callback never
    double-records them."""
    result = await _tool(sample_tool, tags=[AUDIT_AT_HANDLER_TAG]).ainvoke({"course_id": 7, "title": "Algebra"})

    assert result == {"course_id": 7, "title": "Algebra"}
    assert await audit_events() == []


async def test_model_and_source_come_from_ai_audit_context(audit_events: AuditEventsFetcher) -> None:
    model = AuditModelInfo(provider="anthropic", name="claude-sonnet-5", version="claude-sonnet-5-20250929")

    with ai_audit_context(source=AuditSource.RAG, model=model):
        await _tool(sample_tool).ainvoke({"course_id": 1})

    invoked, completed = await audit_events()
    for row in (invoked, completed):
        assert row.source == "rag"
        assert row.model_provider == "anthropic"
        assert row.model_name == "claude-sonnet-5"


async def test_secret_args_are_redacted(audit_events: AuditEventsFetcher) -> None:
    async def authed_tool(auth: dict[str, Any], course_id: int) -> str:
        """Tool taking a credentials payload."""
        return "ok"

    await _tool(authed_tool).ainvoke({"auth": {"api_url": "https://x", "token": "s3cret"}, "course_id": 1})

    invoked = (await audit_events())[0]
    assert invoked.tool_args is not None
    assert invoked.tool_args["auth"] == REDACTED
    assert invoked.tool_args["course_id"] == 1


async def test_run_tracking_is_bounded_and_evicts_oldest_first(
    active_audit_callbacks: AuditToolCallbackHandler,
    audit_events: AuditEventsFetcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A run cancelled between callbacks never gets a terminal callback
    (LangChain fires ``on_tool_error`` only for ``Exception`` and
    ``KeyboardInterrupt``, not ``asyncio.CancelledError``), so in-flight run
    tracking must stay bounded instead of accumulating for the process
    lifetime. The oldest entry is dropped first, and a dropped run's late
    outcome callback is a no-op: its invocation stays on record with no
    outcome event, the same signal a crash leaves."""
    monkeypatch.setattr("sparkth.core.audit.callbacks.MAX_TRACKED_TOOL_RUNS", 2)
    handler = active_audit_callbacks

    first, second, third = uuid4(), uuid4(), uuid4()
    for run_id in (first, second, third):
        await handler.on_tool_start({"name": "orphaned_tool"}, "{}", run_id=run_id)

    await handler.on_tool_end("late", run_id=first)
    await handler.on_tool_end("ok", run_id=third)

    rows = await audit_events()
    assert [(row.category, row.action) for row in rows] == [
        ("tool", "invoked"),
        ("tool", "invoked"),
        ("tool", "invoked"),
        ("tool", "completed"),
    ]
    # The completed event belongs to the still-tracked third run, not the
    # evicted first one.
    assert rows[3].target_id == rows[2].target_id


def test_handler_reaches_every_callback_manager(active_audit_callbacks: AuditToolCallbackHandler) -> None:
    """Importing the callbacks module registers the configure hook process-wide
    (the same mechanism LangSmith tracing uses), so whenever the contextvar
    holds a handler, every LangChain tool run picks it up without per-call
    wiring."""
    manager = AsyncCallbackManager.configure()
    assert active_audit_callbacks in manager.inheritable_handlers


def test_handler_is_fail_closed_and_ordered() -> None:
    """``raise_error`` makes an ``on_tool_start`` failure abort the run;
    ``run_inline`` guarantees the ``tool.invoked`` write is awaited before the
    tool executes rather than racing it in a gathered task."""
    handler = AuditToolCallbackHandler()
    assert handler.raise_error is True
    assert handler.run_inline is True
