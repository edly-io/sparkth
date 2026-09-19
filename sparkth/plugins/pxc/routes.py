"""The learner-facing surface, mounted at ``/api/v1/pxc``.

These requests carry no Sparkth session; the launch token in the query string authenticates them.

Every call into the PXC runtime is dispatched to a worker thread. The sandbox executes
WebAssembly synchronously on the calling thread, so running it inline would block the event
loop for every other request in the process.
"""

import asyncio
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
    """The activity socket's URL for this launch, as a browser must address it."""
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
    await publish_events(claims.activity, claims.placement, events)


@router.websocket("/ws")
async def activity_socket(websocket: WebSocket, token: str = Query()) -> None:
    """The socket an activity's client keeps open, to send actions and to receive events."""
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
        # Always, but not before every close: the frame loop's refusal paths close the socket
        # and then return into this clause, so a publish landing in that window still walks a
        # closed socket — L16's first defect. _SubscriberSocket absorbs the RuntimeError that
        # causes, which is what keeps the window harmless.
        EVENT_BUS.unsubscribe(claims.activity, subscriber)
