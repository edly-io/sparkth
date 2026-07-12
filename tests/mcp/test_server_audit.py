"""The FastMCP server seam: tool calls served on ``/ai/mcp`` are audited by
the wrapped handlers, and the ``ToolCallAuditMiddleware`` backstop records
protocol-level failures that never reach a handler (unknown tool, input
validation), per ADR-0002 seam table row three."""

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from sparkth.lib.testing import AuditEventsFetcher
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
