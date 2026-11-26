"""The activity socket's frame loop: what arrives on the socket, and what it causes."""

from typing import Any

from fastapi import status
from pxc.lib.fields import FieldType
from pxc.lib.runtime import ActivityRuntime
from starlette.websockets import WebSocket

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.actions import perform_action
from sparkth.plugins.pxc.constants import (
    PXC_ACTION_FAILED,
    PXC_ACTION_REJECTED,
    PXC_CLOSE_ACTIVITY_NOT_FOUND,
    PXC_CLOSE_INVALID_TOKEN,
    PXC_CLOSE_NOT_PERMITTED,
)
from sparkth.plugins.pxc.exceptions import (
    PxcActionRejected,
    PxcActivityNotFound,
    PxcActivityNotPermitted,
    PxcInvalidLaunchToken,
    PxcSandboxFailure,
)
from sparkth.plugins.pxc.launch_access import require_launch_access
from sparkth.plugins.pxc.tokens import read_launch_token

logger = get_logger(__name__)

# The close code a refused socket gets, by the refusal.
SOCKET_REFUSAL_CODES: dict[type[Exception], int] = {
    PxcInvalidLaunchToken: PXC_CLOSE_INVALID_TOKEN,
    PxcActivityNotPermitted: PXC_CLOSE_NOT_PERMITTED,
    PxcActivityNotFound: PXC_CLOSE_ACTIVITY_NOT_FOUND,
}


def get_socket_refusal_code(refusal: Exception) -> int:
    """Return the close code for a refusal, the code of the nearest mapped class when it is a subclass of one.

    Raises:
        KeyError: if the refusal is not an instance of any mapped class.
    """
    for refusal_type, code in SOCKET_REFUSAL_CODES.items():
        if isinstance(refusal, refusal_type):
            return code
    raise KeyError(type(refusal))


async def run_action_frames(websocket: WebSocket, runtime: ActivityRuntime, token: str) -> None:
    """Read and run action frames until the client goes away or sends one that cannot be run.

    An action the manifest refuses, or whose sandbox fails, is answered on this socket with an error
    frame naming it; the socket stays open. A frame arriving after the token no longer verifies, the
    account no longer holds a permission that allows the launch, or the activity is gone, closes the
    socket with the code for that refusal.

    Raises:
        WebSocketDisconnect: when the client goes away, which is this loop's normal exit.
    """
    while True:
        frame = await _read_action_frame(websocket, runtime)
        if frame is None:
            return

        try:
            await _run_one_action(runtime, token, frame)
        except (PxcInvalidLaunchToken, PxcActivityNotPermitted, PxcActivityNotFound) as err:
            logger.warning(
                "Closing a PXC socket whose launch is no longer allowed on %s (activity_instance=%s): %s: %s",
                runtime.name,
                runtime.activity_id,
                type(err).__name__,
                err,
            )
            await websocket.close(code=get_socket_refusal_code(err))
            return
        except PxcActionRejected as err:
            # A client bug, not a connection fault: the socket stays open.
            logger.warning(
                "Rejected a PXC socket action %s on %s (activity_instance=%s): %s",
                frame["action"],
                runtime.name,
                runtime.activity_id,
                err,
            )
            await websocket.send_json({"error": PXC_ACTION_REJECTED, "action": str(frame["action"])})
        except PxcSandboxFailure as err:
            # The activity's fault, not the connection's: the socket stays open.
            logger.error(
                "PXC sandbox failed running socket action %s on %s (activity_instance=%s): %s",
                frame["action"],
                runtime.name,
                runtime.activity_id,
                err.error_text,
            )
            await websocket.send_json({"error": PXC_ACTION_FAILED, "action": str(frame["action"])})


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
            "Refusing a PXC socket frame the loop cannot read as JSON text on %s (activity_instance=%s): %r",
            runtime.name,
            runtime.activity_id,
            err,
        )
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return None

    if not isinstance(frame, dict) or "action" not in frame:
        logger.warning(
            "Refusing a PXC socket frame with no action on %s (activity_instance=%s)",
            runtime.name,
            runtime.activity_id,
        )
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return None

    return frame


async def _run_one_action(runtime: ActivityRuntime, token: str, frame: dict[str, Any]) -> None:
    """Run one frame's action through the sandbox and fan out the events it produced.

    A frame supplies only the action's name and value; permission and context come from the
    signed claims, re-verified here so an action after the token lapses does not take effect. The
    account the claims are checked for must still hold a permission that allows the launch. A
    failure in a preview inside Sparkth is recorded for the agents that work on the activity.

    Raises:
        PxcInvalidLaunchToken: if the token no longer verifies.
        PxcActivityNotFound: if the token's activity no longer exists.
        PxcActivityNotPermitted: if the account holds no permission that allows the launch.
        PxcActionRejected: if the manifest does not accept this action or value.
        PxcSandboxFailure: if the sandbox itself failed.
    """
    claims = read_launch_token(token)
    await require_launch_access(claims)
    action_name = str(frame["action"])
    action_value: FieldType = frame.get("value", "")
    await perform_action(runtime, claims, action_name, action_value)
