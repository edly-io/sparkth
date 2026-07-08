import json
from collections.abc import Callable
from types import TracebackType
from typing import Any, Self

from aiohttp import ClientPayloadError, ClientResponse, ClientSession

from sparkth.lib.enums import Auth, Method
from sparkth.lib.exceptions import AuthenticationError, LMSRequestError


class BaseHttpClient:
    """Shared base for HTTP API clients that authenticate with a token.

    Subclasses provide a ``token`` property and call ``_request()`` instead of
    duplicating the token-check + URL-join logic.
    The optional ``base_url`` override on ``_request`` supports clients whose
    verb methods accept a per-call base URL (e.g. OpenEdxClient).
    """

    def __init__(self, base_url: str, auth: Auth = Auth.BEARER) -> None:
        """Initialise the client with a base URL and authentication scheme."""
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.session: ClientSession = ClientSession()

    @property
    def token(self) -> str | None:
        """Return the bearer token for the current session; override in subclasses."""
        return None

    async def _request(
        self,
        method: Method,
        endpoint: str,
        *,
        base_url: str | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        data: Any | None = None,
        content_type: str | None = None,
    ) -> Any:
        """Execute an authenticated HTTP request and return the parsed response body.

        Use ``payload`` for JSON bodies (sets Content-Type: application/json automatically),
        ``data`` for form/multipart/raw bodies, and ``content_type`` to override the header
        explicitly. Raises ``AuthenticationError`` when no token is available and
        ``LMSRequestError`` on non-2xx responses or unparseable JSON.
        """
        tok = self.token
        if not tok:
            raise AuthenticationError(401, "Not authenticated")
        resolved = (base_url or self.base_url).rstrip("/")
        url = f"{resolved}/{endpoint.lstrip('/')}"
        effective_content_type = content_type or ("application/json" if payload is not None else None)
        headers: dict[str, str] = {
            "Authorization": f"{self.auth.value} {tok}",
            "Accept": "application/json",
        }
        if effective_content_type is not None:
            headers["Content-Type"] = effective_content_type
        async with self.session.request(
            method, url, headers=headers, params=params, json=payload, data=data
        ) as response:
            if response.status < 200 or response.status >= 300:
                raise await self._handle_error_response(method, url, response)

            text = await response.text()
            if not text.strip():
                return {}

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as e:
                raise LMSRequestError(method, url, response.status, str(e)) from e

            return parsed

    async def _handle_error_response(
        self,
        method: Method,
        url: str,
        response: ClientResponse,
        error_extractor: Callable[[dict[str, Any]], str | None] | None = None,
    ) -> LMSRequestError:
        """Build an ``LMSRequestError`` from a non-2xx response, extracting the message from the body when possible."""
        try:
            text = await response.text()
        except ClientPayloadError:
            text = ""

        message = text
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                extracted = error_extractor(data) if error_extractor else data.get("message")
                if extracted is not None:
                    message = extracted
        except json.JSONDecodeError:
            pass

        return LMSRequestError(method, url, response.status, message)

    async def __aenter__(self) -> Self:
        """Return self to support use as an async context manager."""
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """Close the underlying session on context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the underlying aiohttp session if it is still open."""
        if not self.session.closed:
            await self.session.close()
