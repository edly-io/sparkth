"""PXC's authoring routes need ``plugin.use`` at ``plugin:pxc``; its learner routes need no login."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.models import User
from sparkth.lib.permissions import PLUGIN_USE, PLUGIN_USER_ROLE, revoke_role
from sparkth.lib.permissions.scopes import GLOBAL, PLUGIN
from sparkth.lib.testing import AuditEventsFetcher, grant_permission_at_scope

BASE = "/api/v1/pxc"
UNKNOWN = "11111111-1111-4111-8111-111111111111"

# method, url, the status a caller who may use the plugin gets (every id is unknown).
ROUTES = [
    pytest.param("GET", f"{BASE}/activities", 200, id="list"),
    pytest.param("GET", f"{BASE}/activities/{UNKNOWN}/launch?permission=play", 404, id="launch"),
    pytest.param("DELETE", f"{BASE}/activities/{UNKNOWN}", 404, id="delete"),
]


@pytest.fixture(autouse=True)
def _launch_secret(configured_secret: str) -> None:  # noqa: PT004
    """Configure the launch secret, so a launch reaches its own not-found answer."""


async def _grant_use_at(session: AsyncSession, plugin_name: str) -> None:
    await revoke_role(1, PLUGIN_USER_ROLE, GLOBAL, None, session)
    await grant_permission_at_scope(session, 1, PLUGIN_USE.name, PLUGIN, plugin_name)
    await session.commit()


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
    await revoke_role(1, PLUGIN_USER_ROLE, GLOBAL, None, session)
    await session.commit()

    response = await client.request(method, url)

    assert response.status_code == 403
    event = (await audit_events())[-1]
    assert event.action == "denied"
    assert event.target_id == "plugin.use"
    assert event.error_detail == "scope=plugin:pxc"


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_grant_at_another_plugin_is_denied(
    method: str, url: str, expected: int, client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    await _grant_use_at(session, "compose")

    response = await client.request(method, url)

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_grant_at_pxc_only_passes_the_gate(
    method: str, url: str, expected: int, client: AsyncClient, current_user: User, session: AsyncSession
) -> None:
    await _grant_use_at(session, "pxc")

    response = await client.request(method, url)

    assert response.status_code == expected


@pytest.mark.parametrize(("method", "url", "expected"), ROUTES)
async def test_anonymous_caller_is_unauthorized(method: str, url: str, expected: int, client: AsyncClient) -> None:
    response = await client.request(method, url)

    assert response.status_code == 401


async def test_learner_route_answers_a_caller_without_a_grant(
    client: AsyncClient, current_user: User, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await revoke_role(1, PLUGIN_USER_ROLE, GLOBAL, None, session)
    await session.commit()

    response = await client.get(f"{BASE}/client/pxc.js")

    assert response.status_code == 200
    assert [event for event in await audit_events() if event.action == "denied"] == []
