"""Unit tests for Slack OAuth helper functions."""

import time
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from itsdangerous import BadSignature, SignatureExpired
from sqlmodel import Session

from app.core_plugins.slack.exceptions import UserAlreadyConnectedError, WorkspaceAlreadyConnectedError
from app.core_plugins.slack.models import SlackWorkspace
from app.core_plugins.slack.oauth import (
    decode_state,
    exchange_code_for_tokens,
    generate_authorization_url,
    generate_state,
)
from app.core_plugins.slack.service import WorkspaceService, decrypt_token, encrypt_token
from app.models.user import User


class TestTokenEncryption:
    def test_roundtrip(self) -> None:
        original = "xoxb-real-bot-token-value"
        assert decrypt_token(encrypt_token(original)) == original

    def test_ciphertext_differs_from_plaintext(self) -> None:
        token = "xoxb-some-token"
        assert encrypt_token(token) != token

    def test_different_tokens_produce_different_ciphertext(self) -> None:
        assert encrypt_token("token_a") != encrypt_token("token_b")

    def test_decrypt_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="decrypt"):
            decrypt_token("this-is-not-valid-fernet-data")


class TestStateToken:
    def test_roundtrip_preserves_user_id(self) -> None:
        state = generate_state(user_id=42)
        assert decode_state(state)["user_id"] == 42

    def test_tampered_state_raises(self) -> None:
        with pytest.raises(BadSignature):
            decode_state("tampered.state.value")

    def test_expired_state_raises(self) -> None:
        # Sign with a timestamp 700 seconds in the past (> 600s max_age)
        with patch("itsdangerous.timed.time", return_value=time.time() - 700):
            state = generate_state(user_id=1)

        with pytest.raises(SignatureExpired):
            decode_state(state)


class TestGenerateAuthorizationUrl:
    def test_contains_required_params(self) -> None:
        url = generate_authorization_url(user_id=1, client_id="my_client_id", redirect_uri="http://localhost/callback")
        assert "client_id=my_client_id" in url
        assert "redirect_uri=" in url
        assert "scope=" in url
        assert "state=" in url
        assert "slack.com" in url

    def test_state_embeds_user_id(self) -> None:
        url = generate_authorization_url(user_id=99, client_id="cid", redirect_uri="http://cb")
        state = parse_qs(urlparse(url).query)["state"][0]
        assert decode_state(state)["user_id"] == 99


class TestExchangeCodeForTokens:
    @pytest.mark.asyncio
    async def test_success_returns_token_data(self) -> None:
        fake_response = {
            "ok": True,
            "access_token": "xoxb-bot-token",
            "bot_user_id": "U_BOT",
            "team": {"id": "T123", "name": "My Team"},
        }
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=fake_response)
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_resp)
        with patch("app.core_plugins.slack.oauth.httpx.AsyncClient", return_value=mock_http):
            result = await exchange_code_for_tokens("code", "cid", "secret", "http://cb")
        assert result["access_token"] == "xoxb-bot-token"
        assert result["team"]["id"] == "T123"

    @pytest.mark.asyncio
    async def test_slack_error_raises_value_error(self) -> None:
        fake_response = {"ok": False, "error": "invalid_code"}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=fake_response)
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_resp)
        with patch("app.core_plugins.slack.oauth.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(ValueError, match="invalid_code"):
                await exchange_code_for_tokens("bad", "cid", "secret", "http://cb")


class TestWorkspaceCRUD:
    def test_save_new_workspace(self, sync_session: Session, test_user: User) -> None:
        service = WorkspaceService()
        ws = service.save(
            sync_session,
            user_id=cast(int, test_user.id),
            team_id="T_NEW",
            team_name="New Team",
            bot_token="xoxb-real",
            bot_user_id="U_BOT",
        )
        assert ws.id is not None
        assert ws.team_id == "T_NEW"
        assert decrypt_token(ws.bot_token_encrypted) == "xoxb-real"
        assert service.get(sync_session, cast(int, test_user.id)) is not None

    def test_save_raises_when_user_already_connected(self, sync_session: Session, test_user: User) -> None:
        service = WorkspaceService()
        service.save(sync_session, cast(int, test_user.id), "T_FIRST", "First", "tok1", "U1")
        with pytest.raises(UserAlreadyConnectedError):
            service.save(sync_session, cast(int, test_user.id), "T_SECOND", "Second", "tok2", "U2")

    def test_get_workspace_returns_none_when_absent(self, sync_session: Session, test_user: User) -> None:
        assert WorkspaceService().get(sync_session, cast(int, test_user.id)) is None

    def test_get_workspace_returns_none_after_soft_delete(
        self, sync_session: Session, test_workspace: SlackWorkspace, test_user: User
    ) -> None:
        service = WorkspaceService()
        service.delete(sync_session, cast(int, test_user.id))
        assert service.get(sync_session, cast(int, test_user.id)) is None

    def test_delete_workspace_when_none_is_noop(self, sync_session: Session, test_user: User) -> None:
        WorkspaceService().delete(sync_session, cast(int, test_user.id))

    def test_save_raises_when_team_id_already_active(self, sync_session: Session, test_user: User) -> None:
        """Raises WorkspaceAlreadyConnectedError when team_id is already taken."""
        other_user = User(
            name="Other User",
            username="otheruser",
            email="other@example.com",
            hashed_password="fakehashedpassword",
        )
        sync_session.add(other_user)
        sync_session.commit()
        sync_session.refresh(other_user)

        WorkspaceService().save(sync_session, cast(int, other_user.id), "T_DUP", "Dup Team", "xoxb-tok", "U_BOT")

        with pytest.raises(WorkspaceAlreadyConnectedError):
            WorkspaceService().save(sync_session, cast(int, test_user.id), "T_DUP", "Dup Team", "xoxb-tok2", "U_BOT2")

    def test_save_raises_when_team_id_taken_by_another_user(
        self, sync_session: Session, test_user: User, test_workspace: SlackWorkspace
    ) -> None:
        """Second user cannot connect a team_id already active under another user."""
        other_user = User(
            name="Other User",
            username="otheruser",
            email="other@example.com",
            hashed_password="fakehashedpassword",
        )
        sync_session.add(other_user)
        sync_session.commit()
        sync_session.refresh(other_user)

        with pytest.raises(WorkspaceAlreadyConnectedError):
            WorkspaceService().save(
                sync_session,
                cast(int, other_user.id),
                test_workspace.team_id,
                test_workspace.team_name,
                "xoxb-other",
                "U_OTHER",
            )
