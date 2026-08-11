from typing import cast

from fastapi import APIRouter
from fastapi.routing import iter_route_contexts
from starlette.routing import BaseRoute

from sparkth.lib.plugins import SparkthPlugin

from . import hooks

PLUGIN_NAME_ATTRIBUTE = "__sparkth_plugin_name__"


def register_router(plugin: SparkthPlugin, router: APIRouter) -> None:
    """
    Register a router associated to a plugin.

    The plugin routes will automatically be prefixed with "/api/v1/<plugin-name>" and
    the plugin name will be associated to the route tags.
    """
    prefixed_router = APIRouter()
    prefixed_router.include_router(
        router,
        prefix=f"/api/v1/{plugin.name}",
        tags=[f"plugin:{plugin.name}", plugin.name],
    )

    # Associate each route to the plugin.
    #
    # Since FastAPI 0.140 include_router() no longer copies the sub-routes into
    # prefixed_router.routes: it appends a single lazy _IncludedRouter branch, which has no
    # .endpoint to stamp. iter_route_contexts flattens those branches back into the
    # underlying routes, so the attribute lands on the endpoints the app actually serves.
    for context in iter_route_contexts(prefixed_router.routes):
        endpoint = getattr(context.original_route, "endpoint", None)
        if endpoint is not None:
            setattr(endpoint, PLUGIN_NAME_ATTRIBUTE, plugin.name)

    hooks.PLUGIN_ROUTERS.add_item(plugin, prefixed_router)


def get_route_plugin_name(route: BaseRoute) -> str | None:
    """
    Get the plugin name associated to a route, if any.

    This is done based on the PLUGIN_NAME_ATTRIBUTE set on the route via register_router.
    """
    if endpoint := getattr(route, "endpoint", None):
        if plugin_name := getattr(endpoint, PLUGIN_NAME_ATTRIBUTE, None):
            return cast(str, plugin_name)
    return None
