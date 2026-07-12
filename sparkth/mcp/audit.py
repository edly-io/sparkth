"""Protocol-level audit backstop for the FastMCP server.

Successful tool calls (and handler-raised failures) are recorded by the
audited handler wrapper (:func:`sparkth.lib.audit.audited_tool_handler`); this
middleware covers the calls that never reach a handler (unknown tool names
and input-validation rejections), so every ``tools/call`` on ``/ai/mcp``
leaves a record either way (ADR-0002 seam table row three).
"""

from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.tool import ToolResult

from sparkth.lib.audit import record_event_now
from sparkth.lib.audit.events import AuditOutcome, AuditToolCall, ToolFailedAuditEvent
from sparkth.lib.audit.execution import tool_execution_recording
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


class ToolCallAuditMiddleware(Middleware):
    """Record ``tool.failed`` for calls no audited handler ever saw."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        with tool_execution_recording() as handler_recorded:
            try:
                return await call_next(context)
            # NOTE: Kept broad intentionally: any protocol-layer error
            # (unknown tool, validation, handler crash) must be considered
            # for the backstop record, and is always re-raised.
            except Exception as exc:
                if not handler_recorded():
                    await self._record_protocol_failure(context.message, exc)
                raise

    @staticmethod
    async def _record_protocol_failure(message: mt.CallToolRequestParams, exc: Exception) -> None:
        args: dict[str, Any] | None = message.arguments
        await record_event_now(
            ToolFailedAuditEvent(
                outcome=AuditOutcome.FAILURE,
                tool=AuditToolCall(name=message.name, args=args),
                error_detail=f"{type(exc).__name__}: {exc}",
            )
        )
