from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sparkth.core.exceptions.handlers import EXCEPTION_HANDLERS
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.main import _register_exception_handlers, assemble_app


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    """Isolate each test from the process-global EXCEPTION_HANDLERS registry.

    Registration always targets the global registry, so every test snapshots it on entry and
    restores it on exit — preserving the ships-empty invariant and avoiding duplicate-key
    collisions across tests.
    """
    snapshot = dict(EXCEPTION_HANDLERS._items)
    try:
        yield
    finally:
        EXCEPTION_HANDLERS._items.clear()
        EXCEPTION_HANDLERS._items.update(snapshot)


def test_register_exception_handler_registers_on_global_registry() -> None:
    register_exception_handler(ValueError, 422)

    assert ValueError in dict(EXCEPTION_HANDLERS.iter_values())


@pytest.mark.parametrize("status_code", [20, 200, 302, 600, 0, -1])
def test_register_exception_handler_rejects_non_error_status(status_code: int) -> None:
    with pytest.raises(ValueError, match="status_code"):
        register_exception_handler(ValueError, status_code)


def test_register_exception_handler_rejects_duplicate_type() -> None:
    register_exception_handler(ValueError, 409)

    with pytest.raises(ValueError, match="Duplicate hook item for key"):
        register_exception_handler(ValueError, 400)


class _DomainError(Exception):
    pass


class _SpecificDomainError(_DomainError):
    pass


def _app_raising(exc: Exception) -> FastAPI:
    """Build a bare app with one route that raises ``exc``, wired from the global registry."""
    app = FastAPI()

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    _register_exception_handlers(app)
    return app


def test_registered_handler_renders_raised_exception() -> None:
    register_exception_handler(_DomainError, 409)

    client = TestClient(_app_raising(_DomainError("already exists")))
    response = client.get("/boom")

    assert response.status_code == 409
    assert response.json() == {"detail": "already exists"}


def test_handler_on_base_class_catches_subclass_via_mro() -> None:
    register_exception_handler(_DomainError, 422)  # base registered

    client = TestClient(_app_raising(_SpecificDomainError("nope")))  # subclass raised
    response = client.get("/boom")

    assert response.status_code == 422
    assert response.json() == {"detail": "nope"}


def test_global_registry_ships_empty() -> None:
    # Guards the scope: this issue delivers the mechanism, not any mapping.
    assert list(EXCEPTION_HANDLERS.iter_values()) == []


def test_assemble_app_wires_handlers_from_global_registry() -> None:
    class _AssembleWiringProbe(Exception):
        pass

    # assemble_app() calls _register_exception_handlers(application), which iterates the global
    # EXCEPTION_HANDLERS. Register a probe and confirm assemble_app wires it onto the app
    # (the _restore_registry fixture removes the probe afterwards).
    register_exception_handler(_AssembleWiringProbe, 418)

    app = assemble_app()

    assert _AssembleWiringProbe in app.exception_handlers
