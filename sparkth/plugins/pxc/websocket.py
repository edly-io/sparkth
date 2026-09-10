"""The activity socket's frame loop: what arrives on the socket, and what it causes.

Kept out of ``routes.py`` because none of it is routing. The route's job ends once the launch
token is verified and the subscription exists; from there this module owns every frame.
"""

from pxc.lib.runtime import ActivityRuntime
from starlette.websockets import WebSocket

from sparkth.lib.log import get_logger

logger = get_logger(__name__)


async def run_action_frames(websocket: WebSocket, runtime: ActivityRuntime, token: str) -> None:
    """Read and run action frames until the client goes away.

    Stub for this task: each frame is read and discarded. Dispatching it as an action against
    ``runtime`` and publishing the events it produces is Task 3's job.

    Raises:
        WebSocketDisconnect: when the client goes away, which is this loop's normal exit.
    """
    while True:
        await websocket.receive_json()
