"""The chat turns streaming in this process, and the stop requests aimed at them.

A turn registers when its stream starts and releases when it ends. The stop route sets the
event its processor polls between steps, which is what makes a stop land between tool calls
rather than inside one.
"""

import asyncio
from dataclasses import dataclass

from sparkth.lib.log import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LiveTurn:
    """Who owns a streaming turn, and the event that asks it to stop."""

    user_id: int
    stop_requested: asyncio.Event


# ponytail: per-process registry, Redis pub/sub if the backend ever runs more than one replica
_live_turns: dict[str, LiveTurn] = {}


def register_turn(turn_id: str, user_id: int) -> asyncio.Event:
    """Record a streaming turn and return the event its processor polls."""
    turn = LiveTurn(user_id, asyncio.Event())
    _live_turns[turn_id] = turn
    return turn.stop_requested


def release_turn(turn_id: str) -> None:
    """Forget a finished turn. An unknown id is ignored, so releasing twice is safe."""
    _live_turns.pop(turn_id, None)


def request_stop(turn_id: str, user_id: int) -> bool:
    """Ask a turn to stop, returning whether it was this user's and still live.

    An unknown id and another user's id both return False, so a caller cannot use this to
    learn whether someone else's turn exists.
    """
    turn = _live_turns.get(turn_id)
    if turn is None or turn.user_id != user_id:
        return False
    turn.stop_requested.set()
    logger.info("Stop requested for chat turn %s", turn_id)
    return True
