"""Integration tests for Slack OAuth routes."""

import time
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core_plugins.slack.models import BotResponseLog, SlackWorkspace


class TestGetAuthorizationUrl:
    @pytest.mark.asyncio
    async def test_returns_slack_install_url(self, slack_client: AsyncClient) -> None:
        response = await slack_client.get("/api/v1/slack/oauth/authorize")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "url" in data
        assert "slack.com" in data["url"]
        assert "client_id=fake_client_id" in data["url"]


class TestConnectionStatus:
    @pytest.mark.asyncio
    async def test_not_connected(self, slack_client: AsyncClient) -> None:
        response = await slack_client.get("/api/v1/slack/oauth/status")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["connected"] is False

    @pytest.mark.asyncio
    async def test_connected(self, slack_client: AsyncClient, test_workspace: SlackWorkspace) -> None:
        response = await slack_client.get("/api/v1/slack/oauth/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connected"] is True
        assert data["team_name"] == "Test Workspace"
        assert data["team_id"] == "T123ABC"


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_not_connected_returns_404(self, slack_client: AsyncClient) -> None:
        response = await slack_client.delete("/api/v1/slack/oauth/disconnect")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_disconnects_successfully(self, slack_client: AsyncClient, test_workspace: SlackWorkspace) -> None:
        response = await slack_client.delete("/api/v1/slack/oauth/disconnect")

        assert response.status_code == status.HTTP_200_OK
        assert "disconnected" in response.json()["detail"]

        # Status should now be not connected
        status_resp = await slack_client.get("/api/v1/slack/oauth/status")
        assert status_resp.json()["connected"] is False


class TestOAuthCallback:
    @pytest.mark.asyncio
    async def test_valid_callback_saves_workspace_and_redirects(
        self, slack_client: AsyncClient, test_user: object
    ) -> None:
        fake_token_data = {
            "ok": True,
            "access_token": "xoxb-new-token",
            "bot_user_id": "U_NEW_BOT",
            "team": {"id": "T_NEW", "name": "New Team"},
        }
        from app.core_plugins.slack.oauth import generate_state

        state = generate_state(user_id=cast(int, getattr(test_user, "id")))

        with patch(
            "app.core_plugins.slack.routes.exchange_code_for_tokens",
            new_callable=AsyncMock,
            return_value=fake_token_data,
        ):
            response = await slack_client.get(
                "/api/v1/slack/oauth/callback",
                params={"code": "valid_code", "state": state},
                follow_redirects=False,
            )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert "/dashboard/slack?connected=true" in response.headers["location"]

    @pytest.mark.asyncio
    async def test_expired_state_returns_400(self, slack_client: AsyncClient) -> None:
        from itsdangerous import SignatureExpired

        with patch(
            "app.core_plugins.slack.routes.decode_state",
            side_effect=SignatureExpired("expired"),
        ):
            response = await slack_client.get(
                "/api/v1/slack/oauth/callback",
                params={"code": "code", "state": "expired_state"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "expired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_slack_api_error_returns_400(self, slack_client: AsyncClient, test_user: object) -> None:
        from app.core_plugins.slack.oauth import generate_state

        state = generate_state(user_id=cast(int, getattr(test_user, "id")))

        with patch(
            "app.core_plugins.slack.routes.exchange_code_for_tokens",
            new_callable=AsyncMock,
            side_effect=ValueError("invalid_code"),
        ):
            response = await slack_client.get(
                "/api/v1/slack/oauth/callback",
                params={"code": "bad_code", "state": state},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestSlackEvents:
    @pytest.mark.asyncio
    async def test_url_verification_returns_challenge(self, slack_client: AsyncClient) -> None:
        payload = {"type": "url_verification", "challenge": "3eZbrw1aBm"}
        with patch("app.core_plugins.slack.routes.get_settings") as mock_settings:
            mock_settings.return_value.SLACK_SIGNING_SECRET = ""
            response = await slack_client.post(
                "/api/v1/slack/events",
                json=payload,
                headers={"X-Slack-Request-Timestamp": "0", "X-Slack-Signature": "v0=skip"},
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["challenge"] == "3eZbrw1aBm"

    @pytest.mark.asyncio
    async def test_bad_signature_returns_403(self, slack_client: AsyncClient) -> None:
        with patch("app.core_plugins.slack.routes.get_settings") as mock_settings:
            mock_settings.return_value.SLACK_SIGNING_SECRET = "real_secret"

            response = await slack_client.post(
                "/api/v1/slack/events",
                json={"type": "event_callback"},
                headers={
                    "X-Slack-Request-Timestamp": str(int(time.time())),
                    "X-Slack-Signature": "v0=badsignature",
                },
            )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_event_callback_unknown_team_returns_ok(self, slack_client: AsyncClient) -> None:
        payload = {
            "type": "event_callback",
            "team_id": "T_UNKNOWN",
            "event": {"type": "app_mention", "text": "<@BOT> hi", "user": "U1", "channel": "C1"},
        }
        with patch("app.core_plugins.slack.routes.get_settings") as mock_settings:
            mock_settings.return_value.SLACK_SIGNING_SECRET = ""
            response = await slack_client.post(
                "/api/v1/slack/events",
                json=payload,
                headers={"X-Slack-Request-Timestamp": "0", "X-Slack-Signature": "v0=skip"},
            )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"ok": "true"}

    @pytest.mark.asyncio
    async def test_event_callback_dispatches_background_task(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
    ) -> None:
        payload = {
            "type": "event_callback",
            "team_id": test_workspace.team_id,
            "event": {
                "type": "app_mention",
                "text": f"<@{test_workspace.bot_user_id}> what is a loop?",
                "user": "U_STUDENT",
                "channel": "C_CHANNEL",
                "ts": "1234567890.000001",
            },
        }
        with (
            patch("app.core_plugins.slack.routes.get_settings") as mock_settings,
            patch("app.core_plugins.slack.routes._dispatch_event", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_settings.return_value.SLACK_SIGNING_SECRET = ""
            response = await slack_client.post(
                "/api/v1/slack/events",
                json=payload,
                headers={"X-Slack-Request-Timestamp": "0", "X-Slack-Signature": "v0=skip"},
            )

        assert response.status_code == status.HTTP_200_OK
        mock_dispatch.assert_called_once()
        kwargs = mock_dispatch.call_args.kwargs
        assert kwargs["workspace_id"] == test_workspace.id
        assert kwargs["user_id"] == test_workspace.user_id
        assert kwargs["event"]["type"] == "app_mention"
        assert "what is a loop?" in kwargs["event"]["text"]


class TestDispatchEventGreeting:
    @pytest.mark.asyncio
    async def test_greeting_skips_rag_and_posts_greeting_message(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
    ) -> None:
        payload = {
            "type": "event_callback",
            "team_id": test_workspace.team_id,
            "event": {
                "type": "app_mention",
                "text": f"<@{test_workspace.bot_user_id}> hi",
                "user": "U_STUDENT",
                "channel": "C_CHANNEL",
                "ts": "1234567890.000001",
            },
        }
        with (
            patch("app.core_plugins.slack.routes.get_settings") as mock_settings,
            patch("app.core_plugins.slack.routes._dispatch_event", new_callable=AsyncMock) as mock_dispatch,
        ):
            mock_settings.return_value.SLACK_SIGNING_SECRET = ""
            response = await slack_client.post(
                "/api/v1/slack/events",
                json=payload,
                headers={"X-Slack-Request-Timestamp": "0", "X-Slack-Signature": "v0=skip"},
            )

        assert response.status_code == status.HTTP_200_OK
        mock_dispatch.assert_called_once()
        kwargs = mock_dispatch.call_args.kwargs
        assert "hi" in kwargs["event"]["text"]


class TestGetLogs:
    @pytest.mark.asyncio
    async def test_no_workspace_returns_404(self, slack_client: AsyncClient) -> None:
        response = await slack_client.get("/api/v1/slack/logs")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_returns_empty_logs(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
    ) -> None:
        response = await slack_client.get("/api/v1/slack/logs")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_existing_log_entry(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
        sync_session: Any,
    ) -> None:
        log = BotResponseLog(
            workspace_id=test_workspace.id,  # type: ignore[arg-type]
            slack_channel="C1",
            slack_user="U1",
            slack_ts="1234.0001",
            question="what is a loop?",
            answer="A loop repeats code.",
            rag_matched=True,
        )
        sync_session.add(log)
        sync_session.commit()

        response = await slack_client.get("/api/v1/slack/logs")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["question"] == "what is a loop?"
        assert item["rag_matched"] is True
        assert item["answer"] == "A loop repeats code."
