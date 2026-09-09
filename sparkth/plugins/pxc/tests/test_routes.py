import re

import pytest
from httpx import AsyncClient

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


async def test_the_activitys_ui_script_is_served(client: AsyncClient, token: str) -> None:
    # Unmarked deliberately: serving ui.js builds a runtime and reads manifest.ui, neither of
    # which touches the sandbox. Only get_state() and on_action() need the wasm.
    response = await client.get("/api/v1/pxc/assets/ui.js", params={"token": token})

    assert response.status_code == 200


# Unmarked deliberately: ActivityRuntime.on_action validates the action name against the
# manifest and raises ActionValidationError before it ever checks whether a sandbox exists, so
# this never reaches the wasm.
async def test_an_undeclared_action_is_unprocessable(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/pxc/actions/no.such.action", params={"token": token}, json=[])

    assert response.status_code == 422


@pytest.mark.wasm
async def test_the_shells_own_action_url_can_submit_an_answer(client: AsyncClient, token: str) -> None:
    # Every other test in this file injects the token via params={"token": ...} by hand, so none
    # of them ever consumed the embed shell's own markup. That is how routes.py shipped
    # data-action-url and action_base_url without the token they need: submit_action declares
    # token as a required query parameter, but nothing built the URL the way the browser does.
    #
    # This test drives the shell's own output instead: it extracts data-action-url and
    # data-pxc-token exactly as sparkth-pxc.js's sendAction() does — appending
    # "/{action}?token={token}" to the base — and POSTs to that composed URL. The JS
    # composition itself has no test harness here (it is a backend-served static asset, outside
    # frontend/tests/'s vitest include), so this pins the server half of the contract: the shell
    # must emit a base URL and a token the client can combine into one submit_action accepts.
    embed_response = await client.get("/api/v1/pxc/embed", params={"token": token})
    action_base_url = _extract_attr(embed_response.text, "data-action-url")
    shell_token = _extract_attr(embed_response.text, "data-pxc-token")

    action_url = f"{action_base_url}/answer.submit?token={shell_token}"
    response = await client.post(action_url, json=[0])

    assert response.status_code == 200


async def test_a_malformed_action_body_is_unprocessable_not_a_server_error(client: AsyncClient, token: str) -> None:
    # request.json() raises json.JSONDecodeError (a ValueError) on a body that is not valid
    # JSON, and this is a public route any browser can reach with nothing but a valid token.
    # Unmarked: the bad body is rejected before build_runtime ever touches the sandbox.
    response = await client.post(
        "/api/v1/pxc/actions/answer.submit",
        params={"token": token},
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
