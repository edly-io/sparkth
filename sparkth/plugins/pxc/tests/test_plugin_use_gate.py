"""PXC's authoring routes need ``plugin.use`` at ``plugin:pxc``; its learner routes need no login."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.lib.testing import AuditEventsFetcher, assert_plugin_use_denied, restrict_plugin_use
from sparkth.plugins.pxc.constants import PXC_PLUGIN_NAME

pytestmark = pytest.mark.usefixtures("configured_secret")

BASE = "/api/v1/pxc"
UNKNOWN = "11111111-1111-4111-8111-111111111111"

# method, url, the status a caller who may use the plugin gets (every id is unknown).
ROUTES = [
    pytest.param("GET", f"{BASE}/activities", 200, id="list"),
    pytest.param("GET", f"{BASE}/activities/{UNKNOWN}/launch?permission=play", 404, id="launch"),
    pytest.param("DELETE", f"{BASE}/activities/{UNKNOWN}", 404, id="delete"),
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
    await assert_plugin_use_denied(audit_events, PXC_PLUGIN_NAME)


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_grant_at_another_plugin_is_denied(
    method: str, url: str, expected: int, client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    await restrict_plugin_use(session, "compose")

    response = await client.request(method, url)

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_grant_at_pxc_only_passes_the_gate(
    method: str, url: str, expected: int, client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    await restrict_plugin_use(session, PXC_PLUGIN_NAME)

    response = await client.request(method, url)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_anonymous_caller_is_unauthorized(method: str, url: str, expected: int, client: AsyncClient) -> None:
    response = await client.request(method, url)

    assert response.status_code == 401


async def test_learner_route_answers_a_caller_without_a_grant(
    client: AsyncClient, current_user: User, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await restrict_plugin_use(session, None)

    response = await client.get(f"{BASE}/client/pxc.js")

    assert response.status_code == 200
    assert [event for event in await audit_events() if event.action == "denied"] == []
