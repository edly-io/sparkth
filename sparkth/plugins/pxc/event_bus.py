"""The process's PXC event bus, and the one safe way to publish to it.

Subscribers are held in memory, so the bus's reach is one process (L11).
"""

from pxc.lib.event_bus import EventBus, Subscriber
from pxc.lib.runtime import PendingEvent
from starlette.websockets import WebSocket

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.tokens import LaunchClaims

logger = get_logger(__name__)

EVENT_BUS = EventBus()


class _SubscriberSocket:
    """A subscriber's socket that absorbs a ``RuntimeError`` send so the fan-out continues (L16)."""

    def __init__(self, websocket: WebSocket, user_id: str) -> None:
        self._websocket = websocket
        self._user_id = user_id

    async def send_json(self, message: dict[str, str]) -> None:
        try:
            await self._websocket.send_json(message)
        except RuntimeError as err:
            logger.warning("Dropped a PXC event for subscriber %s: %s", self._user_id, err)


def subscribe_socket(activity: str, websocket: WebSocket, claims: LaunchClaims) -> Subscriber:
    """Subscribe one launch's socket to ``activity``'s events, and return its subscription."""
    # pxc-lib ships no py.typed marker, so mypy sees subscribe() as returning Any; the adapter
    # is the whole reason a fan-out survives a dead subscriber.
    subscriber: Subscriber = EVENT_BUS.subscribe(
        activity,
        _SubscriberSocket(websocket, claims.user_id),
        claims.user_id,
        claims.permission,
        claims.course_id,
        claims.placement,
    )
    return subscriber


async def publish_events(activity: str, placement: str, events: list[PendingEvent]) -> None:
    """Fan out one action's events to every subscriber their context and permission admit."""
    try:
        await EVENT_BUS.publish(activity, events)
    except RuntimeError as err:
        logger.error(
            "PXC event fan-out stopped early for %s (placement=%s, events=%s): %s",
            activity,
            placement,
            [event["name"] for event in events],
            err,
        )
