"""Unit tests for Google Drive OAuth functions."""

from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session

from app.core_plugins.googledrive.oauth import (
    decode_state,
    decrypt_token,
    delete_token,
    encrypt_token,
    generate_authorization_url,
    get_token_record,
    get_valid_access_token,
    save_tokens,
)
from app.models.drive import DriveOAuthToken
from app.models.user import User


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Encrypting then decrypting returns the original token."""
        original = "ya29.a0AfH6SMB_test_token_value"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_different_tokens_produce_different_ciphertext(self) -> None:
        """Different tokens should not produce the same encrypted value."""
        enc1 = encrypt_token("token_one")
        enc2 = encrypt_token("token_two")

        assert enc1 != enc2


class TestGenerateAuthorizationUrl:
    def test_url_contains_required_params(self) -> None:
        """Authorization URL should include client_id, redirect_uri, scope, state."""
        url = generate_authorization_url(
            user_id=42,
            client_id="test_client_id",
            redirect_uri="http://localhost/callback",
        )

        assert "client_id=test_client_id" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url
        assert "access_type=offline" in url
        assert "state=" in url
        assert "accounts.google.com" in url

    def test_url_includes_login_hint(self) -> None:
        """Login hint should be included when provided."""
        url = generate_authorization_url(
            user_id=1,
            client_id="cid",
            redirect_uri="http://localhost/callback",
            login_hint="user@gmail.com",
        )

        assert "login_hint=user%40gmail.com" in url

    def test_url_omits_login_hint_when_none(self) -> None:
        """Login hint should not appear when not provided."""
        url = generate_authorization_url(
            user_id=1,
            client_id="cid",
            redirect_uri="http://localhost/callback",
        )

        assert "login_hint" not in url


class TestDecodeState:
    def test_decode_state_roundtrip(self) -> None:
        """State parameter should roundtrip through encode/decode."""
        url = generate_authorization_url(
            user_id=99,
            client_id="cid",
            redirect_uri="http://localhost/callback",
        )

        # Extract state from URL
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        state = parse_qs(parsed.query)["state"][0]
        decoded = decode_state(state)

        assert decoded["user_id"] == 99


class TestSaveTokens:
    def test_save_new_token(self, sync_session: Session, test_user: User) -> None:
        """Saving tokens for a new user creates a record."""
        user_id = cast(int, test_user.id)

        record = save_tokens(
            sync_session,
            user_id,
            access_token="access_123",
            refresh_token="refresh_456",
            expires_in=3600,
            scopes="drive.file",
        )

        assert record.user_id == user_id
        assert decrypt_token(record.access_token_encrypted) == "access_123"
        assert decrypt_token(record.refresh_token_encrypted) == "refresh_456"
        assert record.scopes == "drive.file"

    def test_save_updates_existing_token(self, sync_session: Session, test_user: User) -> None:
        """Saving tokens when a record exists should update it."""
        user_id = cast(int, test_user.id)

        save_tokens(sync_session, user_id, "old_access", "old_refresh", 3600, "scope1")
        record = save_tokens(sync_session, user_id, "new_access", "new_refresh", 7200, "scope2")

        assert decrypt_token(record.access_token_encrypted) == "new_access"
        assert record.scopes == "scope2"


class TestGetTokenRecord:
    def test_returns_token_when_exists(
        self, sync_session: Session, test_user: User, test_oauth_token: DriveOAuthToken
    ) -> None:
        """Should return the token record for a connected user."""
        record = get_token_record(sync_session, cast(int, test_user.id))

        assert record is not None
        assert record.user_id == test_user.id

    def test_returns_none_when_no_token(self, sync_session: Session, test_user: User) -> None:
        """Should return None when user has no token."""
        record = get_token_record(sync_session, cast(int, test_user.id))

        assert record is None

    def test_returns_none_for_soft_deleted_token(
        self, sync_session: Session, test_user: User, test_oauth_token: DriveOAuthToken
    ) -> None:
        """Should not return soft-deleted tokens."""
        test_oauth_token.soft_delete()
        sync_session.add(test_oauth_token)
        sync_session.commit()

        record = get_token_record(sync_session, cast(int, test_user.id))

        assert record is None


class TestDeleteToken:
    def test_soft_deletes_token(
        self, sync_session: Session, test_user: User, test_oauth_token: DriveOAuthToken
    ) -> None:
        """Delete should soft-delete the token record."""
        result = delete_token(sync_session, cast(int, test_user.id))

        assert result is True
        record = get_token_record(sync_session, cast(int, test_user.id))
        assert record is None

    def test_returns_false_when_no_token(self, sync_session: Session, test_user: User) -> None:
        """Delete should return False when no token exists."""
        result = delete_token(sync_session, cast(int, test_user.id))

        assert result is False


class TestGetValidAccessToken:
    @pytest.mark.asyncio
    async def test_returns_existing_token_if_not_expired(
        self, sync_session: Session, test_user: User, test_oauth_token: DriveOAuthToken
    ) -> None:
        """Should return existing access token if not expired."""
        token = await get_valid_access_token(sync_session, cast(int, test_user.id), "client_id", "client_secret")

        assert token == "fake_access_token"

    @pytest.mark.asyncio
    async def test_refreshes_expired_token(
        self, sync_session: Session, test_user: User, test_oauth_token: DriveOAuthToken
    ) -> None:
        """Should refresh and return new token if expired."""
        # Make token expired
        test_oauth_token.token_expiry = datetime.now(timezone.utc) - timedelta(minutes=10)
        sync_session.add(test_oauth_token)
        sync_session.commit()

        with patch(
            "app.core_plugins.googledrive.oauth.refresh_access_token",
            new_callable=AsyncMock,
            return_value={"access_token": "refreshed_token", "expires_in": 3600},
        ):
            token = await get_valid_access_token(sync_session, cast(int, test_user.id), "client_id", "client_secret")

        assert token == "refreshed_token"

    @pytest.mark.asyncio
    async def test_raises_when_not_connected(self, sync_session: Session, test_user: User) -> None:
        """Should raise ValueError when user has no token."""
        with pytest.raises(ValueError, match="not connected"):
            await get_valid_access_token(sync_session, cast(int, test_user.id), "client_id", "client_secret")


class TestExchangeCodeForTokens:
    @pytest.mark.asyncio
    async def test_exchange_success(self) -> None:
        """Successful token exchange returns token data."""
        from app.core_plugins.googledrive.oauth import exchange_code_for_tokens

        token_data = {
            "access_token": "ya29.access",
            "refresh_token": "1//refresh",
            "expires_in": 3600,
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=token_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await exchange_code_for_tokens("auth_code", "cid", "secret", "http://cb")

        assert result["access_token"] == "ya29.access"

    @pytest.mark.asyncio
    async def test_exchange_failure_raises(self) -> None:
        """Failed token exchange should raise ValueError."""
        from app.core_plugins.googledrive.oauth import exchange_code_for_tokens

        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(return_value={"error": "invalid_grant"})
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ValueError, match="Token exchange failed"):
                await exchange_code_for_tokens("bad_code", "cid", "secret", "http://cb")
