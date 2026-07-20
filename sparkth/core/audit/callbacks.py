"""Process-global LangChain callback handler auditing every tool execution.

The framework-level companion to
:func:`sparkth.core.audit.execution.audited_tool_handler`: instead of wrapping
individual tool callables, this handler hooks LangChain's callback system (the
same extension point tracing uses) so every tool run the framework performs is
recorded automatically, with no per-tool or per-agent wiring. Importing this
module registers the :data:`audit_tool_callbacks` hook for the whole process
via ``register_configure_hook``; the handler is active whenever that
contextvar holds an instance.

Failure semantics mirror the wrapper (NIST AU-5 fail-closed): ``raise_error``
plus ``run_inline`` make the ``tool.invoked`` write complete before the tool
executes and abort the run when it fails; a ``tool.completed`` write failure
raises :class:`~sparkth.core.audit.exceptions.AuditCaptureError`; a
``tool.failed`` write failure is logged and suppressed so the tool's own error
surfaces and the missing outcome event stays the abnormal-termination signal.

Tools whose executions are already recorded at the handler level (the chat
registry's hook-wrapped handlers) carry :data:`AUDIT_AT_HANDLER_TAG` in their
``tags`` so their runs are skipped and never double-recorded.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.tracers.context import register_configure_hook
from sqlalchemy.exc import SQLAlchemyError

from sparkth.core.audit.constants import MAX_DEPTH, TOOL_INVOCATION_TARGET_TYPE
from sparkth.core.audit.context import current_model_info
from sparkth.core.audit.enums import AuditOutcome
from sparkth.core.audit.events import ToolCompletedAuditEvent, ToolFailedAuditEvent, ToolInvokedAuditEvent
from sparkth.core.audit.exceptions import AuditCaptureError
from sparkth.core.audit.execution import _jsonable
from sparkth.core.audit.recorder import record_event_now
from sparkth.core.audit.redaction import scrub_error_detail
from sparkth.core.audit.types import AuditModelInfo, AuditTarget, AuditToolCall
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

# Marks a LangChain tool whose executions are already recorded at the handler
# level, so the callback must not record its runs a second time.
AUDIT_AT_HANDLER_TAG = "sparkth:audited-at-handler"


@dataclass(frozen=True)
class _ToolRun:
    """Identity of one in-flight tool run, shared by its event pair."""

    call: AuditToolCall
    model: AuditModelInfo | None
    target: AuditTarget


class AuditToolCallbackHandler(AsyncCallbackHandler):
    """Record the audit event pair around every LangChain tool run."""

    # An on_tool_start failure must abort the run (fail-closed), and the
    # invoked write must be awaited before the tool executes rather than
    # racing it in a gathered task.
    raise_error = True
    run_inline = True

    def __init__(self) -> None:
        self._runs: dict[UUID, _ToolRun] = {}

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if tags and AUDIT_AT_HANDLER_TAG in tags:
            return

        name = serialized.get("name", "unknown")
        args = inputs if inputs is not None else {"input": input_str}
        call = AuditToolCall(name=name, args={key: _jsonable(value, MAX_DEPTH) for key, value in args.items()})
        target = AuditTarget(type=TOOL_INVOCATION_TARGET_TYPE, id=uuid4().hex)
        run = _ToolRun(call=call, model=current_model_info(), target=target)

        try:
            await record_event_now(
                ToolInvokedAuditEvent(outcome=AuditOutcome.SUCCESS, tool=run.call, model=run.model, target=run.target)
            )
        except SQLAlchemyError as exc:
            logger.exception("Audit 'tool.invoked' write failed; refusing tool '%s'", name)
            raise AuditCaptureError("tool.invoked", name) from exc
        self._runs[run_id] = run

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        run = self._runs.pop(run_id, None)
        if run is None:
            return
        try:
            await record_event_now(
                ToolCompletedAuditEvent(outcome=AuditOutcome.SUCCESS, tool=run.call, model=run.model, target=run.target)
            )
        except SQLAlchemyError as exc:
            logger.exception("Audit 'tool.completed' write failed for tool '%s'", run.call.name)
            raise AuditCaptureError("tool.completed", run.call.name) from exc

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        run = self._runs.pop(run_id, None)
        if run is None:
            return
        try:
            await record_event_now(
                ToolFailedAuditEvent(
                    outcome=AuditOutcome.FAILURE,
                    tool=run.call,
                    model=run.model,
                    target=run.target,
                    error_detail=scrub_error_detail(error),
                )
            )
        except SQLAlchemyError:
            # The invocation is already on record; a missing outcome event is
            # the abnormal-termination signal, so the tool's own error must
            # surface, not the audit store's.
            logger.exception("Audit 'tool.failed' write failed for tool '%s'", run.call.name)


# Process-global registration: LangChain's CallbackManager.configure() adds
# the ContextVar's value to every run (the mechanism tracing integrations
# use). Inactive while the value is None; the execution seams switch over to
# it (and away from per-tool wrapping) by giving it a default instance.
audit_tool_callbacks: ContextVar[AuditToolCallbackHandler | None] = ContextVar("audit_tool_callbacks", default=None)
register_configure_hook(audit_tool_callbacks, inheritable=True)
