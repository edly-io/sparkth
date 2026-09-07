"""The learner-facing HTTP surface, mounted at ``/api/v1/pxc``.

These requests carry no Sparkth session. They arrive from a learner's browser inside another
LMS's course page, and the launch token in the query string is what authenticates them — which
is why they pass the plugin access gate untouched: it fails open for anonymous callers by
design.

Every call into the PXC runtime is dispatched to a worker thread. The sandbox executes
WebAssembly synchronously on the calling thread, so running it inline would block the event
loop for every other request in the process.
"""

import asyncio
from pathlib import Path

import pxc.lib
from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pxc.lib.runtime import AssetAccessError

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.exceptions import PxcAssetNotFound
from sparkth.plugins.pxc.runtime import build_runtime, read_state, run_action
from sparkth.plugins.pxc.schemas import ActionResult, ActivityConfig, LaunchContext
from sparkth.plugins.pxc.tokens import read_launch_token

logger = get_logger(__name__)

router = APIRouter()

# The two client scripts the activity page loads: PXC's own component, served from the installed
# pxc-lib distribution, and Sparkth's HTTP transport subclass of it. An explicit map rather than
# a directory: it is the whole allowlist, so no path can escape it.
_CLIENT_FILES = {
    "pxc.js": Path(pxc.lib.__file__).parent / "static" / "js" / "pxc.js",
    "sparkth-pxc.js": Path(__file__).parent / "static" / "sparkth-pxc.js",
}


@router.get("/embed", response_class=HTMLResponse)
async def embed_activity(request: Request, token: str = Query()) -> HTMLResponse:
    """The document an LMS iframes to show one activity to one learner."""
    read_launch_token(token)
    base = str(request.url_for("embed_activity")).rsplit("/embed", 1)[0]
    return HTMLResponse(
        "<!DOCTYPE html>"
        '<html><head><meta charset="utf-8"><style>body{margin:0}</style></head>'
        "<body>"
        f'<pxc-activity data-config-url="{base}/config?token={token}"'
        f' data-action-url="{base}/actions"></pxc-activity>'
        f'<script type="module" src="{base}/client/sparkth-pxc.js"></script>'
        "</body></html>"
    )


@router.get("/config")
async def activity_config(request: Request, token: str = Query()) -> ActivityConfig:
    """This activity's state, context and asset URLs for the launching learner."""
    claims = read_launch_token(token)
    runtime = await asyncio.to_thread(build_runtime, claims)
    state = await asyncio.to_thread(read_state, runtime)
    base = str(request.url_for("activity_config")).rsplit("/config", 1)[0]
    return ActivityConfig(
        activity=claims.activity,
        context=LaunchContext(activity_id=claims.placement, course_id=claims.course_id, user_id=claims.user_id),
        permission=runtime.permission.value,
        state=dict(state),
        ui_url=f"{base}/assets/{runtime.ui_path}?token={token}",
        asset_base_url=f"{base}/assets",
        action_base_url=f"{base}/actions",
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
async def activity_asset(file_path: str, token: str = Query()) -> FileResponse:
    """Serve the activity's UI script or one of its declared assets.

    Raises:
        PxcAssetNotFound: if the manifest does not declare the file, or it is missing.
    """
    claims = read_launch_token(token)
    runtime = await asyncio.to_thread(build_runtime, claims)
    try:
        if file_path == runtime.ui_path:
            path = runtime.get_ui_path()
        else:
            path = runtime.get_asset_path(file_path)
    except AssetAccessError as err:
        logger.warning("Refused asset %s of activity %s: %s", file_path, claims.activity, err)
        raise PxcAssetNotFound(f"No such asset: {file_path}") from err
    return FileResponse(path)


@router.post("/actions/{action_name}")
async def submit_action(action_name: str, request: Request, token: str = Query()) -> ActionResult:
    """Run one action through the activity's sandbox and return the events it produced.

    The request body is read as a raw JSON value, not a typed model, by design: an action's
    value is a manifest-defined ``FieldType``, a JSON union no Pydantic model can express
    generically, so the body is deliberately untyped rather than accidentally so.

    A sandbox crash during the action is swallowed upstream and comes back as a 200 with an
    empty event list, not an error — see ``run_action``'s docstring for why.
    """
    claims = read_launch_token(token)
    action_value = await request.json()
    runtime = await asyncio.to_thread(build_runtime, claims)
    events = await asyncio.to_thread(run_action, runtime, action_name, action_value)
    return ActionResult(events=[dict(event) for event in events])
