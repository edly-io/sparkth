"""Tests for plugin route registration in ``sparkth.core.routes``."""

from typing import Awaitable, Callable

from fastapi import APIRouter
from fastapi.routing import iter_route_contexts

from sparkth.core.routes import get_route_plugin_name, register_router
from sparkth.core.routes.hooks import PLUGIN_ROUTERS
from sparkth.lib.plugins import SparkthPlugin


async def _ping() -> dict[str, str]:
    """Endpoint stood up purely so the router has a route to stamp."""
    return {"status": "ok"}


async def _pong() -> dict[str, str]:
    """Second endpoint so each test stamps its own function object."""
    return {"status": "ok"}


def _plugin_router(endpoint: Callable[[], Awaitable[dict[str, str]]]) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/ping", endpoint, methods=["GET"])
    return router


def _registered_router(plugin: SparkthPlugin) -> APIRouter:
    routers = {registered: router for registered, router in PLUGIN_ROUTERS.iter_items()}
    return routers[plugin]


def test_register_router_stamps_the_plugin_name_on_its_routes() -> None:
    # The stamp is what PluginAccessMiddleware reads to decide which plugin owns a URL, so a
    # router whose routes carry no plugin name leaves the per-user access gate with nothing
    # to enforce. iter_route_contexts flattens the lazy _IncludedRouter branch include_router
    # appends (FastAPI 0.140+) back into the underlying routes.
    plugin = SparkthPlugin("stamp-test")
    register_router(plugin, _plugin_router(_ping))

    contexts = list(iter_route_contexts(_registered_router(plugin).routes))

    assert [get_route_plugin_name(context.original_route) for context in contexts] == ["stamp-test"]


def test_register_router_prefixes_routes_with_the_plugin_namespace() -> None:
    plugin = SparkthPlugin("prefix-test")
    register_router(plugin, _plugin_router(_pong))

    paths = [context.path for context in iter_route_contexts(_registered_router(plugin).routes)]

    assert paths == ["/api/v1/prefix-test/ping"]
