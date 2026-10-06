"""Connecting and disconnecting a Slack workspace leaves an audit row that
never carries the bot token."""

from collections.abc import AsyncGenerator
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.audit.hooks import AUDIT_EVENTS
from sparkth.lib.auth import bind_request_user, get_current_user
from sparkth.lib.models import User
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.main import app
from sparkth.plugins.slack.audit import SlackConnectedAuditEvent, SlackDisconnectedAuditEvent
from sparkth.plugins.slack.models import SlackWorkspace
from sparkth.plugins.slack.oauth import generate_state

CALLBACK_URL = "/api/v1/slack/oauth/callback"
DISCONNECT_URL = "/api/v1/slack/oauth/disconnect"
BOT_TOKEN = "xoxb-new-secret-token"
TOKEN_DATA = {
    "ok": True,
    "access_token": BOT_TOKEN,
    "bot_user_id": "U_NEW_BOT",
    "team": {"id": "T_NEW", "name": "New Team"},
}


@pytest.fixture
async def authed_client(slack_client: AsyncClient, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """``slack_client`` whose auth override binds the audit actor, as ``get_current_user`` does."""

    async def get_user_override() -> User:
        bind_request_user(test_user)
        return test_user

    app.dependency_overrides[get_current_user] = get_user_override
    yield slack_client


async def _callback(slack_client: AsyncClient, user_id: int) -> int:
    with patch(
        "sparkth.plugins.slack.routes.oauth.exchange_code_for_tokens",
        new_callable=AsyncMock,
        return_value=TOKEN_DATA,
    ):
        response = await slack_client.get(
            CALLBACK_URL,
            params={"code": "code", "state": generate_state(user_id=user_id)},
            follow_redirects=False,
        )
    return response.status_code


def test_events_are_registered() -> None:
    assert AUDIT_EVENTS.get("slack.connected") is SlackConnectedAuditEvent
    assert AUDIT_EVENTS.get("slack.disconnected") is SlackDisconnectedAuditEvent


@pytest.mark.asyncio
async def test_callback_records_connected(
    slack_client: AsyncClient, session: AsyncSession, test_user: User, audit_events: AuditEventsFetcher
) -> None:
    user_id = cast(int, test_user.id)

    assert await _callback(slack_client, user_id) == status.HTTP_307_TEMPORARY_REDIRECT

    workspace = (await session.exec(select(SlackWorkspace).where(SlackWorkspace.team_id == "T_NEW"))).one()
    (event,) = await audit_events()
    assert (event.category, event.action) == ("slack", "connected")
    assert event.outcome == "success"
    assert event.actor_type == "user"
    assert event.actor_id == str(user_id)
    assert (event.target_type, event.target_id) == ("slack_workspace", str(workspace.id))
    assert event.old_values is None
    assert event.new_values == {"team_id": "T_NEW", "bot_user_id": "U_NEW_BOT"}
    text = event.canonical_bytes.decode()
    assert BOT_TOKEN not in text
    assert workspace.bot_token_encrypted not in text


@pytest.mark.asyncio
async def test_rejected_connect_records_nothing(
    slack_client: AsyncClient, test_user: User, test_workspace: SlackWorkspace, audit_events: AuditEventsFetcher
) -> None:
    assert await _callback(slack_client, cast(int, test_user.id)) == status.HTTP_409_CONFLICT
    assert await audit_events() == []


@pytest.mark.asyncio
async def test_disconnect_records_disconnected(
    authed_client: AsyncClient, test_user: User, test_workspace: SlackWorkspace, audit_events: AuditEventsFetcher
) -> None:
    workspace_id = test_workspace.id
    encrypted = test_workspace.bot_token_encrypted

    response = await authed_client.delete(DISCONNECT_URL)

    assert response.status_code == status.HTTP_200_OK
    (event,) = await audit_events()
    assert (event.category, event.action) == ("slack", "disconnected")
    assert event.outcome == "success"
    assert event.actor_id == str(test_user.id)
    assert event.actor_label == test_user.username
    assert (event.target_type, event.target_id) == ("slack_workspace", str(workspace_id))
    assert event.old_values == {"team_id": "T123ABC", "bot_user_id": "U_BOT_ID"}
    assert event.new_values is None
    text = event.canonical_bytes.decode()
    assert "xoxb-fake-bot-token" not in text
    assert encrypted not in text


@pytest.mark.asyncio
async def test_disconnect_when_not_connected_records_nothing(
    slack_client: AsyncClient, audit_events: AuditEventsFetcher
) -> None:
    response = await slack_client.delete(DISCONNECT_URL)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert await audit_events() == []


@pytest.mark.asyncio
async def test_connect_is_fail_closed(
    slack_client: AsyncClient, session: AsyncSession, test_user: User, audit_events: AuditEventsFetcher
) -> None:
    with (
        patch("sparkth.plugins.slack.service.record_event", side_effect=SQLAlchemyError("audit down")),
        pytest.raises(SQLAlchemyError),
    ):
        await _callback(slack_client, cast(int, test_user.id))

    assert (await session.exec(select(SlackWorkspace))).all() == []
    assert await audit_events() == []


@pytest.mark.asyncio
async def test_disconnect_is_fail_closed(
    slack_client: AsyncClient,
    session: AsyncSession,
    test_workspace: SlackWorkspace,
    audit_events: AuditEventsFetcher,
) -> None:
    with (
        patch("sparkth.plugins.slack.service.record_event", side_effect=SQLAlchemyError("audit down")),
        pytest.raises(SQLAlchemyError),
    ):
        await slack_client.delete(DISCONNECT_URL)

    await session.refresh(test_workspace)
    assert test_workspace.is_active
    assert not test_workspace.is_deleted
    assert await audit_events() == []
