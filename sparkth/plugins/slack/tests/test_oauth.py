"""Unit tests for Slack OAuth helper functions."""

import time
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from itsdangerous import BadSignature, SignatureExpired
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.models.user import User
from sparkth.plugins.slack.exceptions import UserAlreadyConnectedError, WorkspaceAlreadyConnectedError
from sparkth.plugins.slack.models import SlackWorkspace
from sparkth.plugins.slack.oauth import (
    decode_state,
    exchange_code_for_tokens,
    generate_authorization_url,
    generate_state,
)
from sparkth.plugins.slack.service import WorkspaceService, decrypt_token, encrypt_token


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
        with patch("sparkth.plugins.slack.oauth.httpx.AsyncClient", return_value=mock_http):
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
        with patch("sparkth.plugins.slack.oauth.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(ValueError, match="invalid_code"):
                await exchange_code_for_tokens("bad", "cid", "secret", "http://cb")


class TestWorkspaceCRUD:
    @pytest.mark.asyncio
    async def test_save_new_workspace(self, session: AsyncSession, test_user: User) -> None:
        user_id = cast(int, test_user.id)
        service = WorkspaceService()
        ws = await service.save(
            session,
            user_id=user_id,
            team_id="T_NEW",
            team_name="New Team",
            bot_token="xoxb-real",
            bot_user_id="U_BOT",
        )
        assert ws.id is not None
        assert ws.team_id == "T_NEW"
        assert decrypt_token(ws.bot_token_encrypted) == "xoxb-real"
        assert await service.get(session, user_id) is not None

    @pytest.mark.asyncio
    async def test_save_raises_when_user_already_connected(self, session: AsyncSession, test_user: User) -> None:
        user_id = cast(int, test_user.id)
        service = WorkspaceService()
        await service.save(session, user_id, "T_FIRST", "First", "tok1", "U1")
        with pytest.raises(UserAlreadyConnectedError):
            await service.save(session, user_id, "T_SECOND", "Second", "tok2", "U2")

    @pytest.mark.asyncio
    async def test_get_workspace_returns_none_when_absent(self, session: AsyncSession, test_user: User) -> None:
        assert await WorkspaceService().get(session, cast(int, test_user.id)) is None

    @pytest.mark.asyncio
    async def test_get_workspace_returns_none_after_soft_delete(
        self, session: AsyncSession, test_workspace: SlackWorkspace, test_user: User
    ) -> None:
        user_id = cast(int, test_user.id)
        service = WorkspaceService()
        await service.delete(session, user_id)
        assert await service.get(session, user_id) is None

    @pytest.mark.asyncio
    async def test_delete_workspace_when_none_is_noop(self, session: AsyncSession, test_user: User) -> None:
        await WorkspaceService().delete(session, cast(int, test_user.id))

    @pytest.mark.asyncio
    async def test_save_raises_when_team_id_already_active(self, session: AsyncSession, test_user: User) -> None:
        """Raises WorkspaceAlreadyConnectedError when team_id is already taken."""
        user_id = cast(int, test_user.id)
        other_user = User(
            name="Other User",
            username="otheruser",
            email="other@example.com",
            hashed_password="fakehashedpassword",
        )
        session.add(other_user)
        await session.flush()
        await session.refresh(other_user)
        other_user_id = cast(int, other_user.id)

        await WorkspaceService().save(session, other_user_id, "T_DUP", "Dup Team", "xoxb-tok", "U_BOT")

        with pytest.raises(WorkspaceAlreadyConnectedError):
            await WorkspaceService().save(session, user_id, "T_DUP", "Dup Team", "xoxb-tok2", "U_BOT2")

    @pytest.mark.asyncio
    async def test_save_raises_when_team_id_taken_by_another_user(
        self, session: AsyncSession, test_user: User, test_workspace: SlackWorkspace
    ) -> None:
        """Second user cannot connect a team_id already active under another user."""
        team_id = test_workspace.team_id
        team_name = test_workspace.team_name
        other_user = User(
            name="Other User",
            username="otheruser",
            email="other@example.com",
            hashed_password="fakehashedpassword",
        )
        session.add(other_user)
        await session.flush()
        await session.refresh(other_user)
        other_user_id = cast(int, other_user.id)

        with pytest.raises(WorkspaceAlreadyConnectedError):
            await WorkspaceService().save(
                session,
                other_user_id,
                team_id,
                team_name,
                "xoxb-other",
                "U_OTHER",
            )
