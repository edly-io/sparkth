"""The activity socket: who may open one, and how it refuses.

Synchronous: ``TestClient.websocket_connect`` drives its own event loop, so an async test blocks.
"""

import sys

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
    """The finally clause must unsubscribe; the inner assertion pins the subscription key (L16)."""
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
    """An action's events reach every learner on the placement, not just the actor."""
    acting = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)
    watching = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-8", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={watching}") as watcher:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={acting}") as actor:
            actor.send_json({"action": "answer.submit", "value": [0], "permission": "play"})

            assert actor.receive_json()["name"] == "answer.result"
            assert watcher.receive_json()["name"] == "answer.result"


@pytest.mark.wasm
def test_a_frame_cannot_escalate_its_own_permission(ws_client: TestClient, configured_secret: str) -> None:
    """Asserted on the effect, not an error: the sandbox ignores a play-mode save silently."""
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

    # Status before indexing. read_state re-raises a sandbox failure as PxcSandboxFailure, which
    # plugin.py registers to 502, so the body would be {"detail": ...} and ["state"] would raise
    # an opaque KeyError('state') instead of naming the real cause.
    assert config_response.status_code == status.HTTP_200_OK
    assert config_response.json()["state"].get("question") != "Owned?"


def test_a_frame_that_is_not_json_closes_the_socket(ws_client: TestClient, configured_secret: str) -> None:
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            socket.send_text("not-json")
            socket.receive_json()

    assert refusal.value.code == status.WS_1003_UNSUPPORTED_DATA


def test_a_binary_frame_closes_the_socket(ws_client: TestClient, configured_secret: str) -> None:
    """A binary frame reaches the loop as ``KeyError``, not as ``JSONDecodeError``."""
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            socket.send_bytes(b"\x01\x02\x03")
            socket.receive_json()

    assert refusal.value.code == status.WS_1003_UNSUPPORTED_DATA


def test_a_deeply_nested_frame_closes_the_socket(ws_client: TestClient, configured_secret: str) -> None:
    """A frame nested past the parser's recursion limit raises ``RecursionError``, not a decode error.

    200_000 is measured: ``RecursionError`` from ~150_000 up, and 195 KiB stays under the 1 MiB cap.
    """
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            socket.send_text("[" * 200_000)
            socket.receive_json()

    assert refusal.value.code == status.WS_1003_UNSUPPORTED_DATA


def test_a_frame_with_an_over_long_integer_closes_the_socket(ws_client: TestClient, configured_secret: str) -> None:
    """An integer literal past CPython's int-from-string limit raises a bare ``ValueError``.

    The digit count is read from the live limit, which is an interpreter setting, not hardcoded.
    """
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)
    over_long_integer = "1" * (sys.get_int_max_str_digits() + 1)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            socket.send_text('{"action": "answer.submit", "value": ' + over_long_integer + "}")
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
    """A socket verified only at its handshake would accept an action an hour later."""
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with pytest.raises(WebSocketDisconnect) as refusal:
        with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
            monkeypatch.setattr("sparkth.plugins.pxc.tokens.time", lambda: 2_000_000_000)
            socket.send_json({"action": "answer.submit", "value": [0], "permission": "play"})
            socket.receive_json()

    assert refusal.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.wasm
def test_an_action_the_manifest_rejects_leaves_the_socket_open(ws_client: TestClient, configured_secret: str) -> None:
    """Survival is asserted by a valid action afterwards; an absent disconnect would not surface."""
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
        socket.send_json({"action": "no.such.action", "value": [], "permission": "play"})
        socket.send_json({"action": "answer.submit", "value": [0], "permission": "play"})

        assert socket.receive_json()["name"] == "answer.result"


@pytest.mark.wasm
def test_the_http_action_route_publishes_to_the_socket(ws_client: TestClient, configured_secret: str) -> None:
    """``_flushQueue`` routes any payload over 512 KiB through HTTP, and its events must still land."""
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}") as socket:
        response = ws_client.post("/api/v1/pxc/actions/answer.submit", params={"token": token}, json=[0])

        assert response.status_code == 204
        assert socket.receive_json()["name"] == "answer.result"
