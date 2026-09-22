import re
import sys
from pathlib import Path

import pytest
from fastapi import Request
from httpx import AsyncClient

from sparkth.main import assemble_app
from sparkth.plugins.pxc.routes import _socket_url
from sparkth.plugins.pxc.tokens import mint_launch_token


def _extract_attr(html: str, attr: str) -> str:
    """The value of one double-quoted HTML attribute, for tests that drive a route's own markup."""
    match = re.search(f'{attr}="([^"]*)"', html)
    assert match, f"{attr} not found in: {html}"
    return match.group(1)


@pytest.fixture
def token(configured_secret: str) -> str:
    return mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)


async def test_config_without_a_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/config")

    assert response.status_code == 422


async def test_config_with_a_bad_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/config", params={"token": "not-a-token"})

    assert response.status_code == 401


async def test_an_action_with_a_bad_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.post("/api/v1/pxc/actions/answer.submit", params={"token": "not-a-token"}, json=[1])

    assert response.status_code == 401


async def test_the_embed_shell_with_a_bad_token_is_unauthorized(client: AsyncClient) -> None:
    # Guards embed_activity's unbound read_launch_token(token) call: without this test, deleting
    # that line entirely would leave every other test green, and a reader could mistake the
    # discarded result for a pointless call and remove it.
    response = await client.get("/api/v1/pxc/embed", params={"token": "not-a-token"})

    assert response.status_code == 401


async def test_the_embed_shell_renders_the_activity_element(client: AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert response.status_code == 200
    assert "pxc-activity" in response.text
    assert token in response.text


async def test_the_embed_shell_carries_the_token_as_its_own_attribute(client: AsyncClient, token: str) -> None:
    # pxc.js's _initFromAttrs() reads data-pxc-token into this._pxcToken, which the client then
    # appends itself when it builds action and asset URLs — see the action-URL test below. The
    # existing "renders the activity element" test only proves the token appears somewhere (it
    # is already inside data-config-url's query string), not that this attribute exists.
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert f'data-pxc-token="{token}"' in response.text


async def test_the_client_route_serves_the_bundled_pxc_component(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/client/pxc.js")

    assert response.status_code == 200
    assert "class PXC" in response.text


# TODO (#680): `sparkth-pxc.js` needs a vitest suite that executes it. Nothing here can: a
# route test reads the served source as text, and asserting on that text pins formatting rather
# than behaviour — it breaks on a reformat that changes nothing and passes on a rewrite that
# breaks the client. The socket URL coming from the configuration, `_postAction` returning
# false rather than throwing, the launch token on every asset URL, and the reconnect ceiling
# and its notice are all unguarded until then.


async def test_the_client_route_refuses_a_name_it_does_not_own(client: AsyncClient) -> None:
    # A name, not a traversal: httpx and Starlette both normalise "../" out of a URL path
    # before the route ever sees it, so a traversal test would pass without proving anything.
    # The allowlist dict is what makes traversal impossible; this asserts the allowlist.
    response = await client.get("/api/v1/pxc/client/constants.py")

    assert response.status_code == 404


async def test_an_undeclared_asset_is_not_served(client: AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/pxc/assets/manifest.json", params={"token": token})

    assert response.status_code == 404


@pytest.mark.wasm
async def test_config_returns_the_state_and_the_learners_context(client: AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/pxc/config", params={"token": token})

    assert response.status_code == 200
    body = response.json()
    assert body["context"] == {
        "activity_id": "placement-1",
        "course_id": "course-v1:X+Y+Z",
        "user_id": "learner-7",
    }
    assert body["permission"] == "play"
    assert body["ui_url"].endswith("/api/v1/pxc/assets/ui.js?token=" + token)


@pytest.mark.wasm
async def test_config_reports_the_permission_the_token_asked_for(client: AsyncClient, configured_secret: str) -> None:
    edit_token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "edit", configured_secret, 300)

    response = await client.get("/api/v1/pxc/config", params={"token": edit_token})

    assert response.status_code == 200
    assert response.json()["permission"] == "edit"


async def test_the_activitys_ui_script_is_served(client: AsyncClient, token: str) -> None:
    # Unmarked deliberately: the asset route resolves the path from the manifest and never
    # constructs a runtime, so nothing here can reach the sandbox.
    response = await client.get("/api/v1/pxc/assets/ui.js", params={"token": token})

    assert response.status_code == 200


async def test_serving_an_asset_does_not_open_the_activitys_state_file(
    client: AsyncClient, token: str, tmp_path: Path
) -> None:
    # An asset URL resolves to a path under the activity directory; whose state it is has no
    # bearing on it. Building a runtime to answer one creates the SQLite file, sets its journal
    # mode and runs the schema — on every asset of every page load. The absent file is the
    # evidence, because nothing else about the response would change.
    response = await client.get("/api/v1/pxc/assets/ui.js", params={"token": token})

    assert response.status_code == 200
    assert not (tmp_path / "mcq.sqlite3").exists()


# Unmarked deliberately: ActivityRuntime.on_action validates the action name against the
# manifest and raises ActionValidationError before it ever checks whether a sandbox exists, so
# this never reaches the wasm.
async def test_an_undeclared_action_is_unprocessable(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/pxc/actions/no.such.action", params={"token": token}, json=[])

    assert response.status_code == 422


@pytest.mark.wasm
async def test_the_shells_own_action_url_can_submit_an_answer(client: AsyncClient, token: str) -> None:
    # Every other test in this file injects the token via params={"token": ...} by hand, so none
    # of them consumes the embed shell's own markup. That leaves data-action-url and
    # action_base_url unchecked for the token they need: submit_action declares token as a
    # required query parameter, and nothing else here builds the URL the way the browser does.
    #
    # This test drives the shell's own output instead: it extracts data-action-url and
    # data-pxc-token exactly as sparkth-pxc.js's _postAction() does — appending
    # "/{action}?token={token}" to the base — and POSTs to that composed URL. The JS
    # composition itself has no test harness here (it is a backend-served static asset, outside
    # frontend/tests/'s vitest include), so this pins the server half of the contract: the shell
    # must emit a base URL and a token the client can combine into one submit_action accepts.
    embed_response = await client.get("/api/v1/pxc/embed", params={"token": token})
    action_base_url = _extract_attr(embed_response.text, "data-action-url")
    shell_token = _extract_attr(embed_response.text, "data-pxc-token")

    action_url = f"{action_base_url}/answer.submit?token={shell_token}"
    response = await client.post(action_url, json=[0])

    assert response.status_code == 204


async def test_a_malformed_action_body_is_unprocessable_not_a_server_error(client: AsyncClient, token: str) -> None:
    # request.json() raises JSONDecodeError on a body that is not valid JSON at all, and this is
    # a public route any browser can reach with nothing but a valid token. The over-long-integer
    # sibling below covers the other ValueError the same call can raise.
    # Unmarked: the bad body is rejected before build_runtime ever touches the sandbox.
    response = await client.post(
        "/api/v1/pxc/actions/answer.submit",
        params={"token": token},
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


async def test_an_action_body_with_an_over_long_integer_is_unprocessable(client: AsyncClient, token: str) -> None:
    """An integer literal past CPython's int-from-string limit raises a bare ``ValueError``.

    The digit count is read from the live limit, which is an interpreter setting, not hardcoded.
    """
    over_long_integer = "1" * (sys.get_int_max_str_digits() + 1)

    response = await client.post(
        "/api/v1/pxc/actions/answer.submit",
        params={"token": token},
        content=over_long_integer.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


async def test_a_deeply_nested_action_body_is_unprocessable(client: AsyncClient, token: str) -> None:
    """A body nested past the parser's recursion limit raises ``RecursionError``, not a decode error.

    200_000 is measured: ``RecursionError`` from ~60_000 up, at 195 KiB of body.
    """
    response = await client.post(
        "/api/v1/pxc/actions/answer.submit",
        params={"token": token},
        content=b"[" * 200_000,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


@pytest.mark.wasm
async def test_config_carries_the_socket_url_for_this_launch(client: AsyncClient, token: str) -> None:
    # The client sets this on pxc.js's this._wsUrl. Without it, _getWebsocketUrl() falls back
    # to the upstream default of /api/activity/{activity_id}/ws, which Sparkth does not serve.
    response = await client.get("/api/v1/pxc/config", params={"token": token})

    ws_url = response.json()["ws_url"]

    assert ws_url.startswith("ws://")
    assert ws_url.endswith(f"/api/v1/pxc/ws?token={token}")


def test_socket_url_upgrades_a_tls_request_to_wss() -> None:
    """The ``https`` branch, which the ``client`` fixture's ``http://test`` base URL never reaches."""
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "method": "GET",
            "path": "/api/v1/pxc/config",
            "query_string": b"",
            "headers": [(b"host", b"example.com")],
            "server": ("example.com", 443),
            "router": assemble_app().router,
        }
    )

    ws_url = _socket_url(request, "tok-123")

    assert ws_url.startswith("wss://")
    assert ws_url.endswith("/api/v1/pxc/ws?token=tok-123")


@pytest.mark.wasm
async def test_an_action_returns_no_content(client: AsyncClient, token: str) -> None:
    # The events go to the socket, so there is no body to return. pxc.js's _postAction
    # reads only response.ok.
    response = await client.post("/api/v1/pxc/actions/answer.submit", params={"token": token}, json=[0])

    assert response.status_code == 204
    assert response.content == b""
