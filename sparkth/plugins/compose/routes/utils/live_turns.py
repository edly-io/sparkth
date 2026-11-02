"""The chat turns streaming in this process, and the stop requests aimed at them.

A turn registers when its stream starts and releases when it ends. The stop route sets the
event its processor polls between steps, which is what makes a stop land between tool calls
rather than inside one.
"""

import asyncio

from sparkth.lib.log import get_logger

logger = get_logger(__name__)


# Keyed by owner as well as turn: the id comes from the client, so one caller naming
# another's id must not reach, displace or release that turn.
# ponytail: per-process registry, Redis pub/sub if the backend ever runs more than one replica
_live_turns: dict[tuple[int, str], asyncio.Event] = {}


def register_turn(turn_id: str, user_id: int) -> asyncio.Event:
    """Record a streaming turn and return the event its processor polls."""
    stop_requested = asyncio.Event()
    _live_turns[(user_id, turn_id)] = stop_requested
    return stop_requested


def release_turn(turn_id: str, user_id: int) -> None:
    """Forget a finished turn. An unknown turn is ignored, so releasing twice is safe."""
    _live_turns.pop((user_id, turn_id), None)


def request_stop(turn_id: str, user_id: int) -> bool:
    """Ask a turn to stop, returning whether this user had one live under that id.

    An unknown id and another user's id both return False, so a caller cannot use this to
    learn whether someone else's turn exists.
    """
    stop_requested = _live_turns.get((user_id, turn_id))
    if stop_requested is None:
        return False
    stop_requested.set()
    logger.info("Stop requested for chat turn %s", turn_id)
    return True
