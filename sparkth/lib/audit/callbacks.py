"""Framework-level audit capture for LangChain tool executions.

Importing this module (or anything that imports it) activates
:class:`AuditToolCallbackHandler` process-wide: every tool run LangChain
performs is recorded as a fail-closed ``tool.invoked`` / ``tool.completed`` /
``tool.failed`` pair with no per-tool wiring. Kept out of the
:mod:`sparkth.lib.audit` package root so importing the audit write path does
not pull in LangChain.

``AUDIT_AT_HANDLER_TAG`` marks a LangChain tool whose executions are already
recorded at the handler level (a hook-wrapped ``Tool.handler``); tag such
tools so their runs are never double-recorded.
"""

from sparkth.core.audit.callbacks import AUDIT_AT_HANDLER_TAG, AuditToolCallbackHandler

__all__ = [
    "AUDIT_AT_HANDLER_TAG",
    "AuditToolCallbackHandler",
]
