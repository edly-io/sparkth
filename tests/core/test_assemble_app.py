"""Tests for the DB-free app factory in sparkth.main (assemble_app)."""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from sparkth.main import app, assemble_app

PLUGIN_SENTINEL_PATHS = [
    "/api/v1/chat/completions",
    "/api/v1/slack/oauth/status",
    "/api/v1/google-drive/oauth/status",
]


def _route_paths(application: FastAPI) -> set[str]:
    return {route.path for route in application.routes if isinstance(route, APIRoute)}


def test_assemble_app_includes_core_routes() -> None:
    assert "/api/v1/auth/login" in _route_paths(assemble_app())


@pytest.mark.parametrize("path", PLUGIN_SENTINEL_PATHS)
def test_assemble_app_includes_plugin_routes(path: str) -> None:
    assert path in _route_paths(assemble_app())


@pytest.mark.parametrize("path", PLUGIN_SENTINEL_PATHS)
def test_module_level_app_has_plugin_routes_without_lifespan(path: str) -> None:
    """The lifespan never runs in tests, so plugin routes must exist at import time."""
    assert path in _route_paths(app)


def test_assemble_app_is_db_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression guard: assembling the app must never reach for the database."""

    def _explode(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("assemble_app must not touch the database")

    # Patch the consumer binding (sparkth.main imports it by value) plus the
    # defining modules, so both existing references and future lazy imports trip.
    monkeypatch.setattr("sparkth.main.get_plugin_service", _explode)
    monkeypatch.setattr("sparkth.lib.db.get_async_session", _explode)
    monkeypatch.setattr("sparkth.lib.db.session_scope", _explode)
    monkeypatch.setattr("sparkth.services.plugin.get_plugin_service", _explode)

    assert _route_paths(assemble_app())


def test_openapi_schema_contains_plugin_endpoints() -> None:
    """The OpenAPI dump script relies on the full schema being derivable offline."""
    schema = assemble_app().openapi()
    for path in PLUGIN_SENTINEL_PATHS:
        assert path in schema["paths"]
