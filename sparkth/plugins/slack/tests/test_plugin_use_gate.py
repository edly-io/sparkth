"""Slack routes need ``plugin.use`` at ``plugin:slack``, except the OAuth callback and the events webhook."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.lib.testing import AuditEventsFetcher, assert_plugin_use_denied, restrict_plugin_use
from sparkth.plugins.slack.constants import SLACK_PLUGIN_NAME
from sparkth.plugins.slack.oauth import generate_state
from sparkth.plugins.slack.tests.conftest import signed_event_headers

BASE = "/api/v1/slack"
SIGNING_SECRET = "test-signing-secret"

pytestmark = pytest.mark.usefixtures("mock_slack_credentials")

# method, url, the status a caller who may use the plugin gets.
ROUTES = [
    pytest.param("GET", f"{BASE}/oauth/authorize", 200, id="oauth-authorize"),
    pytest.param("DELETE", f"{BASE}/oauth/disconnect", 404, id="oauth-disconnect"),
    pytest.param("GET", f"{BASE}/oauth/status", 200, id="oauth-status"),
    pytest.param("GET", f"{BASE}/logs", 404, id="logs"),
    pytest.param("GET", f"{BASE}/rag/sources", 200, id="rag-sources"),
]


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_default_roles_keep_the_routes_status(
    method: str, url: str, expected: int, client: AsyncClient, current_user: User
) -> None:
    response = await client.request(method, url)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_caller_without_a_grant_is_denied_and_audited(
    method: str,
    url: str,
    expected: int,
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
    audit_events: AuditEventsFetcher,
) -> None:
    await restrict_plugin_use(session, None)

    response = await client.request(method, url)

    assert response.status_code == 403
    await assert_plugin_use_denied(audit_events, SLACK_PLUGIN_NAME)


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_grant_at_another_plugin_is_denied(
    method: str, url: str, expected: int, client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    await restrict_plugin_use(session, "pxc")

    response = await client.request(method, url)

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_grant_at_slack_only_passes_the_gate(
    method: str, url: str, expected: int, client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    await restrict_plugin_use(session, SLACK_PLUGIN_NAME)

    response = await client.request(method, url)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_anonymous_caller_is_unauthorized(method: str, url: str, expected: int, client: AsyncClient) -> None:
    response = await client.request(method, url)

    assert response.status_code == 401


async def test_callback_needs_no_plugin_use(
    client: AsyncClient, test_user: User, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await restrict_plugin_use(session, None)
    token_data = {
        "ok": True,
        "access_token": "xoxb-new-token",
        "bot_user_id": "U_NEW_BOT",
        "team": {"id": "T_NEW", "name": "New Team"},
    }
    with patch(
        "sparkth.plugins.slack.routes.oauth.exchange_code_for_tokens",
        new_callable=AsyncMock,
        return_value=token_data,
    ):
        response = await client.get(
            f"{BASE}/oauth/callback",
            params={"code": "code", "state": generate_state(user_id=1)},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert [event for event in await audit_events() if event.action == "denied"] == []


async def test_events_need_no_plugin_use(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await restrict_plugin_use(session, None)
    body = json.dumps({"type": "url_verification", "challenge": "3eZbrw1aBm"}).encode()
    with patch("sparkth.plugins.slack.routes.get_slack_settings") as mock_settings:
        mock_settings.return_value.signing_secret = SIGNING_SECRET
        response = await client.post(f"{BASE}/events", content=body, headers=signed_event_headers(SIGNING_SECRET, body))

    assert response.status_code == 200
    assert response.json() == {"challenge": "3eZbrw1aBm"}
    assert [event for event in await audit_events() if event.action == "denied"] == []
