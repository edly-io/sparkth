"""Public API for the exception → HTTP mapping mechanism.

This module was generated with LLM (Claude) assistance.

Core and plugins register how a domain exception renders as an HTTP response from here,
never from ``sparkth.core.exception_handlers``. Use ``register_status`` for the common
type→status case, ``register_exception_handler`` for a custom handler, and ``status_handler``
to build the standard ``{"detail": str(exc)}`` responder. Implementation lives in
``sparkth/core/exception_handlers.py``.
"""

from sparkth.core.exception_handlers import (
    ExceptionHandler,
    register_exception_handler,
    register_status,
    status_handler,
)

__all__ = [
    "ExceptionHandler",
    "register_exception_handler",
    "register_status",
    "status_handler",
]
