"""Compose's authoring routes need ``plugin.use`` at ``plugin:compose``."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.lib.permissions import PLUGIN_USE, PLUGIN_USER_ROLE, revoke_role
from sparkth.lib.permissions.scopes import GLOBAL, PLUGIN
from sparkth.lib.testing import AuditEventsFetcher, grant_permission_at_scope

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


async def _grant_use_at(session: AsyncSession, plugin_name: str) -> None:
    await revoke_role(1, PLUGIN_USER_ROLE, GLOBAL, None, session)
    await grant_permission_at_scope(session, 1, PLUGIN_USE.name, PLUGIN, plugin_name)
    await session.commit()


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
    await revoke_role(1, PLUGIN_USER_ROLE, GLOBAL, None, session)
    await session.commit()

    response = await client.request(method, url, json=body)

    assert response.status_code == 403
    event = (await audit_events())[-1]
    assert event.action == "denied"
    assert event.target_id == "plugin.use"
    assert event.error_detail == "scope=plugin:compose"


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
    await _grant_use_at(session, "pxc")

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
    await _grant_use_at(session, "compose")

    response = await client.request(method, url, json=body)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "body", "expected"), ROUTES)
async def test_anonymous_caller_is_unauthorized(
    method: str, url: str, body: dict[str, object] | None, expected: int, client: AsyncClient
) -> None:
    response = await client.request(method, url, json=body)

    assert response.status_code == 401
