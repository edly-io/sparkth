from unittest.mock import patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from sparkth.lib.cache import get_cache_service
from sparkth.lib.exceptions import LMSRequestError
from sparkth.lib.settings import get_settings
from sparkth.plugins.openedx.client import OpenEdxClient, access_token_cache
from sparkth.plugins.openedx.config import OpenEdxConfig
from sparkth.plugins.openedx.tests.conftest import OPENEDX_CONFIG, FakeRedis, http_response, http_session

PROFILE = '{"username": "u"}'


def _token(value: str = "tok-1", extra: str = "") -> str:
    return f'{{"access_token": "{value}"{extra}}}'


async def _authenticate(user_id: int = 1, config: OpenEdxConfig = OPENEDX_CONFIG) -> dict[str, str]:
    async with OpenEdxClient(config, user_id) as client:
        return await client.authenticate()


def _key(user_id: int = 1, config: OpenEdxConfig = OPENEDX_CONFIG) -> str:
    return access_token_cache(user_id, config)[1]


async def test_a_token_is_granted_once_and_reused_by_the_next_client(fake_redis: FakeRedis) -> None:
    session = http_session(_token(), http_response(200, PROFILE), http_response(200, PROFILE))
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        await _authenticate()
        await _authenticate()

    assert session.post.call_count == 1
    assert session.request.call_args.kwargs["headers"]["Authorization"] == "Jwt tok-1"


async def test_tokens_are_never_shared_between_users(fake_redis: FakeRedis) -> None:
    session = http_session(_token(), http_response(200, PROFILE), http_response(200, PROFILE))
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        await _authenticate(1)
        await _authenticate(2)

    assert session.post.call_count == 2
    assert set(fake_redis.store) == {_key(1), _key(2)}


async def test_a_401_drops_the_token_grants_a_new_one_and_retries_once(fake_redis: FakeRedis) -> None:
    fake_redis.store[_key()] = "stale"
    session = http_session(_token(), http_response(401, "expired"), http_response(200, PROFILE))
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        result = await _authenticate()

    assert result == {"username": "u"}
    assert session.post.call_count == 1
    assert fake_redis.store[_key()] == "tok-1"
    auth_headers = [c.kwargs["headers"]["Authorization"] for c in session.request.call_args_list]
    assert auth_headers == ["Jwt stale", "Jwt tok-1"]


async def test_a_second_401_is_reported_not_retried_again(fake_redis: FakeRedis) -> None:
    session = http_session(
        _token(), http_response(401, "expired"), http_response(401, "expired"), http_response(401, "expired")
    )
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        with pytest.raises(LMSRequestError) as exc:
            await _authenticate()

    assert exc.value.status_code == 401
    assert session.request.call_count == 2


@pytest.mark.parametrize(
    ("extra", "expected_ttl"),
    [(', "expires_in": 3600', 3540), (', "expires_in": 30', 1)],
)
async def test_the_cached_token_never_outlives_open_edx_s_expiry(
    fake_redis: FakeRedis, extra: str, expected_ttl: int
) -> None:
    session = http_session(_token(extra=extra), http_response(200, PROFILE))
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        await _authenticate()

    assert fake_redis.ttls[_key()] == expected_ttl


async def test_a_token_without_expiry_uses_the_cache_default_ttl(fake_redis: FakeRedis) -> None:
    session = http_session(_token(), http_response(200, PROFILE))
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        await _authenticate()

    assert fake_redis.ttls[_key()] == get_settings().REDIS_KEY_TTL


class UnreachableRedis:
    async def get(self, key: str) -> str | None:
        raise RedisConnectionError("down")

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        raise RedisConnectionError("down")

    async def delete(self, key: str) -> int:
        raise RedisConnectionError("down")


async def test_an_unreachable_cache_still_lets_the_call_run(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(get_cache_service(settings.REDIS_URL, settings.REDIS_KEY_TTL), "_redis", UnreachableRedis())
    session = http_session(_token(), http_response(200, PROFILE))
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        result = await _authenticate()

    assert result == {"username": "u"}
    assert session.post.call_count == 1


@pytest.mark.parametrize(
    "body", ['{"refresh_token": "leak-me"}', '{"access_token": "leak-me", "expires_in": "leak-me"}', '["leak-me"]']
)
async def test_a_malformed_token_response_never_leaks_its_body(
    fake_redis: FakeRedis, caplog: pytest.LogCaptureFixture, body: str
) -> None:
    session = http_session(body)
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        with pytest.raises(LMSRequestError) as exc:
            await _authenticate()

    assert "leak-me" not in exc.value.message
    assert exc.value.__cause__ is None
    assert "leak-me" not in caplog.text


async def test_a_non_json_token_response_never_echoes_its_body(fake_redis: FakeRedis) -> None:
    session = http_session("token=leak-me")
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        with pytest.raises(LMSRequestError) as exc:
            await _authenticate()

    assert "leak-me" not in exc.value.message


async def test_saved_new_settings_get_a_new_token(fake_redis: FakeRedis) -> None:
    changed = OPENEDX_CONFIG.model_copy(update={"lms_password": "new-pass"})
    session = http_session(_token(), http_response(200, PROFILE), http_response(200, PROFILE))
    with patch("sparkth.lib.http.ClientSession", return_value=session):
        await _authenticate(1)
        await _authenticate(1, changed)

    assert session.post.call_count == 2
    assert session.post.call_args.kwargs["data"]["password"] == "new-pass"
    assert set(fake_redis.store) == {_key(1), _key(1, changed)}


def test_the_cache_key_carries_no_setting_in_the_clear() -> None:
    key = _key()

    assert key.startswith("openedx:access-token:1:")
    for value in ("lms.example.com", "testuser", "testpass"):
        assert value not in key
