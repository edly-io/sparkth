"""Tool-execution capture plumbing beyond the wrapper itself.

:func:`sparkth.lib.audit.audited_tool_handler` (re-exported at the package
root, next to the write path it feeds) is all most seams need;
:func:`tool_execution_recording` is for protocol-layer backstops that must
record exactly the failures no wrapped handler saw, such as the FastMCP
``on_call_tool`` middleware.
"""

from sparkth.core.audit.execution import tool_execution_recording

__all__ = [
    "tool_execution_recording",
]
