"""Unit tests for SlackClient."""

import hashlib
import hmac
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sparkth.plugins.slack.client import SlackClient
from sparkth.plugins.slack.exceptions import SlackSignatureError


def _make_signature(secret: str, timestamp: str, body: bytes) -> str:
    base = f"v0:{timestamp}:{body.decode()}"
    return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


class TestVerifySignature:
    def test_valid_signature_passes(self) -> None:
        secret = "test_signing_secret"
        body = b'{"type":"event_callback"}'
        ts = str(int(time.time()))
        sig = _make_signature(secret, ts, body)
        SlackClient.verify_signature(secret, ts, body, sig)  # should not raise

    def test_wrong_signature_raises(self) -> None:
        secret = "test_signing_secret"
        ts = str(int(time.time()))
        body = b'{"type":"event_callback"}'
        with pytest.raises(SlackSignatureError, match="mismatch"):
            SlackClient.verify_signature(secret, ts, body, "v0=badhash")

    def test_stale_timestamp_raises(self) -> None:
        secret = "signing_secret"
        stale_ts = str(int(time.time()) - 400)
        body = b"{}"
        sig = _make_signature(secret, stale_ts, body)
        with pytest.raises(SlackSignatureError, match="old"):
            SlackClient.verify_signature(secret, stale_ts, body, sig)

    def test_non_numeric_timestamp_raises(self) -> None:
        with pytest.raises(SlackSignatureError, match="timestamp"):
            SlackClient.verify_signature("secret", "not_a_number", b"{}", "v0=hash")


class TestSlackClientWithoutContextManager:
    @pytest.mark.asyncio
    async def test_post_message_without_context_manager_raises(self) -> None:
        client = SlackClient("xoxb-token")
        with pytest.raises(RuntimeError, match="context manager"):
            await client.post_message("C123", "hello")

    @pytest.mark.asyncio
    async def test_auth_test_without_context_manager_raises(self) -> None:
        client = SlackClient("xoxb-token")
        with pytest.raises(RuntimeError, match="context manager"):
            await client.auth_test()


class TestPostMessage:
    @pytest.mark.asyncio
    async def test_sends_correct_payload(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"ok": True, "ts": "123.456"})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                result = await client.post_message("C_CHAN", "Hello learner!")

        assert result["ok"] is True
        payload = mock_http.post.call_args[1]["json"]
        assert payload["channel"] == "C_CHAN"
        assert payload["text"] == "Hello learner!"
        assert "thread_ts" not in payload

    @pytest.mark.asyncio
    async def test_includes_thread_ts_when_provided(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"ok": True})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                await client.post_message("C_CHAN", "reply", thread_ts="111.222")

        payload = mock_http.post.call_args[1]["json"]
        assert payload["thread_ts"] == "111.222"


class TestAuthTest:
    @pytest.mark.asyncio
    async def test_returns_parsed_response(self) -> None:
        fake_data = {"ok": True, "team_id": "T123", "user_id": "U_BOT"}

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=fake_data)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                result = await client.auth_test()

        assert result["team_id"] == "T123"


class TestGetUserDisplayName:
    def _make_client_mock(self, response_json: dict[str, Any]) -> tuple[AsyncMock, MagicMock]:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response_json)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_response)
        return mock_http, mock_response

    @pytest.mark.asyncio
    async def test_returns_display_name_when_set(self) -> None:
        mock_http, _ = self._make_client_mock(
            {"ok": True, "user": {"profile": {"display_name": "alice", "real_name": "Alice Smith"}}}
        )
        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_user_display_name("U123")
        assert name == "alice"

    @pytest.mark.asyncio
    async def test_falls_back_to_real_name_when_display_name_empty(self) -> None:
        mock_http, _ = self._make_client_mock(
            {"ok": True, "user": {"profile": {"display_name": "", "real_name": "Alice Smith"}}}
        )
        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_user_display_name("U123")
        assert name == "Alice Smith"

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self) -> None:
        mock_http, _ = self._make_client_mock({"ok": False, "error": "user_not_found"})
        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_user_display_name("U_BAD")
        assert name is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self) -> None:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_user_display_name("U123")
        assert name is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_status_error(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=MagicMock())
        )
        mock_response.json = MagicMock(return_value={})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_user_display_name("U123")
        assert name is None


class TestGetChannelName:
    def _make_client_mock(self, response_json: dict[str, Any]) -> tuple[AsyncMock, MagicMock]:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response_json)

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_response)
        return mock_http, mock_response

    @pytest.mark.asyncio
    async def test_returns_channel_name(self) -> None:
        mock_http, _ = self._make_client_mock({"ok": True, "channel": {"name": "general"}})
        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_channel_name("C123")
        assert name == "general"

    @pytest.mark.asyncio
    async def test_returns_dm_for_direct_message_channel(self) -> None:
        mock_http, _ = self._make_client_mock({"ok": True, "channel": {"user": "U999"}})
        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_channel_name("D123")
        assert name == "DM"

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self) -> None:
        mock_http, _ = self._make_client_mock({"ok": False, "error": "channel_not_found"})
        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_channel_name("C_BAD")
        assert name is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self) -> None:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_channel_name("C123")
        assert name is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_status_error(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=MagicMock())
        )
        mock_response.json = MagicMock(return_value={})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_http):
            async with SlackClient("xoxb-token") as client:
                name = await client.get_channel_name("C123")
        assert name is None
