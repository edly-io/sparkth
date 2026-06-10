"""Unit tests for app.lib.http.BaseHttpClient._request and _handle_error_response."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.lib.enums import Auth, Method
from app.lib.exceptions import AuthenticationError, LMSRequestError
from app.lib.http import BaseHttpClient


class _ConcreteClient(BaseHttpClient):
    """Minimal subclass with a fixed token for testing."""

    def __init__(self, token: str | None = "tok") -> None:
        super().__init__("https://api.example.com")
        self._token = token

    @property
    def token(self) -> str | None:
        return self._token


def _make_session(*, status: int = 200, body: str = "{}") -> MagicMock:
    """Return a mock aiohttp.ClientSession whose request() yields a canned response."""
    response = AsyncMock()
    response.status = status
    response.text = AsyncMock(return_value=body)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.request.return_value = response
    session.closed = False
    session.close = AsyncMock()
    return session


class TestRequestAuthGuard:
    async def test_raises_authentication_error_when_no_token(self) -> None:
        with patch("app.lib.http.ClientSession", return_value=_make_session()):
            async with _ConcreteClient(token=None) as client:
                with pytest.raises(AuthenticationError) as exc_info:
                    await client._request(Method.GET, "/anything")
        assert exc_info.value.status_code == 401

    async def test_raises_authentication_error_for_empty_string_token(self) -> None:
        with patch("app.lib.http.ClientSession", return_value=_make_session()):
            async with _ConcreteClient(token="") as client:
                with pytest.raises(AuthenticationError):
                    await client._request(Method.GET, "/anything")


class TestRequestUrlBuilding:
    async def test_strips_trailing_slash_from_base_url(self) -> None:
        session = _make_session(body='{"ok": true}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                client.base_url = "https://api.example.com/"
                await client._request(Method.GET, "resource")
        call_url = session.request.call_args[0][1]
        assert call_url == "https://api.example.com/resource"

    async def test_strips_leading_slash_from_endpoint(self) -> None:
        session = _make_session(body='{"ok": true}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                await client._request(Method.GET, "/resource")
        call_url = session.request.call_args[0][1]
        assert call_url == "https://api.example.com/resource"

    async def test_base_url_override_is_used_over_instance_base(self) -> None:
        session = _make_session(body='{"ok": true}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                await client._request(Method.GET, "ep", base_url="https://other.example.com")
        call_url = session.request.call_args[0][1]
        assert call_url == "https://other.example.com/ep"


class TestRequestResponseParsing:
    async def test_returns_dict_for_json_object(self) -> None:
        session = _make_session(body='{"id": 1}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                result = await client._request(Method.GET, "/ep")
        assert result == {"id": 1}

    async def test_returns_list_for_json_array(self) -> None:
        session = _make_session(body="[1, 2, 3]")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                result = await client._request(Method.GET, "/ep")
        assert result == [1, 2, 3]

    async def test_returns_empty_dict_for_empty_body(self) -> None:
        session = _make_session(body="")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                result = await client._request(Method.GET, "/ep")
        assert result == {}

    async def test_returns_empty_dict_for_whitespace_only_body(self) -> None:
        session = _make_session(body="   \n  ")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                result = await client._request(Method.GET, "/ep")
        assert result == {}

    async def test_raises_lms_request_error_for_invalid_json(self) -> None:
        session = _make_session(body="not-json")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                with pytest.raises(LMSRequestError):
                    await client._request(Method.GET, "/ep")

    async def test_raises_lms_request_error_on_non_2xx(self) -> None:
        session = _make_session(status=404, body='{"message": "not found"}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                with pytest.raises(LMSRequestError) as exc_info:
                    await client._request(Method.GET, "/ep")
        assert exc_info.value.status_code == 404


class TestRequestHeaders:
    async def _captured_headers(self, auth: Auth = Auth.BEARER) -> dict[str, Any]:
        session = _make_session(body="{}")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                client.auth = auth
                await client._request(Method.GET, "/ep")
        return cast(dict[str, Any], session.request.call_args[1]["headers"])

    async def test_bearer_authorization_header(self) -> None:
        headers = await self._captured_headers(Auth.BEARER)
        assert headers["Authorization"] == "Bearer tok"

    async def test_jwt_authorization_header(self) -> None:
        headers = await self._captured_headers(Auth.JWT)
        assert headers["Authorization"] == "Jwt tok"

    async def test_content_type_set_when_payload_provided(self) -> None:
        session = _make_session(body="{}")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                await client._request(Method.POST, "/ep", payload={"x": 1})
        headers = session.request.call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"

    async def test_content_type_absent_when_no_payload(self) -> None:
        session = _make_session(body="{}")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                await client._request(Method.GET, "/ep")
        headers = session.request.call_args[1]["headers"]
        assert "Content-Type" not in headers

    async def test_content_type_override(self) -> None:
        session = _make_session(body="{}")
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                await client._request(Method.POST, "/ep", content_type="text/plain")
        headers = session.request.call_args[1]["headers"]
        assert headers["Content-Type"] == "text/plain"


class TestHandleErrorResponse:
    async def test_extracts_message_field_by_default(self) -> None:
        session = _make_session(status=422, body='{"message": "bad input"}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                with pytest.raises(LMSRequestError) as exc_info:
                    await client._request(Method.POST, "/ep", payload={})
        assert "bad input" in exc_info.value.message

    async def test_falls_back_to_raw_body_when_no_message_key(self) -> None:
        session = _make_session(status=500, body='{"error": "kaboom"}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                with pytest.raises(LMSRequestError) as exc_info:
                    await client._request(Method.GET, "/ep")
        assert '{"error": "kaboom"}' in exc_info.value.message

    async def test_error_extractor_overrides_default_message_field(self) -> None:
        session = _make_session(status=403, body='{"detail": "forbidden"}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                # Simulate calling _handle_error_response with a custom extractor.
                fake_response = AsyncMock()
                fake_response.text = AsyncMock(return_value='{"detail": "forbidden"}')
                err = await client._handle_error_response(
                    Method.GET,
                    "https://api.example.com/ep",
                    fake_response,
                    error_extractor=lambda d: d.get("detail"),
                )
        assert err.message == "forbidden"

    async def test_lms_request_error_str_includes_method_as_plain_value(self) -> None:
        """Method enum must render as 'GET', not 'Method.GET', in the error string."""
        session = _make_session(status=404, body='{"message": "nope"}')
        with patch("app.lib.http.ClientSession", return_value=session):
            async with _ConcreteClient() as client:
                with pytest.raises(LMSRequestError) as exc_info:
                    await client._request(Method.GET, "/ep")
        assert str(exc_info.value).startswith("GET ")
        assert "Method.GET" not in str(exc_info.value)
