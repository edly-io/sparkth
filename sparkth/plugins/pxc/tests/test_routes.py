import sys
from pathlib import Path

import pytest
from fastapi import Request
from httpx import AsyncClient

from sparkth.main import assemble_app
from sparkth.plugins.pxc.routes import _socket_url
from sparkth.plugins.pxc.tests.conftest import inline_config
from sparkth.plugins.pxc.tokens import mint_launch_token


@pytest.fixture
def token(configured_secret: str) -> str:
    return mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "play", configured_secret, 300)


async def test_the_embed_shell_without_a_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/embed")

    assert response.status_code == 422


async def test_an_action_with_a_bad_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.post("/api/v1/pxc/actions/answer.submit", params={"token": "not-a-token"}, json=[1])

    assert response.status_code == 401


async def test_the_embed_shell_with_a_bad_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/embed", params={"token": "not-a-token"})

    assert response.status_code == 401


@pytest.mark.wasm
async def test_the_embed_shell_renders_the_activity_element(client: AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert response.status_code == 200
    assert "pxc-activity" in response.text
    assert token in response.text


@pytest.mark.wasm
async def test_the_embed_shell_carries_the_token_as_its_own_attribute(client: AsyncClient, token: str) -> None:
    # pxc.js's _initFromAttrs() reads data-pxc-token into this._pxcToken, which the client then
    # appends itself when it builds action and asset URLs — see the action-URL test below. The
    # "renders the activity element" test only proves the token appears somewhere (it is also
    # inside the inline configuration's URLs), not that this attribute exists.
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert f'data-pxc-token="{token}"' in response.text


async def test_the_client_route_serves_the_bundled_pxc_component(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/client/pxc.js")

    assert response.status_code == 200
    assert "class PXC" in response.text


# TODO (#680): the vitest suite for `sparkth-pxc.js` does not yet cover the launch token on
# every asset URL, or the reconnect ceiling and its notice.


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
async def test_the_embed_shell_inlines_the_state_and_the_learners_context(client: AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert response.status_code == 200
    config = inline_config(response.text)
    assert config.context.model_dump() == {
        "activity_id": "placement-1",
        "course_id": "course-v1:X+Y+Z",
        "user_id": "learner-7",
    }
    assert config.permission == "play"
    assert config.ui_url.endswith("/api/v1/pxc/assets/ui.js?token=" + token)


@pytest.mark.wasm
async def test_the_embed_shell_reports_the_permission_the_token_asked_for(
    client: AsyncClient, configured_secret: str
) -> None:
    edit_token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "edit", configured_secret, 300)

    response = await client.get("/api/v1/pxc/embed", params={"token": edit_token})

    assert response.status_code == 200
    assert inline_config(response.text).permission == "edit"


@pytest.mark.wasm
async def test_inlined_state_cannot_close_the_configuration_script(
    client: AsyncClient, token: str, configured_secret: str
) -> None:
    # An author's saved text lands in the page verbatim; unescaped, this would end the JSON block.
    question = "</script><script>alert(1)</script>"
    edit_token = mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", "edit", configured_secret, 300)
    saved = {"question": question, "answers": ["yes", "no"], "correct_answers": [0]}
    save = await client.post("/api/v1/pxc/actions/config.save", params={"token": edit_token}, json=saved)
    assert save.status_code == 204

    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert inline_config(response.text).state["question"] == question


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
    # of them consumes the embed shell's own output. That leaves action_base_url unchecked for
    # the token it needs: submit_action declares token as a required query parameter, and
    # nothing else here builds the URL the way the browser does.
    #
    # This test reads action_base_url from the inline configuration and appends
    # "/{action}?token={token}" exactly as sparkth-pxc.js's _postAction() does. The vitest
    # suite pins the client half; this pins the server half.
    embed_response = await client.get("/api/v1/pxc/embed", params={"token": token})
    action_base_url = inline_config(embed_response.text).action_base_url

    action_url = f"{action_base_url}/answer.submit?token={token}"
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
async def test_the_embed_shell_carries_the_socket_url_for_this_launch(client: AsyncClient, token: str) -> None:
    # The client sets this on pxc.js's this._wsUrl. Without it, _getWebsocketUrl() falls back
    # to the upstream default of /api/activity/{activity_id}/ws, which Sparkth does not serve.
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    ws_url = inline_config(response.text).ws_url

    assert ws_url.startswith("ws://")
    assert ws_url.endswith(f"/api/v1/pxc/ws?token={token}")


def test_socket_url_upgrades_a_tls_request_to_wss() -> None:
    """The ``https`` branch, which the ``client`` fixture's ``http://test`` base URL never reaches."""
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "method": "GET",
            "path": "/api/v1/pxc/embed",
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


async def test_a_client_script_allows_any_origin(client: AsyncClient) -> None:
    # The embed page's origin is opaque, so loading its module scripts is a cross-origin fetch.
    response = await client.get("/api/v1/pxc/client/sparkth-pxc.js")

    assert response.headers["access-control-allow-origin"] == "*"


async def test_an_activity_asset_allows_any_origin(client: AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/pxc/assets/ui.js", params={"token": token})

    assert response.headers["access-control-allow-origin"] == "*"


async def test_an_action_preflight_is_answered_without_a_token(client: AsyncClient) -> None:
    # A browser sends the preflight before the POST, and without the POST's query credentials.
    response = await client.options(
        "/api/v1/pxc/actions/answer.submit",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-methods"] == "POST"
    assert response.headers["access-control-allow-headers"] == "Content-Type"


@pytest.mark.wasm
async def test_an_action_allows_any_origin(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/pxc/actions/answer.submit", params={"token": token}, json=[0])

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"


async def test_an_activity_asset_opens_in_a_sandbox(client: AsyncClient, token: str) -> None:
    # Opened directly, an asset would otherwise run with Sparkth's origin and reach its storage.
    response = await client.get("/api/v1/pxc/assets/ui.js", params={"token": token})

    assert response.headers["content-security-policy"] == "sandbox allow-scripts allow-forms"


@pytest.mark.wasm
async def test_the_embed_shell_opens_in_a_sandbox(client: AsyncClient, token: str) -> None:
    # The header, not the iframe attribute, is what holds for a direct link or any embedding page.
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert response.headers["content-security-policy"] == "sandbox allow-scripts allow-forms"
