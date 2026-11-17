"""Guard: every plugin route is gated on ``plugin.use`` or deliberately listed as ungated."""

from uuid import UUID, uuid4

import pytest
from fastapi.dependencies.utils import get_flat_dependant
from fastapi.routing import RouteContext, iter_route_contexts
from httpx import AsyncClient

from sparkth.core.models.user import User
from sparkth.core.routes import get_route_plugin_name
from sparkth.lib.testing import AuditEventsFetcher, assert_plugin_use_denied
from sparkth.main import app
from sparkth.plugins.googledrive.constants import GOOGLE_DRIVE_PLUGIN_NAME

WEBSOCKET = "WEBSOCKET"

UNGATED_PLUGIN_ROUTES: dict[tuple[str, str], str] = {
    ("GET", f"/api/v1/{GOOGLE_DRIVE_PLUGIN_NAME}/oauth/callback"): "signed OAuth state, no user login",
    ("GET", "/api/v1/slack/oauth/callback"): "signed OAuth state, no user login",
    ("POST", "/api/v1/slack/events"): "Slack request signature",
    ("GET", "/api/v1/compose/analytics/activity"): "gated by analytics.read at the plugin scope",
    ("GET", f"/api/v1/{GOOGLE_DRIVE_PLUGIN_NAME}/analytics/documents"): "gated by analytics.read at the plugin scope",
    ("GET", "/api/v1/pxc/embed"): "PXC learner router: launch token",
    ("GET", "/api/v1/pxc/client/{file_name}"): "PXC learner router: launch token",
    ("GET", "/api/v1/pxc/assets/{file_path:path}"): "PXC learner router: launch token",
    ("POST", "/api/v1/pxc/actions/{action_name}"): "PXC learner router: launch token",
    ("OPTIONS", "/api/v1/pxc/actions/{action_name}"): "PXC learner router: launch token",
    (WEBSOCKET, "/api/v1/pxc/ws"): "PXC learner router: launch token",
}


def list_plugin_routes() -> list[tuple[str, str, str, RouteContext]]:
    """Return (method, path template, plugin name, context) for every plugin route; a WebSocket has method WEBSOCKET."""
    routes = []
    for context in iter_route_contexts(app.routes):
        plugin_name = get_route_plugin_name(context.original_route)
        if plugin_name is None:
            continue
        path = str(context.path or context.starlette_route.path)
        for method in sorted(context.methods or {WEBSOCKET}):
            if method != "HEAD":
                routes.append((method, path, plugin_name, context))
    return routes


def fill_path_params(context: RouteContext) -> str:
    """Return the route's path with every parameter filled: a random UUID where typed UUID, else ``1``."""
    typed = get_flat_dependant(context.dependant).path_params
    uuid_params = {param.name for param in typed if param.field_info.annotation is UUID}
    values = {name: str(uuid4()) if name in uuid_params else "1" for name in context.param_convertors}
    return str(context.url_path_for(context.name, **values))


PLUGIN_ROUTES = list_plugin_routes()
GATED_ROUTES = [route for route in PLUGIN_ROUTES if route[:2] not in UNGATED_PLUGIN_ROUTES]


def test_every_ungated_entry_names_a_real_route() -> None:
    found = {(method, path) for method, path, _, _ in PLUGIN_ROUTES}
    assert set(UNGATED_PLUGIN_ROUTES) <= found, f"stale ungated entries: {set(UNGATED_PLUGIN_ROUTES) - found}"
    assert GATED_ROUTES


@pytest.mark.parametrize(
    ("method", "path", "plugin_name", "context"),
    GATED_ROUTES,
    ids=[f"{method} {path}" for method, path, _, _ in GATED_ROUTES],
)
async def test_plugin_route_is_gated_on_plugin_use(
    method: str,
    path: str,
    plugin_name: str,
    context: RouteContext,
    client: AsyncClient,
    current_user: User,
    audit_events: AuditEventsFetcher,
) -> None:
    if method == WEBSOCKET:
        pytest.fail("WebSocket routes cannot be gated: list it in UNGATED_PLUGIN_ROUTES with a reason")
    url = fill_path_params(context)
    assert "{" not in url
    response = await client.request(method, url)
    assert response.status_code == 403, "add a plugin.use gate or list the route in UNGATED_PLUGIN_ROUTES"
    await assert_plugin_use_denied(audit_events, plugin_name)
