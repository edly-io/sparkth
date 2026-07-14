"""The FastMCP server seam: tool calls served on ``/ai/mcp`` are audited by
the wrapped handlers, and the ``ToolCallAuditMiddleware`` backstop records
protocol-level failures that never reach a handler (unknown tool, input
validation), per ADR-0002 seam table row three."""

from types import SimpleNamespace
from typing import Any, cast

import mcp.types as mt
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, MiddlewareContext
from fastmcp.tools.tool import ToolResult
from sqlalchemy.exc import OperationalError

from sparkth.lib.audit import audited_tool_handler
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.mcp.audit import ToolCallAuditMiddleware
from sparkth.mcp.server import mcp


async def test_direct_server_tool_call_is_audited(audit_events: AuditEventsFetcher) -> None:
    async with Client(mcp) as client:
        await client.call_tool(
            "get_course_generation_prompt_tool",
            {"course_params": {"course_name": "Algebra", "course_description": "Linear equations"}},
        )

    rows = await audit_events()
    assert [(row.category, row.action) for row in rows] == [("tool", "invoked"), ("tool", "completed")]
    assert rows[0].tool_name == "get_course_generation_prompt_tool"


async def test_unknown_tool_call_records_protocol_failure(audit_events: AuditEventsFetcher) -> None:
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            await client.call_tool("no_such_tool", {})

    rows = await audit_events()
    assert len(rows) == 1
    failed = rows[0]
    assert (failed.category, failed.action) == ("tool", "failed")
    assert failed.tool_name == "no_such_tool"
    assert failed.outcome == "failure"
    assert failed.error_detail


async def test_handler_level_failure_is_not_double_recorded(audit_events: AuditEventsFetcher) -> None:
    """When the wrapped handler already recorded the failure, the middleware
    backstop must stay silent: one invocation, one failure record."""
    async with Client(mcp) as client:
        with pytest.raises(ToolError):
            # Invalid input shape passes the protocol layer but fails handler-side
            # validation before the wrapped handler runs, so this is protocol-level.
            await client.call_tool("get_course_generation_prompt_tool", {"course_params": "not-a-mapping"})

    rows = await audit_events()
    failures = [row for row in rows if row.action == "failed"]
    assert len(failures) == 1


async def test_runtime_handler_failure_is_recorded_exactly_once(audit_events: AuditEventsFetcher) -> None:
    """A wrapped handler that raises during execution records the failure
    itself; the middleware backstop must observe that (via the recording
    contextvar propagating back through FastMCP) and stay silent."""
    server = FastMCP(name="test-audit")
    server.add_middleware(ToolCallAuditMiddleware())

    @server.tool
    @audited_tool_handler
    async def exploding_tool(course_id: int) -> str:
        """Always fails at runtime."""
        raise RuntimeError("boom")

    async with Client(server) as client:
        with pytest.raises(ToolError):
            await client.call_tool("exploding_tool", {"course_id": 1})

    rows = await audit_events()
    assert [(row.category, row.action) for row in rows] == [("tool", "invoked"), ("tool", "failed")]


async def test_backstop_write_failure_does_not_replace_the_original_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the audit store is down, the backstop's own write failure is
    logged, not raised: the protocol error that triggered the backstop must
    surface unchanged instead of being masked by an audit-infra error."""

    async def broken_write(event: Any) -> Any:
        raise OperationalError("INSERT", {}, Exception("audit db down"))

    monkeypatch.setattr("sparkth.mcp.audit.record_event_now", broken_write)

    async def failing_call_next(ctx: MiddlewareContext[mt.CallToolRequestParams]) -> ToolResult:
        raise ToolError("unknown tool")

    context = cast(
        "MiddlewareContext[mt.CallToolRequestParams]",
        SimpleNamespace(message=mt.CallToolRequestParams(name="no_such_tool", arguments={})),
    )
    call_next = cast("CallNext[mt.CallToolRequestParams, ToolResult]", failing_call_next)

    with pytest.raises(ToolError, match="unknown tool"):
        await ToolCallAuditMiddleware().on_call_tool(context, call_next)
