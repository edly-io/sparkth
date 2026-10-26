from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sparkth.lib.cache import get_cache_service
from sparkth.lib.settings import get_settings
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


class FakeRedis:
    """In-memory stand-in for the Redis client, recording values and the TTLs they were set with."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        self.ttls[key] = ex
        return True

    async def delete(self, key: str) -> int:
        self.ttls.pop(key, None)
        return 1 if self.store.pop(key, None) is not None else 0


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> Generator[FakeRedis, None, None]:
    """Route the shared cache to an in-memory Redis so no test touches a real one."""
    settings = get_settings()
    fake = FakeRedis()
    monkeypatch.setattr(get_cache_service(settings.REDIS_URL, settings.REDIS_KEY_TTL), "_redis", fake)
    yield fake


@pytest.fixture
def stored_config() -> Generator[None, None, None]:
    """Make the Open edX tools load ``OPENEDX_CONFIG`` as the caller's stored settings."""
    with patch("sparkth.plugins.openedx.tools.load_user_plugin_config", AsyncMock(return_value=OPENEDX_CONFIG)):
        yield
