import pytest

from sparkth.lib.exception_handlers import (
    ExceptionHandler,
    register_exception_handler,
    register_status,
    status_handler,
)
from sparkth.lib.hooks import TypeKeyedHook


def test_register_status_adds_handler_to_injected_hook() -> None:
    hook: TypeKeyedHook[ExceptionHandler] = TypeKeyedHook()

    register_status(ValueError, 422, hook=hook)

    assert list(dict(hook.iter_items())) == [ValueError]


def test_register_exception_handler_adds_handler_to_injected_hook() -> None:
    hook: TypeKeyedHook[ExceptionHandler] = TypeKeyedHook()

    register_exception_handler(KeyError, status_handler(404), hook=hook)

    assert list(dict(hook.iter_items())) == [KeyError]


def test_register_status_rejects_duplicate_type() -> None:
    hook: TypeKeyedHook[ExceptionHandler] = TypeKeyedHook()
    register_status(ValueError, 409, hook=hook)

    with pytest.raises(ValueError, match="Duplicate hook item for type"):
        register_status(ValueError, 400, hook=hook)
