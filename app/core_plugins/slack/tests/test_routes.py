"""Integration tests for Slack OAuth routes."""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.constants import (
    AI_KEY_UNAVAILABLE_MESSAGE,
    NO_AI_KEY_MESSAGE,
    RETRIEVAL_ERROR_MESSAGE,
    SYNTHESIS_SYSTEM_PROMPT,
)
from app.core_plugins.slack.models import (
    BotResponseLog,
    ConnectionEventType,
    ResponseType,
    SlackConnectionLog,
    SlackWorkspace,
)
from app.core_plugins.slack.routes import _dispatch_event
from app.main import app
from app.models.user import User


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
        assert data["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_message_item_has_correct_shape(
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
            response_type=ResponseType.rag_match,
            slack_user_name="alice",
            slack_channel_name="general",
        )
        sync_session.add(log)
        sync_session.commit()

        response = await slack_client.get("/api/v1/slack/logs")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["type"] == "message"
        assert item["question"] == "what is a loop?"
        assert item["rag_matched"] is True
        assert item["response_type"] == "rag_match"
        assert item["slack_user_name"] == "alice"
        assert item["slack_channel_name"] == "general"

    @pytest.mark.asyncio
    async def test_connection_item_appears_in_stream(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
        sync_session: Any,
    ) -> None:
        sync_session.add(
            SlackConnectionLog(
                workspace_id=test_workspace.id,  # type: ignore[arg-type]
                event_type=ConnectionEventType.connected,
                team_name="Test Workspace",
            )
        )
        sync_session.commit()

        response = await slack_client.get("/api/v1/slack/logs")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["type"] == "connection"
        assert item["event_type"] == "connected"
        assert item["team_name"] == "Test Workspace"

    @pytest.mark.asyncio
    async def test_merged_stream_sorted_newest_first(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
        sync_session: Any,
    ) -> None:
        base = datetime.now(timezone.utc)

        msg_log = BotResponseLog(
            workspace_id=test_workspace.id,  # type: ignore[arg-type]
            slack_channel="C1",
            slack_user="U1",
            slack_ts="100.0",
            question="q1",
            answer="a1",
            rag_matched=False,
            response_type=ResponseType.fallback,
            created_at=base - timedelta(seconds=1),
        )
        sync_session.add(msg_log)
        sync_session.commit()

        conn_log = SlackConnectionLog(
            workspace_id=test_workspace.id,  # type: ignore[arg-type]
            event_type=ConnectionEventType.connected,
            team_name="Test Workspace",
            created_at=base,
        )
        sync_session.add(conn_log)
        sync_session.commit()

        response = await slack_client.get("/api/v1/slack/logs")
        data = response.json()
        assert data["total"] == 2
        assert data["items"][0]["type"] == "connection"
        assert data["items"][1]["type"] == "message"

    @pytest.mark.asyncio
    async def test_next_cursor_is_iso_timestamp(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
        sync_session: Any,
    ) -> None:
        base = datetime.now(timezone.utc)

        for i in range(3):
            sync_session.add(
                BotResponseLog(
                    workspace_id=test_workspace.id,  # type: ignore[arg-type]
                    slack_channel="C1",
                    slack_user="U1",
                    slack_ts=f"100{i}.0",
                    question=f"q{i}",
                    answer=f"a{i}",
                    rag_matched=False,
                    response_type=ResponseType.fallback,
                    created_at=base - timedelta(seconds=2 - i),
                )
            )
            sync_session.commit()

        response = await slack_client.get("/api/v1/slack/logs?limit=2")
        data = response.json()
        assert data["has_more"] is True
        cursor = data["next_cursor"]
        assert isinstance(cursor, str)
        ts_part, id_part, type_part = cursor.split("|")
        datetime.fromisoformat(ts_part)
        assert int(id_part) == data["items"][-1]["id"]
        assert type_part == data["items"][-1]["type"]

    @pytest.mark.asyncio
    async def test_timestamp_cursor_returns_older_entries(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
        sync_session: Any,
    ) -> None:
        base = datetime.now(timezone.utc)

        ids = []
        for i in range(3):
            log = BotResponseLog(
                workspace_id=test_workspace.id,  # type: ignore[arg-type]
                slack_channel="C1",
                slack_user="U1",
                slack_ts=f"100{i}.0",
                question=f"q{i}",
                answer=f"a{i}",
                rag_matched=False,
                response_type=ResponseType.fallback,
                created_at=base - timedelta(seconds=2 - i),
            )
            sync_session.add(log)
            sync_session.commit()
            sync_session.refresh(log)
            ids.append(log.id)

        first = await slack_client.get("/api/v1/slack/logs?limit=2")
        first_data = first.json()
        assert len(first_data["items"]) == 2
        assert first_data["has_more"] is True
        cursor = first_data["next_cursor"]

        second = await slack_client.get(f"/api/v1/slack/logs?cursor={cursor}&limit=10")
        second_data = second.json()
        assert len(second_data["items"]) == 1
        assert second_data["items"][0]["id"] == ids[0]
        assert second_data["has_more"] is False

    @pytest.mark.asyncio
    async def test_since_id_returns_only_message_items(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
        sync_session: Any,
    ) -> None:
        base = datetime.now(timezone.utc)

        old_log = BotResponseLog(
            workspace_id=test_workspace.id,  # type: ignore[arg-type]
            slack_channel="C1",
            slack_user="U1",
            slack_ts="100.0",
            question="old question",
            answer="old answer",
            rag_matched=False,
            response_type=ResponseType.fallback,
            created_at=base - timedelta(seconds=2),
        )
        sync_session.add(old_log)
        sync_session.commit()
        sync_session.refresh(old_log)
        since = old_log.id

        sync_session.add(
            SlackConnectionLog(
                workspace_id=test_workspace.id,  # type: ignore[arg-type]
                event_type=ConnectionEventType.connected,
                team_name="Test Workspace",
                created_at=base - timedelta(seconds=1),
            )
        )
        sync_session.commit()

        new_log = BotResponseLog(
            workspace_id=test_workspace.id,  # type: ignore[arg-type]
            slack_channel="C1",
            slack_user="U1",
            slack_ts="200.0",
            question="new question",
            answer="new answer",
            rag_matched=True,
            response_type=ResponseType.rag_match,
            created_at=base,
        )
        sync_session.add(new_log)
        sync_session.commit()

        response = await slack_client.get(f"/api/v1/slack/logs?since_id={since}&limit=10")
        data = response.json()
        assert all(item["type"] == "message" for item in data["items"])
        questions = [item["question"] for item in data["items"]]
        assert questions == ["new question"]

    @pytest.mark.asyncio
    async def test_malformed_cursor_returns_400(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
    ) -> None:
        response = await slack_client.get("/api/v1/slack/logs?cursor=not-a-timestamp")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_cursor_and_since_id_together_returns_400(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
    ) -> None:
        response = await slack_client.get("/api/v1/slack/logs?cursor=2026-01-01T00:00:00&since_id=3")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_limit_bounds_enforced(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
    ) -> None:
        response = await slack_client.get("/api/v1/slack/logs?limit=0")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def _make_session_mock() -> tuple[AsyncMock, MagicMock]:
    """Return (mock_async_session_cls, mock_session) wired as a context manager."""
    mock_session = AsyncMock()
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_cls, mock_session


def _make_plugin_svc(user_plugin: MagicMock | None) -> AsyncMock:
    """Return a PluginService mock whose get_user_plugin_map returns the given plugin (or {})."""
    instance = AsyncMock()
    instance.get_user_plugin_map.return_value = {"slack": user_plugin} if user_plugin else {}
    return instance


def _make_slack_client_mock() -> AsyncMock:
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post_message = AsyncMock(return_value={"ts": "9999.0000"})
    return client


class TestDispatchEvent:
    """Unit tests for _dispatch_event — each test patches the full dependency chain."""

    @staticmethod
    def _base_patches(user_plugin: MagicMock | None, slack_client: AsyncMock) -> tuple[MagicMock, AsyncMock]:
        """Return (mock_session_cls, mock_plugin_svc) wired for standard dispatch calls."""
        mock_session_cls, _ = _make_session_mock()
        mock_plugin_svc = _make_plugin_svc(user_plugin)
        return mock_session_cls, mock_plugin_svc

    @pytest.mark.asyncio
    async def test_posts_not_configured_message_when_plugin_missing(self) -> None:
        """No UserPlugin row → post informative Slack message, do not process."""
        event = {"type": "app_mention", "text": "<@BOT> hi", "channel": "C1", "user": "U1", "ts": "1.0"}
        slack_client = _make_slack_client_mock()
        mock_session_cls, mock_plugin_svc = self._base_patches(None, slack_client)

        with (
            patch("app.core_plugins.slack.routes.PluginService", return_value=mock_plugin_svc),
            patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
            patch("app.core_plugins.slack.routes.SlackClient", return_value=slack_client),
            patch("app.core_plugins.slack.routes.session_scope", mock_session_cls),
        ):
            await _dispatch_event(workspace_id=1, user_id=1, bot_token_encrypted="enc", bot_user_id="BOT", event=event)

        slack_client.post_message.assert_awaited_once()
        _, kwargs = slack_client.post_message.call_args
        assert "hasn't been set up" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_posts_disabled_message_when_plugin_disabled(self) -> None:
        """Plugin exists but enabled=False → post informative Slack message, do not process."""
        event = {"type": "app_mention", "text": "<@BOT> hi", "channel": "C1", "user": "U1", "ts": "1.0"}
        user_plugin = MagicMock()
        user_plugin.enabled = False
        user_plugin.config = {"bot_name": "TA Bot"}
        slack_client = _make_slack_client_mock()
        mock_session_cls, mock_plugin_svc = self._base_patches(user_plugin, slack_client)

        with (
            patch("app.core_plugins.slack.routes.PluginService", return_value=mock_plugin_svc),
            patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
            patch("app.core_plugins.slack.routes.SlackClient", return_value=slack_client),
            patch("app.core_plugins.slack.routes.session_scope", mock_session_cls),
        ):
            await _dispatch_event(workspace_id=1, user_id=1, bot_token_encrypted="enc", bot_user_id="BOT", event=event)

        slack_client.post_message.assert_awaited_once()
        _, kwargs = slack_client.post_message.call_args
        assert "disabled" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_posts_incomplete_config_message_when_config_empty(self) -> None:
        """Plugin enabled but config is empty → post informative message, do not process."""
        event = {"type": "app_mention", "text": "<@BOT> hi", "channel": "C1", "user": "U1", "ts": "1.0"}
        user_plugin = MagicMock()
        user_plugin.enabled = True
        user_plugin.config = {}
        slack_client = _make_slack_client_mock()
        mock_session_cls, mock_plugin_svc = self._base_patches(user_plugin, slack_client)

        with (
            patch("app.core_plugins.slack.routes.PluginService", return_value=mock_plugin_svc),
            patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
            patch("app.core_plugins.slack.routes.SlackClient", return_value=slack_client),
            patch("app.core_plugins.slack.routes.session_scope", mock_session_cls),
        ):
            await _dispatch_event(workspace_id=1, user_id=1, bot_token_encrypted="enc", bot_user_id="BOT", event=event)

        slack_client.post_message.assert_awaited_once()
        _, kwargs = slack_client.post_message.call_args
        assert "incomplete" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_greeting_posts_greeting_message(self) -> None:
        """is_greeting=True → posts greeting_message from config, rag_matched=False."""
        event = {"type": "app_mention", "text": "<@BOT> hello", "channel": "C1", "user": "U1", "ts": "1.0"}
        user_plugin = MagicMock()
        user_plugin.enabled = True
        user_plugin.config = {"greeting_message": "Hey there, student!"}
        slack_client = _make_slack_client_mock()
        mock_session_cls, mock_plugin_svc = self._base_patches(user_plugin, slack_client)

        with (
            patch("app.core_plugins.slack.routes.PluginService", return_value=mock_plugin_svc),
            patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
            patch("app.core_plugins.slack.routes.SlackClient", return_value=slack_client),
            patch("app.core_plugins.slack.routes.session_scope", mock_session_cls),
        ):
            await _dispatch_event(workspace_id=1, user_id=1, bot_token_encrypted="enc", bot_user_id="BOT", event=event)

        slack_client.post_message.assert_awaited_once()
        _, kwargs = slack_client.post_message.call_args
        assert kwargs["text"] == "Hey there, student!"

    @pytest.mark.asyncio
    async def test_question_posts_rag_answer(self) -> None:
        """Non-greeting question → calls answer_question, posts its result."""
        event = {
            "type": "app_mention",
            "text": "<@BOT> what is a loop?",
            "channel": "C1",
            "user": "U1",
            "ts": "1.0",
        }
        user_plugin = MagicMock()
        user_plugin.enabled = True
        user_plugin.config = {"fallback_message": "No answer found.", "llm_config_id": 1}
        slack_client = _make_slack_client_mock()
        mock_session_cls, _ = _make_session_mock()
        mock_plugin_svc = _make_plugin_svc(user_plugin)
        mock_llm_provider = MagicMock()
        mock_llm_provider.create_llm = MagicMock(return_value=MagicMock())

        with (
            patch("app.core_plugins.slack.routes.PluginService", return_value=mock_plugin_svc),
            patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
            patch("app.core_plugins.slack.routes.SlackClient", return_value=slack_client),
            patch("app.core_plugins.slack.routes.session_scope", mock_session_cls),
            patch(
                "app.core_plugins.slack.routes._build_llm_provider",
                new_callable=AsyncMock,
                return_value=mock_llm_provider,
            ),
            patch(
                "app.core_plugins.slack.routes.answer_question",
                new_callable=AsyncMock,
                return_value=("A loop repeats code.", ResponseType.rag_match),
            ),
        ):
            await _dispatch_event(workspace_id=1, user_id=1, bot_token_encrypted="enc", bot_user_id="BOT", event=event)

        slack_client.post_message.assert_awaited_once()
        _, kwargs = slack_client.post_message.call_args
        assert kwargs["text"] == "A loop repeats code."

    @pytest.mark.asyncio
    async def test_question_returns_no_ai_key_message_when_no_llm_config_id(self) -> None:
        """No llm_config_id configured → reply is NO_AI_KEY_MESSAGE, answer_question is NOT called."""
        event = {
            "type": "app_mention",
            "text": "<@BOT> what is recursion?",
            "channel": "C1",
            "user": "U1",
            "ts": "1.0",
        }
        user_plugin = MagicMock()
        user_plugin.enabled = True
        user_plugin.config = {"fallback_message": "Bot temporarily unavailable."}
        slack_client = _make_slack_client_mock()
        mock_session_cls, _ = _make_session_mock()
        mock_plugin_svc = _make_plugin_svc(user_plugin)

        with (
            patch("app.core_plugins.slack.routes.PluginService", return_value=mock_plugin_svc),
            patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
            patch("app.core_plugins.slack.routes.SlackClient", return_value=slack_client),
            patch("app.core_plugins.slack.routes.session_scope", mock_session_cls),
            patch(
                "app.core_plugins.slack.routes.answer_question",
                new_callable=AsyncMock,
            ) as mock_answer,
        ):
            await _dispatch_event(workspace_id=1, user_id=1, bot_token_encrypted="enc", bot_user_id="BOT", event=event)

        slack_client.post_message.assert_awaited_once()
        _, kwargs = slack_client.post_message.call_args
        assert kwargs["text"] == NO_AI_KEY_MESSAGE
        mock_answer.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_question_returns_ai_key_unavailable_when_build_llm_provider_fails(self) -> None:
        """_build_llm_provider returns None (key unresolvable) → reply is AI_KEY_UNAVAILABLE_MESSAGE."""
        event = {
            "type": "app_mention",
            "text": "<@BOT> what is recursion?",
            "channel": "C1",
            "user": "U1",
            "ts": "1.0",
        }
        user_plugin = MagicMock()
        user_plugin.enabled = True
        user_plugin.config = {"fallback_message": "Bot misconfigured.", "llm_config_id": 99}
        slack_client = _make_slack_client_mock()
        mock_session_cls, _ = _make_session_mock()
        mock_plugin_svc = _make_plugin_svc(user_plugin)

        with (
            patch("app.core_plugins.slack.routes.PluginService", return_value=mock_plugin_svc),
            patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
            patch("app.core_plugins.slack.routes.SlackClient", return_value=slack_client),
            patch("app.core_plugins.slack.routes.session_scope", mock_session_cls),
            patch("app.core_plugins.slack.routes._build_llm_provider", new_callable=AsyncMock, return_value=None),
            patch(
                "app.core_plugins.slack.routes.answer_question",
                new_callable=AsyncMock,
            ) as mock_answer,
        ):
            await _dispatch_event(workspace_id=1, user_id=1, bot_token_encrypted="enc", bot_user_id="BOT", event=event)

        slack_client.post_message.assert_awaited_once()
        _, kwargs = slack_client.post_message.call_args
        assert kwargs["text"] == AI_KEY_UNAVAILABLE_MESSAGE
        mock_answer.assert_not_awaited()


class TestRagSources:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_user_has_no_sources(
        self,
        slack_client: AsyncClient,
        test_user: User,
    ) -> None:
        with patch(
            "app.core_plugins.slack.routes.ChunkStoreService",
        ) as mock_store_cls:
            mock_store = AsyncMock()
            mock_store.get_sources = AsyncMock(return_value=[])
            mock_store_cls.return_value = mock_store

            response = await slack_client.get("/api/v1/slack/rag/sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data == {"sources": []}

    @pytest.mark.asyncio
    async def test_returns_distinct_sources_for_user(
        self,
        slack_client: AsyncClient,
        test_user: User,
    ) -> None:
        with patch(
            "app.core_plugins.slack.routes.ChunkStoreService",
        ) as mock_store_cls:
            mock_store = AsyncMock()
            mock_store.get_sources = AsyncMock(return_value=["doc_a", "doc_b"])
            mock_store_cls.return_value = mock_store

            response = await slack_client.get("/api/v1/slack/rag/sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert sorted(data["sources"]) == ["doc_a", "doc_b"]

    @pytest.mark.asyncio
    async def test_requires_authentication(self) -> None:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            response = await ac.get("/api/v1/slack/rag/sources")
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            )


@pytest.mark.asyncio
async def test_dispatch_event_passes_llm_provider_when_configured() -> None:
    """When llm_config_id is set and resolves successfully, llm_provider is passed."""
    config = SlackConfig(llm_config_id=7)
    event = {
        "type": "app_mention",
        "text": "<@BOT> what is recursion?",
        "channel": "C123",
        "user": "U456",
        "ts": "1234.5678",
    }

    mock_llm_config = MagicMock()
    mock_llm_config.provider = "anthropic"
    mock_llm_config.model = "claude-haiku-4-5"

    mock_slack_client = AsyncMock()
    mock_slack_client.__aenter__ = AsyncMock(return_value=mock_slack_client)
    mock_slack_client.__aexit__ = AsyncMock(return_value=False)
    mock_slack_client.post_message = AsyncMock(return_value={"ts": "9999.0000"})

    with (
        patch("app.core_plugins.slack.routes.PluginService") as mock_plugin_svc,
        patch("app.core_plugins.slack.routes.answer_question", new_callable=AsyncMock) as mock_aq,
        patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
        patch("app.core_plugins.slack.routes.SlackClient", return_value=mock_slack_client),
        patch("app.core_plugins.slack.routes.LLMConfigService") as mock_llm_svc_cls,
        patch("app.core_plugins.slack.routes.get_provider") as mock_get_provider,
        patch("app.core_plugins.slack.routes.get_encryption_service"),
        patch("app.core_plugins.slack.routes.get_cache_service"),
        patch("app.core_plugins.slack.routes.get_settings"),
        patch("app.core_plugins.slack.routes.session_scope") as mock_async_session_cls,
    ):
        mock_aq.return_value = ("Synthesized answer", ResponseType.rag_match)

        # Simulate plugin config returning LLM-enabled config
        mock_plugin_instance = AsyncMock()
        mock_user_plugin = MagicMock()
        mock_user_plugin.enabled = True
        mock_user_plugin.config = config.model_dump()
        mock_plugin_instance.get_user_plugin_map.return_value = {"slack": mock_user_plugin}
        mock_plugin_svc.return_value = mock_plugin_instance

        # Simulate LLMConfigService.resolve returning config + decrypted key
        mock_llm_svc = AsyncMock()
        mock_llm_svc.resolve.return_value = (mock_llm_config, "sk-decrypted-key")
        mock_llm_svc_cls.return_value = mock_llm_svc

        mock_provider_instance = MagicMock()
        mock_get_provider.return_value = mock_provider_instance

        # Wire up the async session context manager
        mock_session = AsyncMock()
        mock_async_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _dispatch_event(
            workspace_id=1,
            user_id=1,
            bot_token_encrypted="encrypted-token",
            bot_user_id="BOT",
            event=event,
        )

        # Verify answer_question received an llm_provider
        mock_aq.assert_awaited_once()
        call_kwargs = mock_aq.call_args.kwargs
        assert call_kwargs.get("llm_provider") is mock_provider_instance

        # Verify get_provider was called with the resolved config values
        mock_get_provider.assert_called_once()
        gp_kwargs = mock_get_provider.call_args.kwargs
        assert gp_kwargs["provider_name"] == "anthropic"
        assert gp_kwargs["api_key"] == "sk-decrypted-key"
        assert gp_kwargs["model"] == "claude-haiku-4-5"
        assert gp_kwargs["system_prompt"] == SYNTHESIS_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_dispatch_event_uses_model_override_when_configured() -> None:
    """When llm_model_override is set, get_provider is called with the override model."""
    config = SlackConfig(llm_config_id=7, llm_model_override="claude-haiku-4-5")
    event = {
        "type": "app_mention",
        "text": "<@BOT> what is recursion?",
        "channel": "C123",
        "user": "U456",
        "ts": "1234.5678",
    }

    mock_llm_config = MagicMock()
    mock_llm_config.provider = "anthropic"
    mock_llm_config.model = "claude-sonnet-4-6"  # the config's model — should be overridden

    mock_slack_client = AsyncMock()
    mock_slack_client.__aenter__ = AsyncMock(return_value=mock_slack_client)
    mock_slack_client.__aexit__ = AsyncMock(return_value=False)
    mock_slack_client.post_message = AsyncMock(return_value={"ts": "9999.0000"})

    with (
        patch("app.core_plugins.slack.routes.PluginService") as mock_plugin_svc,
        patch("app.core_plugins.slack.routes.answer_question", new_callable=AsyncMock) as mock_aq,
        patch("app.core_plugins.slack.routes.decrypt_token", return_value="xoxb-fake"),
        patch("app.core_plugins.slack.routes.SlackClient", return_value=mock_slack_client),
        patch("app.core_plugins.slack.routes.LLMConfigService") as mock_llm_svc_cls,
        patch("app.core_plugins.slack.routes.get_provider") as mock_get_provider,
        patch("app.core_plugins.slack.routes.get_encryption_service"),
        patch("app.core_plugins.slack.routes.get_cache_service"),
        patch("app.core_plugins.slack.routes.get_settings"),
        patch("app.core_plugins.slack.routes.session_scope") as mock_async_session_cls,
    ):
        mock_aq.return_value = ("Synthesized answer", ResponseType.rag_match)

        mock_plugin_instance = AsyncMock()
        mock_user_plugin = MagicMock()
        mock_user_plugin.enabled = True
        mock_user_plugin.config = config.model_dump()
        mock_plugin_instance.get_user_plugin_map.return_value = {"slack": mock_user_plugin}
        mock_plugin_svc.return_value = mock_plugin_instance

        mock_llm_svc = AsyncMock()
        mock_llm_svc.resolve.return_value = (mock_llm_config, "sk-decrypted-key")
        mock_llm_svc_cls.return_value = mock_llm_svc

        mock_get_provider.return_value = MagicMock()

        mock_session = AsyncMock()
        mock_async_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_async_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await _dispatch_event(
            workspace_id=1,
            user_id=1,
            bot_token_encrypted="encrypted-token",
            bot_user_id="BOT",
            event=event,
        )

        mock_get_provider.assert_called_once()
        gp_kwargs = mock_get_provider.call_args.kwargs
        assert gp_kwargs["model"] == "claude-haiku-4-5", "Expected llm_model_override to override the LLMConfig's model"


class TestDispatchEventLogging:
    """Test that _dispatch_event creates BotResponseLog for every bot reply path."""

    @staticmethod
    def _make_fake_session(added: list[Any]) -> Any:
        class _FakeSession:
            async def __aenter__(self) -> "_FakeSession":
                return self

            async def __aexit__(self, *a: Any) -> None:
                pass

            def add(self, obj: Any) -> None:
                added.append(obj)

            async def commit(self) -> None:
                pass

            async def rollback(self) -> None:
                pass

        return _FakeSession()

    @pytest.mark.asyncio
    async def test_plugin_not_configured_logs_plugin_disabled(self) -> None:
        added: list[Any] = []

        with (
            patch(
                "app.core_plugins.slack.routes.PluginService",
                return_value=MagicMock(get_user_plugin_map=AsyncMock(return_value={})),
            ),
            patch(
                "app.core_plugins.slack.routes._post_slack_message",
                new_callable=AsyncMock,
                return_value="111.0",
            ),
            patch(
                "app.core_plugins.slack.routes._resolve_names",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch("app.core_plugins.slack.routes.session_scope", return_value=self._make_fake_session(added)),
        ):
            await _dispatch_event(
                workspace_id=1,
                user_id=1,
                bot_token_encrypted="enc",
                bot_user_id="U_BOT",
                event={"text": "<@U_BOT> hi", "user": "U1", "channel": "C1", "ts": "1.0"},
            )

        assert len(added) == 1
        log = added[0]
        assert isinstance(log, BotResponseLog)
        assert log.response_type == ResponseType.plugin_disabled

    @pytest.mark.asyncio
    async def test_plugin_disabled_logs_plugin_disabled(self) -> None:
        added: list[Any] = []

        plugin = MagicMock()
        plugin.enabled = False
        plugin.config = {"fallback_message": "Bot is disabled"}

        with (
            patch(
                "app.core_plugins.slack.routes.PluginService",
                return_value=MagicMock(get_user_plugin_map=AsyncMock(return_value={"slack": plugin})),
            ),
            patch(
                "app.core_plugins.slack.routes._post_slack_message",
                new_callable=AsyncMock,
                return_value="111.0",
            ),
            patch(
                "app.core_plugins.slack.routes._resolve_names",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch("app.core_plugins.slack.routes.session_scope", return_value=self._make_fake_session(added)),
        ):
            await _dispatch_event(
                workspace_id=1,
                user_id=1,
                bot_token_encrypted="enc",
                bot_user_id="U_BOT",
                event={"text": "<@U_BOT> hello", "user": "U1", "channel": "C1", "ts": "1.0"},
            )

        assert len(added) == 1
        assert added[0].response_type == ResponseType.plugin_disabled

    @pytest.mark.asyncio
    async def test_config_incomplete_logs_config_incomplete(self) -> None:
        added: list[Any] = []

        plugin = MagicMock()
        plugin.enabled = True
        plugin.config = None

        with (
            patch(
                "app.core_plugins.slack.routes.PluginService",
                return_value=MagicMock(get_user_plugin_map=AsyncMock(return_value={"slack": plugin})),
            ),
            patch(
                "app.core_plugins.slack.routes._post_slack_message",
                new_callable=AsyncMock,
                return_value="111.0",
            ),
            patch(
                "app.core_plugins.slack.routes._resolve_names",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch("app.core_plugins.slack.routes.session_scope", return_value=self._make_fake_session(added)),
        ):
            await _dispatch_event(
                workspace_id=1,
                user_id=1,
                bot_token_encrypted="enc",
                bot_user_id="U_BOT",
                event={"text": "<@U_BOT> hello", "user": "U1", "channel": "C1", "ts": "1.0"},
            )

        assert len(added) == 1
        assert added[0].response_type == ResponseType.config_incomplete

    @pytest.mark.asyncio
    async def test_greeting_logs_with_resolved_names(self) -> None:
        added: list[Any] = []

        plugin = MagicMock()
        plugin.enabled = True
        plugin.config = {
            "fallback_message": "I don't know",
            "greeting_message": "Hello! I am the TA Bot.",
        }

        with (
            patch(
                "app.core_plugins.slack.routes.PluginService",
                return_value=MagicMock(get_user_plugin_map=AsyncMock(return_value={"slack": plugin})),
            ),
            patch(
                "app.core_plugins.slack.routes._post_slack_message",
                new_callable=AsyncMock,
                return_value="111.0",
            ),
            patch(
                "app.core_plugins.slack.routes._resolve_names",
                new_callable=AsyncMock,
                return_value=("alice", "general"),
            ),
            patch("app.core_plugins.slack.routes.is_greeting", return_value=True),
            patch("app.core_plugins.slack.routes.session_scope", return_value=self._make_fake_session(added)),
        ):
            await _dispatch_event(
                workspace_id=1,
                user_id=1,
                bot_token_encrypted="enc",
                bot_user_id="U_BOT",
                event={"text": "<@U_BOT> hi there", "user": "U1", "channel": "C1", "ts": "1.0"},
            )

        assert len(added) == 1
        log = added[0]
        assert log.response_type == ResponseType.greeting
        assert log.slack_user_name == "alice"
        assert log.slack_channel_name == "general"

    @pytest.mark.asyncio
    async def test_post_failure_means_no_log_created(self) -> None:
        added: list[Any] = []

        with (
            patch(
                "app.core_plugins.slack.routes.PluginService",
                return_value=MagicMock(get_user_plugin_map=AsyncMock(return_value={})),
            ),
            patch(
                "app.core_plugins.slack.routes._post_slack_message",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.core_plugins.slack.routes._resolve_names",
                new_callable=AsyncMock,
                return_value=(None, None),
            ),
            patch("app.core_plugins.slack.routes.session_scope", return_value=self._make_fake_session(added)),
        ):
            await _dispatch_event(
                workspace_id=1,
                user_id=1,
                bot_token_encrypted="enc",
                bot_user_id="U_BOT",
                event={"text": "<@U_BOT> hi", "user": "U1", "channel": "C1", "ts": "1.0"},
            )

        assert len(added) == 0


class TestConnectionEventLogging:
    @pytest.mark.asyncio
    async def test_oauth_callback_inserts_connected_log(
        self,
        slack_client: AsyncClient,
        test_user: object,
        sync_session: Any,
    ) -> None:
        from typing import cast as tcast

        from app.core_plugins.slack.oauth import generate_state

        fake_token_data = {
            "ok": True,
            "access_token": "xoxb-conn-token",
            "bot_user_id": "U_BOT_CONN",
            "team": {"id": "T_CONN", "name": "Conn Team"},
        }
        state = generate_state(user_id=tcast(int, getattr(test_user, "id")))

        with patch(
            "app.core_plugins.slack.routes.exchange_code_for_tokens",
            new_callable=AsyncMock,
            return_value=fake_token_data,
        ):
            await slack_client.get(
                "/api/v1/slack/oauth/callback",
                params={"code": "valid_code", "state": state},
                follow_redirects=False,
            )

        logs = sync_session.exec(select(SlackConnectionLog)).all()
        assert len(logs) == 1
        assert logs[0].event_type == ConnectionEventType.connected
        assert logs[0].team_name == "Conn Team"
        assert logs[0].workspace_id is not None

    @pytest.mark.asyncio
    async def test_disconnect_inserts_disconnected_log(
        self,
        slack_client: AsyncClient,
        test_workspace: SlackWorkspace,
        sync_session: Any,
    ) -> None:
        response = await slack_client.delete("/api/v1/slack/oauth/disconnect")
        assert response.status_code == status.HTTP_200_OK

        logs = sync_session.exec(select(SlackConnectionLog)).all()
        assert len(logs) == 1
        assert logs[0].event_type == ConnectionEventType.disconnected
        assert logs[0].workspace_id == test_workspace.id
