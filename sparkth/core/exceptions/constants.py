"""Constants for the exception → HTTP response registry.

This module was generated with LLM (Claude) assistance.

Internal to :mod:`sparkth.core.exceptions`; nothing here is re-exported through the
:mod:`sparkth.lib.exceptions` public surface.
"""

from fastapi.exceptions import RequestValidationError, WebSocketRequestValidationError
from starlette.exceptions import HTTPException

# Types FastAPI ships default handlers for; ``fastapi.HTTPException`` subclasses the Starlette one.
FRAMEWORK_HANDLED_EXCEPTIONS: tuple[type[Exception], ...] = (
    HTTPException,
    RequestValidationError,
    WebSocketRequestValidationError,
)
