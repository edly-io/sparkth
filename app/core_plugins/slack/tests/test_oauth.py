"""Unit tests for Slack OAuth helper functions."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session

from app.core_plugins.slack.models import SlackWorkspace
from app.models.user import User


class TestTokenEncryption:
    def test_roundtrip(self) -> None:
        from app.core_plugins.slack.oauth import decrypt_token, encrypt_token

        original = "xoxb-real-bot-token-value"
        assert decrypt_token(encrypt_token(original)) == original

    def test_ciphertext_differs_from_plaintext(self) -> None:
        from app.core_plugins.slack.oauth import encrypt_token

        token = "xoxb-some-token"
        assert encrypt_token(token) != token

    def test_different_tokens_produce_different_ciphertext(self) -> None:
        from app.core_plugins.slack.oauth import encrypt_token

        assert encrypt_token("token_a") != encrypt_token("token_b")

    def test_decrypt_invalid_raises(self) -> None:
        from app.core_plugins.slack.oauth import decrypt_token

        with pytest.raises(ValueError, match="decrypt"):
            decrypt_token("this-is-not-valid-fernet-data")


class TestStateToken:
    def test_roundtrip_preserves_user_id(self) -> None:
        from app.core_plugins.slack.oauth import decode_state, generate_state

        state = generate_state(user_id=42)
        assert decode_state(state)["user_id"] == 42

    def test_tampered_state_raises(self) -> None:
        from itsdangerous import BadSignature

        from app.core_plugins.slack.oauth import decode_state

        with pytest.raises(BadSignature):
            decode_state("tampered.state.value")

    def test_expired_state_raises(self) -> None:
        import time

        from itsdangerous import SignatureExpired

        from app.core_plugins.slack.oauth import _get_signer, decode_state

        # Sign with a timestamp 700 seconds in the past (> 600s max_age)
        signer = _get_signer()
        with patch("itsdangerous.timed.time", return_value=time.time() - 700):
            state = signer.dumps({"user_id": 1})

        with pytest.raises(SignatureExpired):
            decode_state(state)


class TestGenerateAuthorizationUrl:
    def test_contains_required_params(self) -> None:
        from app.core_plugins.slack.oauth import generate_authorization_url

        url = generate_authorization_url(user_id=1, client_id="my_client_id", redirect_uri="http://localhost/callback")
        assert "client_id=my_client_id" in url
        assert "redirect_uri=" in url
        assert "scope=" in url
        assert "state=" in url
        assert "slack.com" in url

    def test_state_embeds_user_id(self) -> None:
        from urllib.parse import parse_qs, urlparse

        from app.core_plugins.slack.oauth import decode_state, generate_authorization_url

        url = generate_authorization_url(user_id=99, client_id="cid", redirect_uri="http://cb")
        state = parse_qs(urlparse(url).query)["state"][0]
        assert decode_state(state)["user_id"] == 99


class TestExchangeCodeForTokens:
    @pytest.mark.asyncio
    async def test_success_returns_token_data(self) -> None:
        from app.core_plugins.slack.oauth import exchange_code_for_tokens

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
        from app.core_plugins.slack.oauth import exchange_code_for_tokens

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
        from app.core_plugins.slack.oauth import decrypt_token, get_workspace, save_workspace

        ws = save_workspace(
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
        assert get_workspace(sync_session, cast(int, test_user.id)) is not None

    def test_save_overwrites_existing(self, sync_session: Session, test_user: User) -> None:
        from sqlmodel import select

        from app.core_plugins.slack.oauth import save_workspace

        save_workspace(sync_session, cast(int, test_user.id), "T_OLD", "Old", "tok1", "U1")
        save_workspace(sync_session, cast(int, test_user.id), "T_NEW", "New", "tok2", "U2")
        all_ws = sync_session.exec(select(SlackWorkspace).where(SlackWorkspace.user_id == test_user.id)).all()
        active = [w for w in all_ws if w.is_active and not w.is_deleted]
        assert len(active) == 1
        assert active[0].team_id == "T_NEW"

    def test_get_workspace_returns_none_when_absent(self, sync_session: Session, test_user: User) -> None:
        from app.core_plugins.slack.oauth import get_workspace

        assert get_workspace(sync_session, cast(int, test_user.id)) is None

    def test_get_workspace_returns_none_after_soft_delete(
        self, sync_session: Session, test_workspace: SlackWorkspace, test_user: User
    ) -> None:
        from app.core_plugins.slack.oauth import delete_workspace, get_workspace

        delete_workspace(sync_session, cast(int, test_user.id))
        assert get_workspace(sync_session, cast(int, test_user.id)) is None

    def test_delete_workspace_when_none_is_noop(self, sync_session: Session, test_user: User) -> None:
        from app.core_plugins.slack.oauth import delete_workspace

        delete_workspace(sync_session, cast(int, test_user.id))
