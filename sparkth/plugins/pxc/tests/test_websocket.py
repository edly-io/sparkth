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
    with pytest.raises(WebSocketDisconnect):
        with ws_client.websocket_connect("/api/v1/pxc/ws"):
            pass


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
    """The finally clause must unsubscribe, or a closed socket stays in the bus's list (L16)."""
    token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)

    with ws_client.websocket_connect(f"/api/v1/pxc/ws?token={token}"):
        pass

    assert EVENT_BUS._subscribers.get("mcq", []) == []
