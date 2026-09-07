from pathlib import Path

import pytest
from httpx import AsyncClient

from sparkth.plugins.pxc.tokens import mint_launch_token

SECRET = "shared-secret"


@pytest.fixture(autouse=True)
def launch_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.tokens.PXC_LAUNCH_SECRET", SECRET)
    monkeypatch.setattr("sparkth.plugins.pxc.activities.PXC_DATA_DIR", tmp_path)
    monkeypatch.setattr("sparkth.plugins.pxc.runtime.PXC_DATA_DIR", tmp_path)


@pytest.fixture
def token() -> str:
    return mint_launch_token("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7", SECRET, 300)


async def test_config_without_a_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/config")

    assert response.status_code == 422


async def test_config_with_a_bad_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/config", params={"token": "not-a-token"})

    assert response.status_code == 401


async def test_an_action_with_a_bad_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.post("/api/v1/pxc/actions/answer.submit", params={"token": "not-a-token"}, json=[1])

    assert response.status_code == 401


async def test_the_embed_shell_renders_the_activity_element(client: AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/pxc/embed", params={"token": token})

    assert response.status_code == 200
    assert "pxc-activity" in response.text
    assert token in response.text


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


@pytest.mark.wasm
async def test_an_undeclared_action_is_unprocessable(client: AsyncClient, token: str) -> None:
    response = await client.post("/api/v1/pxc/actions/no.such.action", params={"token": token}, json=[])

    assert response.status_code == 422
