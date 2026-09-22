"""The activity socket's frame loop: what arrives on the socket, and what it causes."""

import asyncio
from typing import Any

from fastapi import status
from pxc.lib.fields import FieldType
from pxc.lib.runtime import ActivityRuntime
from starlette.websockets import WebSocket

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.event_bus import publish_events
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcInvalidLaunchToken, PxcSandboxFailure
from sparkth.plugins.pxc.runtime import run_action
from sparkth.plugins.pxc.tokens import read_launch_token

logger = get_logger(__name__)


async def run_action_frames(websocket: WebSocket, runtime: ActivityRuntime, token: str) -> None:
    """Read and run action frames until the client goes away or sends one that cannot be run.

    Raises:
        WebSocketDisconnect: when the client goes away, which is this loop's normal exit.
    """
    while True:
        frame = await _read_action_frame(websocket, runtime)
        if frame is None:
            return

        try:
            await _run_one_action(runtime, token, frame)
        except PxcInvalidLaunchToken as err:
            logger.warning(
                "Closing a PXC socket whose token no longer verifies on %s (placement=%s): %s",
                runtime.name,
                runtime.activity_id,
                err,
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        except PxcActionRejected as err:
            # A client bug, not a connection fault: the socket stays open.
            logger.warning(
                "Rejected a PXC socket action %s on %s (placement=%s): %s",
                frame["action"],
                runtime.name,
                runtime.activity_id,
                err,
            )
        except PxcSandboxFailure as err:
            # The activity's fault, not the connection's: the socket stays open.
            logger.error(
                "PXC sandbox failed running socket action %s on %s (placement=%s): %s",
                frame["action"],
                runtime.name,
                runtime.activity_id,
                err,
            )


async def _read_action_frame(websocket: WebSocket, runtime: ActivityRuntime) -> dict[str, Any] | None:
    """The next runnable action frame, or ``None`` once the socket has been closed as unusable.

    ``None`` means the socket is closed and the caller must stop, never skip on to the next frame.

    Raises:
        WebSocketDisconnect: when the client goes away, before a frame is read.
    """
    try:
        frame = await websocket.receive_json()
    except (ValueError, KeyError, RecursionError) as err:
        # The stack has unwound by the time close() runs, so there is headroom to send it.
        # Logged with %r so the exception type says which cause arrived.
        logger.warning(
            "Refusing a PXC socket frame the loop cannot read as JSON text on %s (placement=%s): %r",
            runtime.name,
            runtime.activity_id,
            err,
        )
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return None

    if not isinstance(frame, dict) or "action" not in frame:
        logger.warning(
            "Refusing a PXC socket frame with no action on %s (placement=%s)",
            runtime.name,
            runtime.activity_id,
        )
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return None

    return frame


async def _run_one_action(runtime: ActivityRuntime, token: str, frame: dict[str, Any]) -> None:
    """Run one frame's action through the sandbox and fan out the events it produced.

    A frame supplies only the action's name and value; permission and context come from the
    signed claims, re-verified here so an action after the token lapses does not take effect.

    Raises:
        PxcInvalidLaunchToken: if the token no longer verifies.
        PxcActionRejected: if the manifest does not accept this action or value.
        PxcSandboxFailure: if the sandbox itself failed.
    """
    claims = read_launch_token(token)
    action_name = str(frame["action"])
    action_value: FieldType = frame.get("value", "")
    events = await asyncio.to_thread(run_action, runtime, action_name, action_value)
    await publish_events(claims.activity, claims.placement, events)
