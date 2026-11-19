"""Drive routes need ``plugin.use`` at the Drive plugin's scope, except the OAuth callback and the analytics read."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.lib.testing import AuditEventsFetcher, assert_plugin_use_denied, restrict_plugin_use
from sparkth.plugins.googledrive.constants import GOOGLE_DRIVE_PLUGIN_NAME

BASE = f"/api/v1/{GOOGLE_DRIVE_PLUGIN_NAME}"
TOKEN_STUB_STATUS = 400

pytestmark = pytest.mark.usefixtures("mock_drive_credentials")

# method, url, body, the status a caller who may use the plugin gets (every id is unknown).
ROUTES = [
    pytest.param("GET", f"{BASE}/folders", None, 200, id="list-folders"),
    pytest.param("POST", f"{BASE}/folders/sync", {"drive_folder_id": "abc"}, TOKEN_STUB_STATUS, id="sync-folder"),
    pytest.param("POST", f"{BASE}/folders/1/refresh", None, 404, id="refresh-folder"),
    pytest.param("GET", f"{BASE}/folders/1/files", None, 404, id="list-files"),
    pytest.param("GET", f"{BASE}/folders/1/rag-status", None, 404, id="folder-rag-status"),
    pytest.param("GET", f"{BASE}/files/1", None, 404, id="get-file"),
    pytest.param("GET", f"{BASE}/files/1/rag-status", None, 404, id="file-rag-status"),
    pytest.param("GET", f"{BASE}/files/1/download", None, 404, id="download-file"),
    pytest.param("DELETE", f"{BASE}/files/1", None, 404, id="delete-file"),
    pytest.param("GET", f"{BASE}/browse", None, TOKEN_STUB_STATUS, id="browse"),
    pytest.param("GET", f"{BASE}/oauth/authorize", None, 200, id="oauth-authorize"),
    pytest.param("DELETE", f"{BASE}/oauth/disconnect", None, 404, id="oauth-disconnect"),
    pytest.param("GET", f"{BASE}/oauth/status", None, 200, id="oauth-status"),
]


@pytest.fixture(autouse=True)
def _stub_token_lookup() -> Iterator[None]:
    """Make the token lookup fail with a 400, so token-needing routes stop right after their gates."""
    refusal = AsyncMock(side_effect=HTTPException(TOKEN_STUB_STATUS, "Google Drive not connected"))
    with (
        patch("sparkth.plugins.googledrive.routes.folders.get_valid_access_token", refusal),
        patch("sparkth.plugins.googledrive.routes.files.get_valid_access_token", refusal),
    ):
        yield


@pytest.mark.parametrize(("method", "url", "body", "expected"), ROUTES)
async def test_default_roles_keep_the_routes_status(
    method: str, url: str, body: dict[str, object] | None, expected: int, client: AsyncClient, current_user: User
) -> None:
    response = await client.request(method, url, json=body)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "body", "expected"), ROUTES)
async def test_caller_without_a_grant_is_denied_and_audited(
    method: str,
    url: str,
    body: dict[str, object] | None,
    expected: int,
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    audit_events: AuditEventsFetcher,
) -> None:
    await restrict_plugin_use(session, None)

    response = await client.request(method, url, json=body)

    assert response.status_code == 403
    await assert_plugin_use_denied(audit_events, GOOGLE_DRIVE_PLUGIN_NAME)


@pytest.mark.parametrize(("method", "url", "body", "expected"), ROUTES)
async def test_grant_at_another_plugin_is_denied(
    method: str,
    url: str,
    body: dict[str, object] | None,
    expected: int,
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
) -> None:
    await restrict_plugin_use(session, "pxc")

    response = await client.request(method, url, json=body)

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "url", "body", "expected"), ROUTES)
async def test_grant_at_google_drive_only_passes_the_gate(
    method: str,
    url: str,
    body: dict[str, object] | None,
    expected: int,
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
) -> None:
    await restrict_plugin_use(session, GOOGLE_DRIVE_PLUGIN_NAME)

    response = await client.request(method, url, json=body)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "body", "expected"), ROUTES)
async def test_anonymous_caller_is_unauthorized(
    method: str, url: str, body: dict[str, object] | None, expected: int, client: AsyncClient
) -> None:
    response = await client.request(method, url, json=body)

    assert response.status_code == 401


async def test_callback_needs_no_plugin_use(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await restrict_plugin_use(session, None)
    token_data = {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600, "scope": ""}
    with (
        patch("sparkth.plugins.googledrive.routes.oauth.decode_state", return_value={"user_id": 1}),
        patch(
            "sparkth.plugins.googledrive.routes.oauth.exchange_code_for_tokens",
            new_callable=AsyncMock,
            return_value=token_data,
        ),
    ):
        response = await client.get(
            f"{BASE}/oauth/callback", params={"code": "code", "state": "state"}, follow_redirects=False
        )

    assert response.status_code == 307
    assert response.headers["location"] == f"/dashboard/{GOOGLE_DRIVE_PLUGIN_NAME}?connected=true"
    assert [event for event in await audit_events() if event.action == "denied"] == []
