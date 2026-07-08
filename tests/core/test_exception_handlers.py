import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

from sparkth.core.exception_handlers import EXCEPTION_HANDLERS
from sparkth.lib.exception_handlers import (
    ExceptionHandler,
    register_exception_handler,
    register_status,
    status_handler,
)
from sparkth.lib.hooks import TypeKeyedHook
from sparkth.main import _register_exception_handlers, assemble_app


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


class _DomainError(Exception):
    pass


class _SpecificDomainError(_DomainError):
    pass


def _app_raising(exc: Exception, hook: TypeKeyedHook[ExceptionHandler]) -> FastAPI:
    """Build a bare app with one route that raises ``exc``, wired via ``hook``."""
    app = FastAPI()

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    _register_exception_handlers(app, hook=hook)
    return app


def test_registered_handler_renders_raised_exception() -> None:
    hook: TypeKeyedHook[ExceptionHandler] = TypeKeyedHook()
    register_status(_DomainError, 409, hook=hook)

    client = TestClient(_app_raising(_DomainError("already exists"), hook))
    response = client.get("/boom")

    assert response.status_code == 409
    assert response.json() == {"detail": "already exists"}


def test_handler_on_base_class_catches_subclass_via_mro() -> None:
    hook: TypeKeyedHook[ExceptionHandler] = TypeKeyedHook()
    register_status(_DomainError, 422, hook=hook)  # base registered

    client = TestClient(_app_raising(_SpecificDomainError("nope"), hook))  # subclass raised
    response = client.get("/boom")

    assert response.status_code == 422
    assert response.json() == {"detail": "nope"}


def test_custom_handler_can_read_exception_attributes() -> None:
    class _NotFound(Exception):
        def __init__(self, resource_id: int) -> None:
            super().__init__(f"missing {resource_id}")
            self.resource_id = resource_id

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, _NotFound)
        return JSONResponse(status_code=404, content={"resource_id": exc.resource_id})

    hook: TypeKeyedHook[ExceptionHandler] = TypeKeyedHook()
    register_exception_handler(_NotFound, handler, hook=hook)

    client = TestClient(_app_raising(_NotFound(7), hook))
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json() == {"resource_id": 7}


def test_global_registry_ships_empty() -> None:
    # Guards the scope line: this issue delivers the mechanism, not any mapping.
    assert list(EXCEPTION_HANDLERS.iter_items()) == []


def test_assemble_app_wires_handlers_from_global_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AssembleWiringProbe(Exception):
        pass

    # assemble_app() calls _register_exception_handlers(application) with no explicit
    # hook, so it uses the default parameter value, which was bound to the real
    # EXCEPTION_HANDLERS object at function-definition time. Patching a module-level
    # symbol wouldn't reach that already-bound default, so we inject directly into the
    # global hook's internal dict instead. monkeypatch.setitem removes the entry again
    # on teardown, keeping this isolated from test_global_registry_ships_empty.
    monkeypatch.setitem(EXCEPTION_HANDLERS._items, _AssembleWiringProbe, status_handler(599))

    app = assemble_app()

    assert _AssembleWiringProbe in app.exception_handlers
