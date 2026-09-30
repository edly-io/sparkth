"""Connecting and disconnecting Google Drive leaves an audit row that never
carries token material."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.audit.hooks import AUDIT_EVENTS
from sparkth.lib.auth import bind_request_user, get_current_user
from sparkth.lib.models import User, utc_now
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.main import app
from sparkth.plugins.googledrive.audit import DriveConnectedAuditEvent, DriveDisconnectedAuditEvent
from sparkth.plugins.googledrive.models import DriveOAuthToken
from sparkth.plugins.googledrive.oauth import get_token_record, get_valid_access_token

CALLBACK_URL = "/api/v1/google-drive/oauth/callback"
DISCONNECT_URL = "/api/v1/google-drive/oauth/disconnect"
SCOPES = "https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/drive.readonly"
ACCESS = "ya29.access-secret-value"
REFRESH = "1//refresh-secret-value"


@pytest.fixture
async def authed_client(drive_client: AsyncClient, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """``drive_client`` whose auth override binds the audit actor, as ``get_current_user`` does."""

    async def get_user_override() -> User:
        bind_request_user(test_user)
        return test_user

    app.dependency_overrides[get_current_user] = get_user_override
    yield drive_client


def _assert_no_token_material(canonical: bytes, *secrets: str) -> None:
    text = canonical.decode()
    for secret in secrets:
        assert secret not in text


async def _callback(drive_client: AsyncClient, user_id: int, token_data: dict[str, object]) -> int:
    with (
        patch("sparkth.plugins.googledrive.routes.oauth.decode_state", return_value={"user_id": user_id}),
        patch(
            "sparkth.plugins.googledrive.routes.oauth.exchange_code_for_tokens",
            new_callable=AsyncMock,
            return_value=token_data,
        ),
    ):
        response = await drive_client.get(
            CALLBACK_URL, params={"code": "code", "state": "state"}, follow_redirects=False
        )
    return response.status_code


def test_events_are_registered() -> None:
    assert AUDIT_EVENTS.get("googledrive.connected") is DriveConnectedAuditEvent
    assert AUDIT_EVENTS.get("googledrive.disconnected") is DriveDisconnectedAuditEvent


@pytest.mark.asyncio
async def test_callback_records_connected(
    drive_client: AsyncClient, session: AsyncSession, test_user: User, audit_events: AuditEventsFetcher
) -> None:
    user_id = cast(int, test_user.id)
    token_data = {"access_token": ACCESS, "refresh_token": REFRESH, "expires_in": 3600, "scope": SCOPES}

    assert await _callback(drive_client, user_id, token_data) == status.HTTP_307_TEMPORARY_REDIRECT

    record = await get_token_record(session, user_id)
    assert record is not None
    (event,) = await audit_events()
    assert (event.category, event.action) == ("googledrive", "connected")
    assert event.outcome == "success"
    assert event.actor_type == "user"
    assert event.actor_id == str(user_id)
    assert (event.target_type, event.target_id) == ("googledrive_connection", str(record.id))
    assert event.old_values is None
    assert event.new_values == {"scopes": SCOPES}
    _assert_no_token_material(
        event.canonical_bytes, ACCESS, REFRESH, record.access_token_encrypted, record.refresh_token_encrypted
    )


@pytest.mark.asyncio
async def test_reconnect_records_connected_on_existing_record(
    drive_client: AsyncClient,
    session: AsyncSession,
    test_user: User,
    test_oauth_token: DriveOAuthToken,
    audit_events: AuditEventsFetcher,
) -> None:
    user_id = cast(int, test_user.id)
    token_id = test_oauth_token.id
    token_data = {"access_token": ACCESS, "expires_in": 3600, "scope": SCOPES}

    assert await _callback(drive_client, user_id, token_data) == status.HTTP_307_TEMPORARY_REDIRECT

    (event,) = await audit_events()
    assert (event.category, event.action) == ("googledrive", "connected")
    assert event.target_id == str(token_id)
    assert event.new_values == {"scopes": SCOPES}
    _assert_no_token_material(event.canonical_bytes, ACCESS, "fake_refresh_token")


@pytest.mark.asyncio
async def test_failed_code_exchange_records_nothing(
    drive_client: AsyncClient, test_user: User, audit_events: AuditEventsFetcher
) -> None:
    with (
        patch("sparkth.plugins.googledrive.routes.oauth.decode_state", return_value={"user_id": test_user.id}),
        patch(
            "sparkth.plugins.googledrive.routes.oauth.exchange_code_for_tokens",
            new_callable=AsyncMock,
            side_effect=ValueError("bad code"),
        ),
    ):
        response = await drive_client.get(CALLBACK_URL, params={"code": "code", "state": "state"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert await audit_events() == []


@pytest.mark.asyncio
async def test_disconnect_records_disconnected(
    authed_client: AsyncClient,
    test_user: User,
    test_oauth_token: DriveOAuthToken,
    audit_events: AuditEventsFetcher,
) -> None:
    token_id = test_oauth_token.id
    encrypted = (test_oauth_token.access_token_encrypted, test_oauth_token.refresh_token_encrypted)
    with patch("sparkth.plugins.googledrive.routes.oauth.revoke_token", new_callable=AsyncMock, return_value=True):
        response = await authed_client.delete(DISCONNECT_URL)

    assert response.status_code == status.HTTP_200_OK
    (event,) = await audit_events()
    assert (event.category, event.action) == ("googledrive", "disconnected")
    assert event.outcome == "success"
    assert event.actor_id == str(test_user.id)
    assert event.actor_label == test_user.username
    assert (event.target_type, event.target_id) == ("googledrive_connection", str(token_id))
    assert event.old_values == {"scopes": "https://www.googleapis.com/auth/drive.file"}
    assert event.new_values is None
    _assert_no_token_material(event.canonical_bytes, "fake_access_token", "fake_refresh_token", *encrypted)


@pytest.mark.asyncio
async def test_disconnect_when_not_connected_records_nothing(
    drive_client: AsyncClient, audit_events: AuditEventsFetcher
) -> None:
    response = await drive_client.delete(DISCONNECT_URL)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert await audit_events() == []


@pytest.mark.asyncio
async def test_token_refresh_records_nothing(
    session: AsyncSession, test_user: User, test_oauth_token: DriveOAuthToken, audit_events: AuditEventsFetcher
) -> None:
    test_oauth_token.token_expiry = utc_now() - timedelta(minutes=1)
    session.add(test_oauth_token)
    await session.commit()

    with patch(
        "sparkth.plugins.googledrive.oauth.refresh_access_token",
        new_callable=AsyncMock,
        return_value={"access_token": ACCESS, "expires_in": 3600},
    ):
        token = await get_valid_access_token(session, cast(int, test_user.id), "cid", "secret")

    assert token == ACCESS
    assert await audit_events() == []


@pytest.mark.asyncio
async def test_connect_is_fail_closed(
    drive_client: AsyncClient, session: AsyncSession, test_user: User, audit_events: AuditEventsFetcher
) -> None:
    token_data = {"access_token": ACCESS, "refresh_token": REFRESH, "expires_in": 3600, "scope": SCOPES}
    with (
        patch("sparkth.plugins.googledrive.oauth.record_event", side_effect=SQLAlchemyError("audit down")),
        pytest.raises(SQLAlchemyError),
    ):
        await _callback(drive_client, cast(int, test_user.id), token_data)

    assert await get_token_record(session, cast(int, test_user.id)) is None
    assert await audit_events() == []


@pytest.mark.asyncio
async def test_disconnect_is_fail_closed(
    drive_client: AsyncClient,
    session: AsyncSession,
    test_user: User,
    test_oauth_token: DriveOAuthToken,
    audit_events: AuditEventsFetcher,
) -> None:
    user_id = cast(int, test_user.id)
    with (
        patch("sparkth.plugins.googledrive.routes.oauth.revoke_token", new_callable=AsyncMock, return_value=True),
        patch("sparkth.plugins.googledrive.oauth.record_event", side_effect=SQLAlchemyError("audit down")),
        pytest.raises(SQLAlchemyError),
    ):
        await drive_client.delete(DISCONNECT_URL)

    session.expire_all()
    assert await get_token_record(session, user_id) is not None
    assert await audit_events() == []
