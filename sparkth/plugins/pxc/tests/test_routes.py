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


async def test_the_client_connects_a_socket_from_the_configured_url(client: AsyncClient) -> None:
    """Source-level guard: the client must take its socket URL from the config, not the default.

    pxc.js's _getWebsocketUrl() falls back to /api/activity/{activity_id}/ws, which Sparkth
    does not serve, so a client that never sets _wsUrl connects to nothing and silently
    receives no events. It reads this._wsUrl at connect time, so the assignment has to precede
    the connect call: assigning it afterwards leaves the same silent fallback in place while
    both lines are still present. The connect call must in turn precede the activity script
    load: _pushAction reads this._ws.readyState, which throws if the activity's own script
    calls sendAction before a socket object exists. Each pinned line is matched anchored at
    line-start (not just as a substring) so a commented-out line cannot satisfy it.
    """
    response = await client.get("/api/v1/pxc/client/sparkth-pxc.js")

    ws_url_assignment = re.search(r"^\s*this\._wsUrl = config\.ws_url;\s*$", response.text, re.MULTILINE)
    connect_call = re.search(r"^\s*this\._connectWebSocket\(\);\s*$", response.text, re.MULTILINE)
    load_script_call = re.search(r"^\s*await this\._loadScript\(", response.text, re.MULTILINE)

    assert ws_url_assignment, "this._wsUrl must be assigned from config.ws_url"
    assert connect_call, "the socket must actually be connected"
    assert load_script_call, "the activity script must still be loaded"
    assert ws_url_assignment.start() < connect_call.start(), "_wsUrl must be set before the socket connects"
    assert connect_call.start() < load_script_call.start(), "the socket must connect before the script loads"


async def test_the_client_overrides_the_large_payload_post_route(client: AsyncClient) -> None:
    """Source-level guard: the inherited _postAction points at a route Sparkth does not serve.

    pxc.js's own _postAction hardcodes /api/activity/{id}/actions/{name} with cookie
    credentials. Left inherited, every payload over 512 KiB 404s, _flushQueue breaks out of
    its loop on the false return, and the action sits in IndexedDB forever — retried on every
    reconnect and never delivered. Both of _postAction's own failure paths — a rejected response
    and a network-level throw from fetch itself — must resolve to `false`, never throw:
    _flushQueue reads the boolean to decide whether to keep draining the queue, and a throw
    would abort it there, stranding every queued record behind the failing one.

    The failure-path searches run against the text from _postAction's definition onward, not
    the whole file: connectedCallback has an `if (!response.ok)` branch of its own, earlier in
    the file, so an unscoped search can be satisfied by a method this test says nothing about.
    """
    response = await client.get("/api/v1/pxc/client/sparkth-pxc.js")

    post_action_def = re.search(r"^\s*async _postAction\(", response.text, re.MULTILINE)
    assert post_action_def, "_postAction must still be defined"

    post_action_onward = response.text[post_action_def.start() :]
    action_url_ref = re.search(r"^\s*const url = .*this\._actionUrl", post_action_onward, re.MULTILINE)
    ok_branch_returns_false = re.search(r"if\s*\(!response\.ok\)\s*\{[^}]*return false", post_action_onward)
    catch_branch_returns_false = re.search(r"catch\s*\(error\)\s*\{[^}]*return false", post_action_onward)

    assert action_url_ref, "the POST url must be built from this._actionUrl"
    assert ok_branch_returns_false, "a rejected response must return false, not throw"
    assert catch_branch_returns_false, "a network-level fetch failure must return false, not throw"


async def test_the_client_does_not_import_the_private_database_helper(client: AsyncClient) -> None:
    # pxc.js exports only PXC; _openDB is module-private, so importing it does not resolve and
    # the module fails to load. _pushAction and _flushQueue each open the database themselves.
    response = await client.get("/api/v1/pxc/client/sparkth-pxc.js")

    assert "_openDB" not in response.text


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

    ``json.loads`` refuses to build an ``int`` from more digits than
    ``sys.get_int_max_str_digits()`` permits, and that refusal is a plain ``ValueError`` rather
    than a ``JSONDecodeError``: the body is well-formed JSON the parser declines to
    materialise. This route is reachable by anyone holding a valid token, so the refusal has to
    be a clean 422 and not a 500 — the same cause closes the socket with 1003 on the other
    transport.

    The digit count is derived from the live limit instead of hardcoded, because the limit is
    an interpreter setting (``PYTHONINTMAXSTRDIGITS``, ``-X int_max_str_digits``,
    ``sys.set_int_max_str_digits``). A hardcoded count would silently stop exercising this
    cause on any interpreter configured with a different one.

    Unmarked: the body is rejected before build_runtime ever touches the sandbox.
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

    ``RecursionError`` inherits from ``RuntimeError``, not ``ValueError``, so the clause that
    covers every decode failure does not reach this one. This route is reachable by anyone
    holding a valid token, so the refusal has to be a clean 422 and not a 500 — the socket's
    nested-frame test pins the same cause to a 1003 close.

    Why 200_000: measured end to end. Up to ~50_000 the parser reports a decode error before
    running out of recursion; from ~60_000 up it raises ``RecursionError``. 200_000 sits
    comfortably past that boundary at 195 KiB of body.

    The assertion cannot go stale on a machine with more headroom: ``"["`` repeated is invalid
    JSON at any depth, so it is a 422 either way — by ``RecursionError`` if recursion runs out
    first, by the decode error if it does not. A bigger stack costs this test its power, never
    its correctness.

    Unmarked: the bad body is rejected before build_runtime ever touches the sandbox.
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
    """The one branch no ``client``-fixture test reaches.

    ``sparkth.lib.testing``'s ``client`` fixture pins every request at
    ``base_url="http://test"``, so ``_socket_url``'s ``https`` branch is otherwise exercised by
    nothing — a mapping with its two branches swapped would still pass every other test in this
    suite. Built directly on a ``Request`` rather than by widening the shared fixture, which
    every other test also relies on staying plain HTTP.
    """
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
