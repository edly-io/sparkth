"""Audited execution of AI tool handlers.

The single wrapper every tool-execution path goes through (ADR-0002 seam
table): plugin tools are wrapped at :class:`sparkth.lib.mcp.hooks.Tool`
construction, the RAG agent tools and the FastMCP server's directly-registered
tools wrap explicitly. Failure semantics are fail-closed (NIST AU-5): a
``tool.invoked`` event is committed *before* the handler runs, so a write
failure refuses the call (surfaced as the distinct
:class:`~sparkth.core.audit.exceptions.AuditCaptureError` so execution seams
never mistake it for a tool error) and a crash mid-execution still leaves the
invocation on record; a second ``tool.completed`` / ``tool.failed`` event
records the outcome. A ``tool.failed`` write that itself fails is logged and
suppressed: the invocation is already on record, so the handler's own
exception surfaces and the missing outcome event is the abnormal-termination
signal. Corrections are new events, never updates.
"""

import functools
import inspect
from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from sparkth.core.audit.constants import MAX_DEPTH, REDACTED, TOOL_INVOCATION_TARGET_TYPE
from sparkth.core.audit.context import current_model_info
from sparkth.core.audit.enums import AuditOutcome
from sparkth.core.audit.events import ToolCompletedAuditEvent, ToolFailedAuditEvent, ToolInvokedAuditEvent
from sparkth.core.audit.exceptions import AuditCaptureError
from sparkth.core.audit.recorder import record_event_now
from sparkth.core.audit.redaction import scrub_error_detail
from sparkth.core.audit.types import AuditTarget, AuditToolCall
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

AsyncToolHandler = Callable[..., Awaitable[Any]]

# Whether an audited handler has recorded the tool call currently being served.
# Scoped per protocol-level call by tool_execution_recording(); the FastMCP
# middleware uses it to record failures that never reached a wrapped handler
# without ever double-recording ones that did.
_execution_recorded: ContextVar[bool] = ContextVar("audit_tool_execution_recorded", default=False)


@contextmanager
def tool_execution_recording() -> Iterator[Callable[[], bool]]:
    """Track whether an audited handler recorded the enclosed tool call.

    Yields a callable that returns True once a wrapped handler has written its
    ``tool.invoked`` event inside the block. Protocol-layer backstops (the
    FastMCP middleware) use it to record exactly the failures the handler
    wrapper could not see.
    """
    token = _execution_recorded.set(False)
    try:
        yield _execution_recorded.get
    finally:
        _execution_recorded.reset(token)


def audited_tool_handler(handler: AsyncToolHandler) -> AsyncToolHandler:
    """Wrap an async tool handler so every execution is audited.

    Wrapping preserves the handler's name, docstring, signature, and type
    hints, so generated input schemas are byte-identical post-wrap (the
    ADR-0002 schema-identity requirement). Model identity is read from the
    ambient :func:`sparkth.core.audit.context.ai_audit_context`; origin and
    actor come from the audit context as usual. Already-wrapped handlers are
    returned unchanged, so seams can wrap defensively.

    Raises:
        TypeError: ``handler`` is not a coroutine function. Every seam
            (FastMCP, the chat tool wrappers, the RAG agent) awaits the
            handler, so a sync handler would run its side effects and then
            fail on ``await`` at every call; refusing at wrap time keeps the
            contract loud.

    Raises (from the returned wrapper):
        AuditCaptureError: The ``tool.invoked`` write failed and the handler
            was **not** executed (fail-closed refusal), or the handler
            succeeded but the ``tool.completed`` write failed (the outcome
            cannot be attested). The failed storage error is chained as the
            cause.
    """
    if getattr(handler, "__audit_wrapped__", False):
        return handler
    if not inspect.iscoroutinefunction(handler):
        raise TypeError(
            f"audited_tool_handler requires an async handler; "
            f"'{getattr(handler, '__name__', handler)}' is not a coroutine function"
        )

    @functools.wraps(handler)
    async def audited(*args: Any, **kwargs: Any) -> Any:
        call = AuditToolCall(name=handler.__name__, args=_named_jsonable_args(handler, args, kwargs))
        model = current_model_info()
        target = AuditTarget(type=TOOL_INVOCATION_TARGET_TYPE, id=uuid4().hex)

        try:
            await record_event_now(
                ToolInvokedAuditEvent(outcome=AuditOutcome.SUCCESS, tool=call, model=model, target=target)
            )
        except SQLAlchemyError as exc:
            logger.exception("Audit 'tool.invoked' write failed; refusing tool '%s'", handler.__name__)
            raise AuditCaptureError("tool.invoked", handler.__name__) from exc
        _execution_recorded.set(True)
        try:
            result = await handler(*args, **kwargs)
        # NOTE: Kept broad intentionally: handlers are arbitrary plugin code
        # that can raise anything, the failure is recorded as the audit event
        # this except exists for, and the exception is always re-raised.
        except Exception as exc:
            try:
                await record_event_now(
                    ToolFailedAuditEvent(
                        outcome=AuditOutcome.FAILURE,
                        tool=call,
                        model=model,
                        target=target,
                        error_detail=scrub_error_detail(exc),
                    )
                )
            except SQLAlchemyError:
                # The invocation is already on record; a missing outcome event
                # is the abnormal-termination signal, so the handler's own
                # error must surface, not the audit store's.
                logger.exception("Audit 'tool.failed' write failed for tool '%s'", handler.__name__)
            raise
        try:
            await record_event_now(
                ToolCompletedAuditEvent(outcome=AuditOutcome.SUCCESS, tool=call, model=model, target=target)
            )
        except SQLAlchemyError as exc:
            logger.exception("Audit 'tool.completed' write failed for tool '%s'", handler.__name__)
            raise AuditCaptureError("tool.completed", handler.__name__) from exc
        return result

    # setattr keeps mypy strict happy: functions have no declared attributes.
    setattr(audited, "__audit_wrapped__", True)
    return audited


def _named_jsonable_args(handler: AsyncToolHandler, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Map the call's arguments to parameter names and JSON-native values.

    Positional arguments are named via the handler's signature so the recorded
    payload is stable however the seam invoked the handler; if binding fails
    (the call would TypeError anyway) positional values are kept under
    ``__args__`` rather than dropped.
    """
    if args:
        try:
            named = dict(inspect.signature(handler).bind_partial(*args, **kwargs).arguments)
        except TypeError:
            named = {"__args__": list(args), **kwargs}
    else:
        named = dict(kwargs)
    return {key: _jsonable(value, MAX_DEPTH) for key, value in named.items()}


def _jsonable(value: Any, depth: int) -> Any:
    """Reduce ``value`` to JSON-native types for redaction and canonicalization.

    Pydantic models are dumped (so nested credential fields stay visible to the
    redactor as mappings), containers recurse with the same depth bound the
    redactor uses, and anything else non-native falls back to ``str`` (an
    audit record of an odd value beats a refused tool call).
    """
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json"), depth)
    if isinstance(value, Mapping):
        if depth <= 0:
            return REDACTED
        return {str(key): _jsonable(inner, depth - 1) for key, inner in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        if depth <= 0:
            return REDACTED
        return [_jsonable(item, depth - 1) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
