"""Integration tests for Slack OAuth routes."""

from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core_plugins.slack.models import SlackWorkspace


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
