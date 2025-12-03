import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from sparkth_mcp.openedx.client import OpenEdxClient
from sparkth_mcp.types import AuthenticationError


@pytest.mark.asyncio
class TestOpenEdxClient:
    async def test_authenticate_success(self):
        lms_url = "https://openedx.example.com"
        access_token = "valid_token"

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"user": "test_user"})
        mock_response.text = AsyncMock(return_value='{"user": "test_user"}')

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.request.return_value = mock_cm

        with patch("aiohttp.ClientSession", return_value=mock_session):
            client = OpenEdxClient(lms_url, access_token)
            result = await client.authenticate()

        assert result == {"user": "test_user"}

    async def test_request_jwt_no_token(self):
        lms_url = "https://openedx.example.com"
        client = OpenEdxClient(lms_url)

        with pytest.raises(AuthenticationError) as exc_info:
            await client.request_jwt("GET", "api/user/v1/me", base_url=lms_url)

        assert exc_info.value.args[0] == "Access token not set (status_code=401)"

    async def test_get_token_success(self):
        lms_url = "https://openedx.example.com"
        username = "user1"
        password = "pass1"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "access_token": "new_token",
                "refresh_token": "refresh_token",
            }
        )
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            client = OpenEdxClient(lms_url)
            token_data = await client.get_token(username, password)

        assert token_data["access_token"] == "new_token"
        assert client.access_token == "new_token"
        assert client.refresh_token == "refresh_token"

    async def test_refresh_access_token_success(self):
        lms_url = "https://openedx.example.com"
        old_refresh_token = "old_refresh"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"access_token": "refreshed_token", "refresh_token": "new_refresh"})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            client = OpenEdxClient(lms_url)
            token_data = await client.refresh_access_token(old_refresh_token)

        assert token_data["access_token"] == "refreshed_token"
        assert client.access_token == "refreshed_token"
        assert client.refresh_token == "new_refresh"
