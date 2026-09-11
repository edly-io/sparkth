"""The learner-facing surface, mounted at ``/api/v1/pxc``.

These requests carry no Sparkth session. They arrive from a learner's browser inside another
LMS's course page, and the launch token in the query string is what authenticates them — which
is why they pass the plugin access gate untouched: it fails open for anonymous callers by
design. The WebSocket route authenticates the same way, and bypasses that gate for a second
reason too: the gate is HTTP middleware, so non-HTTP ASGI scopes never reach it (L15).

Actions arrive over the socket, and the events they produce are published to every subscriber
the event addresses rather than returned to the caller — so an action by one learner can update
another learner's view. The POST action route exists for payloads above the client's 512 KiB
socket ceiling and publishes the same way.

Every call into the PXC runtime is dispatched to a worker thread. The sandbox executes
WebAssembly synchronously on the calling thread, so running it inline would block the event
loop for every other request in the process.
"""

import asyncio
from json import JSONDecodeError
from pathlib import Path

import pxc.lib
from fastapi import APIRouter, Depends, Query, Request, WebSocket, status
from fastapi.responses import FileResponse, HTMLResponse
from starlette.websockets import WebSocketDisconnect

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import asset_path
from sparkth.plugins.pxc.event_bus import EVENT_BUS, publish_events, subscribe_socket
from sparkth.plugins.pxc.exceptions import (
    PxcActionRejected,
    PxcActivityNotFound,
    PxcAssetNotFound,
    PxcInvalidLaunchToken,
)
from sparkth.plugins.pxc.runtime import build_runtime, read_state, run_action
from sparkth.plugins.pxc.schemas import ActivityConfig, LaunchContext
from sparkth.plugins.pxc.tokens import LaunchClaims, read_launch_token
from sparkth.plugins.pxc.websocket import run_action_frames

logger = get_logger(__name__)

# The launch token is the only credential these routes have, so verifying it is declared as a
# dependency rather than repeated as the first line of each handler. Two routes do not declare
# it: `client_script`, which serves the same two scripts to everyone and reads no state, and
# `activity_socket`, which has to turn a refusal into a close code and so verifies inline.
router = APIRouter()

# The two client scripts the activity page loads: PXC's own component, served from the installed
# pxc-lib distribution, and Sparkth's subclass of it. An explicit map rather than a directory: it
# is the whole allowlist, so no path can escape it.
_CLIENT_FILES = {
    "pxc.js": Path(pxc.lib.__file__).parent / "static" / "js" / "pxc.js",
    "sparkth-pxc.js": Path(__file__).parent / "static" / "sparkth-pxc.js",
}


@router.get("/embed", response_class=HTMLResponse, dependencies=[Depends(read_launch_token)])
async def embed_activity(request: Request, token: str = Query()) -> HTMLResponse:
    """The document an LMS iframes to show one activity to one learner.

    Gated by the dependency rather than a claims parameter: the shell hands the raw token to the
    client and reads nothing out of it.
    """
    base = str(request.url_for("embed_activity")).rsplit("/embed", 1)[0]
    return HTMLResponse(
        "<!DOCTYPE html>"
        '<html><head><meta charset="utf-8"><style>body{margin:0}</style></head>'
        "<body>"
        f'<pxc-activity data-config-url="{base}/config?token={token}"'
        f' data-action-url="{base}/actions" data-pxc-token="{token}"></pxc-activity>'
        f'<script type="module" src="{base}/client/sparkth-pxc.js"></script>'
        "</body></html>"
    )


def _socket_url(request: Request, token: str) -> str:
    """The activity socket's URL for this launch, as a browser must address it.

    ``activity_socket`` is a WebSocket route, so ``request.url_for`` already resolves it to the
    ``ws``/``wss`` scheme a browser's ``WebSocket`` constructor needs, translating from whatever
    scheme this very request arrived on (``starlette.datastructures.URLPath.make_absolute_url``
    maps ``http``/``https`` to ``ws``/``wss`` by ``base_url.is_secure``) — there is no ``http``/
    ``https`` URL to convert here, and no scheme comparison to get backwards. ``https`` becomes
    ``wss`` rather than ``ws``, or the handshake would be refused on any TLS deployment.
    """
    return f"{request.url_for('activity_socket')}?token={token}"


@router.get("/config")
async def activity_config(
    request: Request, claims: LaunchClaims = Depends(read_launch_token), token: str = Query()
) -> ActivityConfig:
    """This activity's state, context and asset URLs for the launching learner.

    Takes the raw token as well as the claims, because the URLs it hands back carry it.
    """
    runtime = await asyncio.to_thread(build_runtime, claims)
    state = await asyncio.to_thread(read_state, runtime)
    base = str(request.url_for("activity_config")).rsplit("/config", 1)[0]
    # Neither base URL below carries the token: the embed shell already gave the client one,
    # and the client appends it itself in SparkthPXC's methods. ui_url and ws_url do carry one,
    # because pxc.js uses each directly with nothing appending a token afterward.
    return ActivityConfig(
        activity=claims.activity,
        context=LaunchContext(activity_id=claims.placement, course_id=claims.course_id, user_id=claims.user_id),
        permission=runtime.permission.value,
        state=dict(state),
        ui_url=f"{base}/assets/{runtime.ui_path}?token={token}",
        asset_base_url=f"{base}/assets",
        action_base_url=f"{base}/actions",
        ws_url=_socket_url(request, token),
    )


@router.get("/client/{file_name}")
async def client_script(file_name: str) -> FileResponse:
    """Serve one of the client scripts the activity page loads.

    Raises:
        PxcAssetNotFound: if ``file_name`` is not one of them.
    """
    path = _CLIENT_FILES.get(file_name)
    if path is None:
        raise PxcAssetNotFound(f"Unknown client script: {file_name}")
    return FileResponse(path, media_type="text/javascript")


@router.get("/assets/{file_path:path}")
async def activity_asset(file_path: str, claims: LaunchClaims = Depends(read_launch_token)) -> FileResponse:
    """Serve the activity's UI script or one of its declared assets.

    Resolved from the manifest, not from a runtime. Which learner is asking does not change
    where a file lives, and building a runtime to answer would create the activity's state file
    and run its schema on every asset of every page load.

    Raises:
        PxcAssetNotFound: if the manifest does not declare the file, or it is missing.
    """
    return FileResponse(asset_path(claims.activity, file_path))


@router.post("/actions/{action_name}", status_code=status.HTTP_204_NO_CONTENT)
async def submit_action(action_name: str, request: Request, claims: LaunchClaims = Depends(read_launch_token)) -> None:
    """Run one action through the activity's sandbox, for a payload too large for the socket.

    ``pxc.js`` sends actions over the socket and falls back to this route above 512 KiB, since
    uvicorn closes an inbound frame over 1 MiB before the server can read it. The events the
    action produces are published to the bus, exactly as the socket path publishes them —
    returning them here would send them nowhere, because the client reads only the response's
    status.

    The request body is read as a raw JSON value, not a typed model, by design: an action's
    value is a manifest-defined ``FieldType``, a JSON union no Pydantic model can express
    generically, so the body is deliberately untyped rather than accidentally so.

    Raises:
        PxcActionRejected: if the body is not valid JSON.
    """
    try:
        action_value = await request.json()
    except JSONDecodeError as err:
        logger.warning("Malformed action body for %s of activity %s: %s", action_name, claims.activity, err)
        raise PxcActionRejected("Request body is not valid JSON") from err
    runtime = await asyncio.to_thread(build_runtime, claims)
    events = await asyncio.to_thread(run_action, runtime, action_name, action_value)
    await publish_events(claims.activity, claims.placement, events)


@router.websocket("/ws")
async def activity_socket(websocket: WebSocket, token: str = Query()) -> None:
    """The socket an activity's client keeps open, to send actions and to receive events.

    The events an action produces reach every subscriber that action addresses, not only the
    client that sent it, which is what lets one learner's move update another's view. This
    route only authenticates the launch and manages the subscription's lifecycle;
    ``run_action_frames`` owns every frame from there.

    Refusals are close codes rather than HTTP statuses: this plugin's registered exception
    handlers render only for HTTP requests, so a domain exception raised from here would render
    nothing and the socket would simply fail.
    """
    try:
        claims = read_launch_token(token)
        runtime = await asyncio.to_thread(build_runtime, claims)
    except (PxcInvalidLaunchToken, PxcActivityNotFound) as err:
        logger.warning("Refused a PXC activity socket: %s", err)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    subscriber = subscribe_socket(claims.activity, websocket, claims)
    try:
        await run_action_frames(websocket, runtime, token)
    except WebSocketDisconnect:
        # The ordinary way a socket ends: the learner navigated away or closed the tab.
        pass
    finally:
        # Before any close: publish() walks this list and a closed socket still in it is what
        # L16's first defect trips over.
        EVENT_BUS.unsubscribe(claims.activity, subscriber)
