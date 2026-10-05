"""The learner-facing surface, mounted at ``/api/v1/pxc``.

These requests carry no Sparkth session; the launch token in the query string authenticates them.
The author's own session-authenticated routes live in ``routes.activities``.

Every call into the PXC runtime is dispatched to a worker thread. The sandbox executes
WebAssembly synchronously on the calling thread, so running it inline would block the event
loop for every other request in the process.
"""

import asyncio
from pathlib import Path

import pxc.lib
from fastapi import APIRouter, Depends, Query, Request, Response, WebSocket, status
from fastapi.responses import FileResponse, HTMLResponse
from starlette.websockets import WebSocketDisconnect

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import asset_path
from sparkth.plugins.pxc.constants import (
    PXC_CLOSE_ACTIVITY_NOT_FOUND,
    PXC_CLOSE_INVALID_TOKEN,
    PXC_CORS_HEADERS,
    PXC_PREFLIGHT_HEADERS,
    PXC_SANDBOX_HEADERS,
)
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

# Every route authenticates by launch token, except the public client scripts and the preflight.
router = APIRouter()

# Allowlist of the client scripts the activity page loads.
_CLIENT_FILES = {
    "pxc.js": Path(pxc.lib.__file__).parent / "static" / "js" / "pxc.js",
    "sparkth-pxc.js": Path(__file__).parent.parent / "static" / "sparkth-pxc.js",
}


@router.get("/embed", response_class=HTMLResponse)
async def embed_activity(
    request: Request, claims: LaunchClaims = Depends(read_launch_token), token: str = Query()
) -> HTMLResponse:
    """The document an LMS iframes to show one activity to one learner.

    The activity's configuration is inlined as a JSON script element, so the client reads it
    without a request of its own.

    Served under a sandbox CSP, so the document has an opaque origin however it is opened, and
    activity code in it cannot reach Sparkth's own storage.
    """
    config_json = (await _activity_config(claims, token, request)).model_dump_json().replace("<", "\\u003c")
    client_url = request.url_for("client_script", file_name="sparkth-pxc.js")
    return HTMLResponse(
        "<!DOCTYPE html>"
        '<html><head><meta charset="utf-8"><style>body{margin:0}</style></head>'
        "<body>"
        f'<pxc-activity data-pxc-token="{token}">'
        f'<script type="application/json">{config_json}</script></pxc-activity>'
        f'<script type="module" src="{client_url}"></script>'
        "</body></html>",
        headers=PXC_SANDBOX_HEADERS,
    )


async def _activity_config(claims: LaunchClaims, token: str, request: Request) -> ActivityConfig:
    """This activity's state, context and asset URLs for the launching learner.

    Takes the raw token as well as the claims, because the URLs it hands back carry it.
    """
    runtime = await asyncio.to_thread(build_runtime, claims)
    state = await asyncio.to_thread(read_state, runtime)
    base = str(request.url_for("embed_activity")).rsplit("/embed", 1)[0]
    # ui_url and ws_url carry the token; the two base URLs do not, because the client appends the
    # page's data-pxc-token itself in SparkthPXC's methods.
    return ActivityConfig(
        activity=claims.activity,
        context=LaunchContext(activity_id=claims.activity_instance, course_id=claims.course_id, user_id=claims.user_id),
        permission=runtime.permission.value,
        state=dict(state),
        ui_url=f"{base}/assets/{runtime.ui_path}?token={token}",
        asset_base_url=f"{base}/assets",
        action_base_url=f"{base}/actions",
        ws_url=f"{request.url_for('activity_socket')}?token={token}",
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
    return FileResponse(path, media_type="text/javascript", headers=PXC_CORS_HEADERS)


@router.get("/assets/{file_path:path}")
async def activity_asset(file_path: str, claims: LaunchClaims = Depends(read_launch_token)) -> FileResponse:
    """Serve the activity's UI script or one of its declared assets.

    Resolved from the manifest, not from a runtime. Which learner is asking does not change
    where a file lives, and building a runtime to answer would create the activity's state file
    and run its schema on every asset of every page load.

    Raises:
        PxcAssetNotFound: if the manifest does not declare the file, or it is missing.
    """
    return FileResponse(asset_path(claims.activity, file_path), headers=PXC_CORS_HEADERS | PXC_SANDBOX_HEADERS)


@router.post("/actions/{action_name}", status_code=status.HTTP_204_NO_CONTENT)
async def submit_action(
    action_name: str, request: Request, claims: LaunchClaims = Depends(read_launch_token)
) -> Response:
    """Run one action through the activity's sandbox, for a payload too large for the socket.

    The events it produces are published to the bus, not returned; the client reads only the status.

    Raises:
        PxcActionRejected: if the body is not JSON the parser will read.
    """
    try:
        action_value = await request.json()
    except (ValueError, RecursionError) as err:
        # Logged with %r so the exception type says which cause arrived.
        logger.warning(
            "Refusing a PXC action body the parser cannot read for %s of activity %s: %r",
            action_name,
            claims.activity,
            err,
        )
        raise PxcActionRejected("Request body is not JSON this server can read") from err
    runtime = await asyncio.to_thread(build_runtime, claims)
    events = await asyncio.to_thread(run_action, runtime, action_name, action_value)
    await publish_events(claims.activity, claims.activity_instance, events)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=PXC_CORS_HEADERS)


@router.options("/actions/{action_name}", include_in_schema=False)
async def preflight_action() -> Response:
    """Answer the preflight a browser sends before a cross-origin action POST with a JSON body."""
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=PXC_PREFLIGHT_HEADERS)


@router.websocket("/ws")
async def activity_socket(websocket: WebSocket, token: str = Query()) -> None:
    """The socket an activity's client keeps open, to send actions and to receive events."""
    try:
        claims = read_launch_token(token)
        runtime = await asyncio.to_thread(build_runtime, claims)
    except (PxcInvalidLaunchToken, PxcActivityNotFound) as err:
        logger.warning("Refused a PXC activity socket: %s", err)
        # Accepted first: a browser sees the close code only after a completed handshake.
        await websocket.accept()
        invalid_token = isinstance(err, PxcInvalidLaunchToken)
        await websocket.close(code=PXC_CLOSE_INVALID_TOKEN if invalid_token else PXC_CLOSE_ACTIVITY_NOT_FOUND)
        return

    await websocket.accept()
    subscriber = subscribe_socket(claims.activity, websocket, claims)
    try:
        await run_action_frames(websocket, runtime, token)
    except WebSocketDisconnect:
        # The ordinary way a socket ends: the learner navigated away or closed the tab.
        pass
    finally:
        # Refusal paths close the socket before reaching here, so a publish can still hit a
        # closed socket. _SubscriberSocket absorbs the resulting RuntimeError.
        EVENT_BUS.unsubscribe(claims.activity, subscriber)
