import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sparkth_mcp.canvas.client import CanvasClient
from sparkth_mcp.types import AuthenticationError


class TestCanvasClientAuthenticate:
    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        api_url = "https://canvas.example.com"
        api_token = "test_token_123"

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            status = await CanvasClient.authenticate(api_url, api_token)

        assert status == 200
        mock_session.get.assert_called_once_with(
            "https://canvas.example.com/users/self",
            headers={"Authorization": "Bearer test_token_123"},
        )

    @pytest.mark.asyncio
    async def test_authenticate_failure_401_invalid_token(self):
        """Test authentication failure with 401 status"""
        api_url = "https://canvas.example.com"
        api_token = "invalid_token"

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.json = AsyncMock(return_value={"errors": [{"message": "Invalid access token"}]})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(AuthenticationError) as exc_info:
                await CanvasClient.authenticate(api_url, api_token)

        assert exc_info.value.args[0] == "Invalid access token (status_code=401)"
