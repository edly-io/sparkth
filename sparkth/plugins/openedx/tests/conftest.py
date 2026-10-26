from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkth.plugins.openedx.config import OpenEdxConfig

OPENEDX_CONFIG = OpenEdxConfig.model_validate(
    {
        "lms_url": "https://lms.example.com",
        "studio_url": "https://studio.example.com",
        "lms_username": "testuser",
        "lms_password": "testpass",
    }
)


def http_response(status: int, body: str) -> AsyncMock:
    """An aiohttp response answering ``status`` with ``body`` as its text."""
    response = AsyncMock()
    response.status = status
    response.text = AsyncMock(return_value=body)
    response.__aenter__.return_value = response
    response.__aexit__.return_value = None
    return response


def http_session(token_body: str, *api_responses: AsyncMock) -> MagicMock:
    """A session whose token endpoint answers ``token_body`` and whose API calls answer in order."""
    session = MagicMock()
    session.post.return_value = http_response(200, token_body)
    session.request.side_effect = list(api_responses)
    session.closed = False
    session.close = AsyncMock()
    return session


@pytest.fixture
def stored_config() -> Generator[None, None, None]:
    """Make the Open edX tools act for user 1, with ``OPENEDX_CONFIG`` as that user's stored settings."""
    with (
        patch("sparkth.plugins.openedx.tools.current_user_id", return_value=1),
        patch("sparkth.plugins.openedx.tools.load_user_plugin_config", AsyncMock(return_value=OPENEDX_CONFIG)),
    ):
        yield
