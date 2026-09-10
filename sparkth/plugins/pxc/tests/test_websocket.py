"""The activity socket: who may open one, and how it refuses.

Synchronous tests, unlike the rest of this suite. ``TestClient.websocket_connect`` drives its
own event loop through a portal, so calling it from an async test would block. Both fixtures
these tests need are synchronous, and the PXC routes touch no application database.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sparkth.plugins.pxc.event_bus import EVENT_BUS
from sparkth.plugins.pxc.tokens import mint_launch_token


def test_a_socket_without_a_token_is_refused(ws_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect("/api/v1/pxc/ws"):
            pass

    assert refusal.value.code == status.WS_1008_POLICY_VIOLATION


def test_a_socket_with_a_bad_token_is_closed_with_a_policy_violation(ws_client: TestClient) -> None:
    # 1008, not 401: a WebSocket route cannot produce an HTTP status, and the plugin's
    # registered exception handlers render only for HTTP requests.
    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect("/api/v1/pxc/ws?token=not-a-token"):
            pass

    assert refusal.value.code == status.WS_1008_POLICY_VIOLATION


def test_a_socket_for_an_unbundled_activity_is_closed(ws_client: TestClient, configured_secret: str) -> None:
    token = mint_launch_token(
        "no-such-activity", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300
    )

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}"):
            pass

    assert refusal.value.code == status.WS_1008_POLICY_VIOLATION


def test_a_socket_with_a_valid_token_is_accepted(ws_client: TestClient, configured_secret: str) -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
        assert socket is not None


def test_a_closed_socket_leaves_no_subscriber_behind(ws_client: TestClient, configured_secret: str) -> None:
    """The finally clause must unsubscribe, or a closed socket stays in the bus's list (L16).

    The assertion inside the open socket pins the subscription key. Without it the closing
    assertion alone passes both when the socket subscribed and unsubscribed and when it never
    subscribed under ``"mcq"`` at all, so a wrong key would pass every test in this file.
    """
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}"):
        assert len(EVENT_BUS._subscribers["mcq"]) == 1

    assert EVENT_BUS._subscribers.get("mcq", []) == []


@pytest.mark.wasm
def test_an_action_sent_over_the_socket_comes_back_as_an_event(ws_client: TestClient, configured_secret: str) -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
        socket.send_json({"action": "answer.submit", "value": [0], "permission": "play"})
        event = socket.receive_json()

    assert event["name"] == "answer.result"


@pytest.mark.wasm
def test_two_learners_on_one_placement_both_receive_one_learners_event(
    ws_client: TestClient, configured_secret: str
) -> None:
    """The feature. Before this transport, an action's events reached only the acting client.

    Both sockets come from the same TestClient context, so they share one portal and one event
    loop — and one process, which is what L11 requires and what this asserts by construction.
    """
    acting = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)
    watching = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-8", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={watching}") as watcher:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={acting}") as actor:
            actor.send_json({"action": "answer.submit", "value": [0], "permission": "play"})

            assert actor.receive_json()["name"] == "answer.result"
            assert watcher.receive_json()["name"] == "answer.result"


@pytest.mark.wasm
def test_a_frame_cannot_escalate_its_own_permission(ws_client: TestClient, configured_secret: str) -> None:
    """The property this transport is most likely to lose.

    ``pxc.js`` puts a ``permission`` field in every frame, and the client belongs to the
    learner. The permission the sandbox runs at must come from the signed ``prm`` claim.

    Asserted on the effect, not on an error: the sandbox is the enforcement point and it
    *silently ignores* a play-mode ``config.save`` rather than raising — the same way
    ``test_configuration_saves_with_edit_and_is_ignored_with_play`` asserts it. A test
    expecting a rejection message would pass against a handler that trusts the frame.
    """
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)
    saved = {"question": "Owned?", "answers": ["yes"], "correct_answers": [0]}

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
        socket.send_json({"action": "config.save", "value": saved, "permission": "edit"})
        socket.send_json({"action": "answer.submit", "value": [0], "permission": "play"})
        # Two assertions in one read. A play-mode config.save is ignored and emits nothing, so
        # the first event to arrive must be the submit's. Had the frame's "edit" been honoured,
        # the save would have emitted fields.change.question first and this would fail — and
        # arriving at all proves the loop processed the save rather than merely not reaching it.
        assert socket.receive_json()["name"] == "answer.result"

    config_response = ws_client.get("/api/v1/pxc/config", params={"token": token})

    assert config_response.json()["state"].get("question") != "Owned?"


def test_a_frame_that_is_not_json_closes_the_socket(ws_client: TestClient, configured_secret: str) -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            socket.send_text("not-json")
            socket.receive_json()

    assert refusal.value.code == status.WS_1003_UNSUPPORTED_DATA


def test_a_frame_with_no_action_closes_the_socket(ws_client: TestClient, configured_secret: str) -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            socket.send_json({"value": [0]})
            socket.receive_json()

    assert refusal.value.code == status.WS_1003_UNSUPPORTED_DATA


def test_an_action_after_the_token_lapses_closes_the_socket(
    ws_client: TestClient, configured_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``xblock/README.md`` states that a save submitted after the token lapses is refused.

    On the HTTP routes that holds because every request verifies the token afresh. A socket
    verified only at its handshake would accept an action an hour later, so the loop
    re-verifies per frame. Time is moved forward rather than slept through, so this is
    deterministic.
    """
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", lambda: 2_000_000_000)
            socket.send_json({"action": "answer.submit", "value": [0], "permission": "play"})
            socket.receive_json()

    assert refusal.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.wasm
def test_an_action_the_manifest_rejects_leaves_the_socket_open(ws_client: TestClient, configured_secret: str) -> None:
    """A client bug must not kill a working socket — the learner's next action must still run.

    Survival is asserted by running a *valid* action afterwards and receiving its event.
    Asserting the absence of a disconnect directly does not work: the server's close would not
    surface on the client until a later read, so a test that only sends and then exits its
    ``with`` block passes whether the socket survived or not.
    """
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
        socket.send_json({"action": "no.such.action", "value": [], "permission": "play"})
        socket.send_json({"action": "answer.submit", "value": [0], "permission": "play"})

        assert socket.receive_json()["name"] == "answer.result"
