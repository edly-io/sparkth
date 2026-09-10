"""The activity socket's frame loop: what arrives on the socket, and what it causes.

Kept out of ``routes.py`` because none of it is routing. The route's job ends once the launch
token is verified and the subscription exists; from there this module owns every frame.
"""

import asyncio
from json import JSONDecodeError
from typing import Any

from fastapi import status
from pxc.lib.fields import FieldType
from pxc.lib.runtime import ActivityRuntime
from starlette.websockets import WebSocket

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.event_bus import publish_events
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcInvalidLaunchToken
from sparkth.plugins.pxc.runtime import run_action
from sparkth.plugins.pxc.tokens import read_launch_token

logger = get_logger(__name__)


async def run_action_frames(websocket: WebSocket, runtime: ActivityRuntime, token: str) -> None:
    """Read and run action frames until the client goes away or sends one that cannot be run.

    Refusals are close codes rather than HTTP statuses: the plugin's registered exception
    handlers render only for HTTP requests, so a domain exception raised from here would render
    nothing. A token that no longer verifies closes with ``WS_1008_POLICY_VIOLATION``.

    Two separate failures both close with ``WS_1003_UNSUPPORTED_DATA``, and they are not the
    same thing. A frame the loop cannot *read* raises out of ``receive_json``: a text frame that
    is not valid JSON, a binary frame (there is no ``"text"`` to read), or one nested deeply
    enough to exhaust the parser's recursion. A frame that parsed but is not an object with an
    ``action`` is the other case — the loop read it fine and found the wrong shape.

    The client is the learner's, so every frame shape is reachable by hand, and an exception that
    escapes costs the learner uvicorn's ``1011`` and an ASGI traceback instead of the refusal
    intended. The three read failures named above are the causes known to date, deliberately not
    a claim of completeness: ``receive_json`` parses attacker-controlled bytes, so another cause
    may exist. ``except Exception`` is not the remedy — ``CLAUDE.md`` forbids it, and it would
    also swallow the ``WebSocketDisconnect`` that is this loop's normal exit. Name a new cause
    when one turns up.

    Raises:
        WebSocketDisconnect: when the client goes away, which is this loop's normal exit.
    """
    while True:
        try:
            frame = await websocket.receive_json()
        except (JSONDecodeError, KeyError, RecursionError) as err:
            # Three causes, one refusal: a text frame whose body is not JSON raises
            # JSONDecodeError, a binary frame raises KeyError("text") because
            # receive_json(mode="text") reads a key its ASGI message does not carry, and a
            # deeply nested frame exhausts the parser's recursion. The stack has unwound by the
            # time close() runs, so there is headroom to send it. Logged with %r so the
            # exception type says which arrived.
            logger.warning(
                "Refusing a PXC socket frame the loop cannot read as JSON text on %s (placement=%s): %r",
                runtime.name,
                runtime.activity_id,
                err,
            )
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        if not isinstance(frame, dict) or "action" not in frame:
            logger.warning(
                "Refusing a PXC socket frame with no action on %s (placement=%s)",
                runtime.name,
                runtime.activity_id,
            )
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
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
            # The socket stays open: a client sending an action this activity does not declare
            # is a client bug, and killing the socket would take the learner's working session
            # with it.
            logger.warning(
                "Rejected a PXC socket action %s on %s (placement=%s): %s",
                frame["action"],
                runtime.name,
                runtime.activity_id,
                err,
            )


async def _run_one_action(runtime: ActivityRuntime, token: str, frame: dict[str, Any]) -> None:
    """Run one frame's action through the sandbox and fan out the events it produced.

    The frame's own ``permission`` field is never read. ``pxc.js`` sends one, and the client is
    the learner's to rewrite; the permission the sandbox runs at came from the signed ``prm``
    claim when the runtime was built. The same holds for every other field the token already
    answers — activity, placement, course and learner all come from the claims, so a frame
    supplies nothing but the action's name and its value.

    The token is re-verified here rather than only at the handshake, so an action submitted
    after it lapses does not take effect — the property ``xblock/README.md`` states, which the
    HTTP routes hold by verifying afresh on every request.

    The sandbox call runs on a worker thread: ``ActivityRuntime`` executes WebAssembly
    synchronously on the calling thread, so running it inline would block the event loop for
    every other request in the process.

    Raises:
        PxcInvalidLaunchToken: if the token no longer verifies.
        PxcActionRejected: if the manifest does not accept this action or value.
    """
    claims = read_launch_token(token)
    action_name = str(frame["action"])
    action_value: FieldType = frame.get("value", "")
    events = await asyncio.to_thread(run_action, runtime, action_name, action_value)
    await publish_events(claims.activity, claims.placement, events)
