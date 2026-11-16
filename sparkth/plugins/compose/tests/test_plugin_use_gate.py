"""Compose's authoring routes need ``plugin.use`` at ``plugin:compose``."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.lib.testing import AuditEventsFetcher, assert_plugin_use_denied, restrict_plugin_use
from sparkth.plugins.compose.constants import COMPOSE_PLUGIN_NAME

BASE = "/api/v1/compose"
UNKNOWN = "11111111-1111-4111-8111-111111111111"
CONVERSATION = f"{BASE}/conversations/{UNKNOWN}"
COMPLETION_BODY = {"llm_config_id": 1, "messages": [{"role": "user", "content": "hi"}]}

# method, url, body, the status a caller who may use the plugin gets (every id is unknown).
ROUTES = [
    pytest.param("POST", f"{BASE}/completions", COMPLETION_BODY, 404, id="completions"),
    pytest.param("POST", f"{BASE}/turns/{UNKNOWN}/stop", None, 404, id="stop"),
    pytest.param("GET", f"{BASE}/conversations", None, 200, id="list-conversations"),
    pytest.param("GET", CONVERSATION, None, 404, id="get-conversation"),
    pytest.param("GET", f"{CONVERSATION}/last-message", None, 404, id="last-message"),
    pytest.param("GET", f"{CONVERSATION}/attachments", None, 404, id="list-attachments"),
    pytest.param("POST", f"{CONVERSATION}/attachments", {"document_id": 1}, 404, id="attach"),
    pytest.param("DELETE", f"{CONVERSATION}/attachments/1", None, 404, id="detach"),
]


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
    await assert_plugin_use_denied(audit_events, COMPOSE_PLUGIN_NAME)


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
async def test_grant_at_compose_only_passes_the_gate(
    method: str,
    url: str,
    body: dict[str, object] | None,
    expected: int,
    client: AsyncClient,
    current_user: User,
    session: AsyncSession,
) -> None:
    await restrict_plugin_use(session, COMPOSE_PLUGIN_NAME)

    response = await client.request(method, url, json=body)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "body", "expected"), ROUTES)
async def test_anonymous_caller_is_unauthorized(
    method: str, url: str, body: dict[str, object] | None, expected: int, client: AsyncClient
) -> None:
    response = await client.request(method, url, json=body)

    assert response.status_code == 401
