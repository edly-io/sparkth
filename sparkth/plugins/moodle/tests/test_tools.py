from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from sparkth.lib.exceptions import AuthenticationError
from sparkth.plugins.moodle.schemas import Auth
from sparkth.plugins.moodle.tools import moodle_authenticate

AUTH = Auth(api_url="https://moodle.example.com", api_token="tok")


def _client_returning(value: Any) -> AsyncMock:
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.call_dict = AsyncMock(return_value=value)
    client.call_list = AsyncMock(return_value=value)
    return client


class TestMoodleAuthenticate:
    @pytest.mark.asyncio
    async def test_returns_the_site_and_user(self) -> None:
        client = _client_returning({"sitename": "Sparkth Moodle Dev", "username": "author"})
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_authenticate(AUTH)

        assert result == {"sitename": "Sparkth Moodle Dev", "username": "author"}
        assert client.call_dict.call_args.args[0] == "core_webservice_get_site_info"

    @pytest.mark.asyncio
    async def test_a_rejected_token_becomes_an_error_dict(self) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(side_effect=AuthenticationError(401, "Invalid token"))
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_authenticate(AUTH)

        assert result["error"]["status_code"] == 401
        assert result["error"]["message"] == "Invalid token"

    @pytest.mark.asyncio
    async def test_a_malformed_response_becomes_an_error_dict_with_a_status_code(self) -> None:
        client = _client_returning(None)
        client.call_dict = AsyncMock(
            side_effect=ValueError("Expected JSON object from core_webservice_get_site_info, got list")
        )
        with patch("sparkth.plugins.moodle.tools.MoodleClient", return_value=client):
            result = await moodle_authenticate(AUTH)

        assert result["error"]["status_code"] == 502
        assert "core_webservice_get_site_info" in result["error"]["message"]
