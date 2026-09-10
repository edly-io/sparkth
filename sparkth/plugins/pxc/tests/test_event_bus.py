"""The bus's fan-out, its filtering, and the adapter that keeps a fan-out going.

Stub sockets rather than real ones: every property under test is about which subscribers the
bus selects and what happens when a send fails, none of which needs a transport.
"""

from typing import Any

from pxc.lib.permission import Permission
from pxc.lib.runtime import PendingEvent

from sparkth.plugins.pxc.event_bus import publish_events, subscribe_socket
from sparkth.plugins.pxc.tokens import LaunchClaims


class StubSocket:
    """Records what the bus sent it, or raises a chosen error instead."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self._fail_with = fail_with

    async def send_json(self, message: dict[str, Any]) -> None:
        if self._fail_with is not None:
            raise self._fail_with
        self.sent.append(message)


def _claims(permission: Permission, placement: str = "placement-1", user_id: str = "learner-7") -> LaunchClaims:
    return LaunchClaims("mcq", placement, "course-v1:X+Y+Z", user_id, permission)


def _event(permission: str, placement: str = "placement-1") -> PendingEvent:
    return {
        "name": "answer.result",
        "value": '{"correct": true}',
        "context": {"activity_id": placement, "course_id": "course-v1:X+Y+Z"},
        "permission": permission,
    }


def _subscribe(socket: StubSocket, claims: LaunchClaims) -> None:
    # cast: the bus types this parameter as WebSocket, but only ever calls send_json on it.
    subscribe_socket("mcq", socket, claims)  # type: ignore[arg-type]


async def test_both_subscribers_on_one_placement_receive_the_event() -> None:
    first, second = StubSocket(), StubSocket()
    _subscribe(first, _claims(Permission.play, user_id="learner-7"))
    _subscribe(second, _claims(Permission.play, user_id="learner-8"))

    await publish_events("mcq", "placement-1", [_event("play")])

    assert len(first.sent) == 1
    assert len(second.sent) == 1
    assert first.sent[0] == {"name": "answer.result", "value": '{"correct": true}'}


async def test_an_edit_scoped_event_does_not_reach_a_play_subscriber() -> None:
    player, author = StubSocket(), StubSocket()
    _subscribe(player, _claims(Permission.play, user_id="learner-7"))
    _subscribe(author, _claims(Permission.edit, user_id="author-1"))

    await publish_events("mcq", "placement-1", [_event("edit")])

    assert player.sent == []
    assert len(author.sent) == 1


async def test_a_subscriber_on_another_placement_does_not_receive() -> None:
    here, elsewhere = StubSocket(), StubSocket()
    _subscribe(here, _claims(Permission.play, placement="placement-1"))
    _subscribe(elsewhere, _claims(Permission.play, placement="placement-2"))

    await publish_events("mcq", "placement-1", [_event("play", placement="placement-1")])

    assert len(here.sent) == 1
    assert elsewhere.sent == []


async def test_a_send_that_raises_does_not_stop_the_others_receiving() -> None:
    """L16: EventBus.publish catches only WebSocketDisconnect and awaits inside its loop.

    The failing subscriber must be subscribed FIRST. With it second, this test passes even
    with no adapter in place and proves nothing. RuntimeError is the exception to inject: a
    client disconnect surfaces as WebSocketDisconnect, which the bus already handles, so
    injecting that would prove nothing either.
    """
    dead = StubSocket(fail_with=RuntimeError('Cannot call "send" once a close message has been sent.'))
    alive = StubSocket()
    _subscribe(dead, _claims(Permission.play, user_id="learner-7"))
    _subscribe(alive, _claims(Permission.play, user_id="learner-8"))

    await publish_events("mcq", "placement-1", [_event("play")])

    assert len(alive.sent) == 1
