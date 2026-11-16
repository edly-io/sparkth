"""Guard: every plugin route is gated on ``plugin.use`` or deliberately listed as ungated."""

import re
from uuid import UUID, uuid4

from fastapi.routing import RouteContext, iter_route_contexts
from httpx import AsyncClient

from sparkth.core.models.user import User
from sparkth.core.routes import get_route_plugin_name
from sparkth.lib.testing import AuditEventsFetcher, assert_plugin_use_denied
from sparkth.main import app

WEBSOCKET = "WEBSOCKET"

UNGATED_PLUGIN_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/google-drive/oauth/callback"): "signed OAuth state, no user login",
    ("GET", "/api/v1/slack/oauth/callback"): "signed OAuth state, no user login",
    ("POST", "/api/v1/slack/events"): "Slack request signature",
    ("GET", "/api/v1/compose/analytics/activity"): "gated by analytics.read at the plugin scope",
    ("GET", "/api/v1/google-drive/analytics/documents"): "gated by analytics.read at the plugin scope",
    ("GET", "/api/v1/pxc/embed"): "PXC learner router: launch token",
    ("GET", "/api/v1/pxc/client/{file_name}"): "PXC learner router: launch token",
    ("GET", "/api/v1/pxc/assets/{file_path:path}"): "PXC learner router: launch token",
    ("POST", "/api/v1/pxc/actions/{action_name}"): "PXC learner router: launch token",
    ("OPTIONS", "/api/v1/pxc/actions/{action_name}"): "PXC learner router: launch token",
    (WEBSOCKET, "/ws"): "PXC learner router: launch token",
}


def list_plugin_routes() -> list[tuple[str, str, RouteContext]]:
    """Return (method, path template, context) for every plugin route; a WebSocket route has method WEBSOCKET."""
    routes = []
    for context in iter_route_contexts(app.routes):
        if get_route_plugin_name(context.original_route) is None:
            continue
        path = str(context.path or getattr(context.original_route, "path", ""))
        for method in sorted(context.methods or {WEBSOCKET}):
            if method != "HEAD":
                routes.append((method, path, context))
    return routes


def fill_path_params(path: str, context: RouteContext) -> str:
    """Fill each path parameter with a random UUID when typed as one, else with ``1``."""
    for param in context.dependant.path_params:
        value = str(uuid4()) if param.field_info.annotation is UUID else "1"
        path = re.sub(r"\{" + param.name + r"(:[a-z]+)?\}", value, path)
    return path


async def test_every_plugin_route_is_gated_or_listed(
    client: AsyncClient, current_user: User, audit_events: AuditEventsFetcher
) -> None:
    routes = list_plugin_routes()
    found = {(method, path) for method, path, _ in routes}
    assert set(UNGATED_PLUGIN_ROUTES) <= found, f"stale ungated entries: {set(UNGATED_PLUGIN_ROUTES) - found}"

    ungated = []
    for method, path, context in routes:
        if (method, path) in UNGATED_PLUGIN_ROUTES:
            continue
        response = await client.request(method, fill_path_params(path, context))
        if response.status_code != 403:
            ungated.append(f"{method} {path} -> {response.status_code}")
            continue
        await assert_plugin_use_denied(audit_events, get_route_plugin_name(context.original_route) or "")
    assert not ungated, "plugin routes not gated on plugin.use (add a gate or list with a reason):\n" + "\n".join(
        ungated
    )
