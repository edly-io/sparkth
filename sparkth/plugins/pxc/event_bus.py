"""The process's PXC event bus, and the one safe way to publish to it.

``pxc-lib``'s :class:`~pxc.lib.event_bus.EventBus` does the selecting — by each event's context
and by its declared minimum permission — so this module supplies only what the library leaves
to its host: one bus per process, and a fan-out that finishes even when one subscriber's socket
has already gone.

The bus keeps its subscribers in memory, so its reach is one process (L11). Two learners served
by different uvicorn workers do not see each other's events, with no error on either side.
"""

from pxc.lib.event_bus import EventBus, Subscriber
from pxc.lib.runtime import PendingEvent
from starlette.websockets import WebSocket

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.tokens import LaunchClaims

logger = get_logger(__name__)

EVENT_BUS = EventBus()


class _SubscriberSocket:
    """A subscriber's socket, as the bus should see it.

    A class rather than a function because the bus holds this object and calls one method on
    it; there is nothing else to be.

    ``EventBus.publish`` catches only ``WebSocketDisconnect``, and it awaits a send on every
    subscriber inside one loop — so a send raising anything else stops the fan-out where it
    stands and the subscribers after it never receive the event (L16). Starlette raises
    ``RuntimeError`` for a send on a socket whose application half has already closed, which is
    reachable whenever one learner reconnects while another's action is fanning out. Absorbing
    it here, where the bus expects success, lets the loop carry on.

    ``WebSocketDisconnect`` is deliberately left to propagate: the bus handles and logs it, and
    swallowing it here would hide a disconnect the library wants to see.
    """

    def __init__(self, websocket: WebSocket, user_id: str) -> None:
        self._websocket = websocket
        self._user_id = user_id

    async def send_json(self, message: dict[str, str]) -> None:
        try:
            await self._websocket.send_json(message)
        except RuntimeError as err:
            logger.warning("Dropped a PXC event for subscriber %s: %s", self._user_id, err)


def subscribe_socket(activity: str, websocket: WebSocket, claims: LaunchClaims) -> Subscriber:
    """Subscribe one launch's socket to ``activity``'s events, and return its subscription.

    The permission recorded here is the token's, which is what makes the bus's per-event
    permission filtering meaningful: an ``edit``-scoped event reaches only a subscriber whose
    signed claim asked for ``edit``.
    """
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
    """Fan out one action's events to every subscriber their context and permission admit.

    The ``RuntimeError`` net is the outer half of L16's mitigation: ``_SubscriberSocket`` keeps
    an individual failing send from stopping the loop, and this catches a ``RuntimeError``
    raised anywhere else in ``publish`` so a fan-out failure cannot fail the action that caused
    it.
    """
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
