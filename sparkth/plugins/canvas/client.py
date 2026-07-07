from typing import Any
from urllib.parse import urljoin

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import AuthenticationError
from sparkth.lib.http import BaseHttpClient


class CanvasClient(BaseHttpClient):
    """HTTP client for the Canvas LMS REST API."""

    def __init__(self, api_url: str, api_token: str) -> None:
        super().__init__(api_url)
        self.api_token = api_token

    @property
    def token(self) -> str | None:
        return self.api_token or None

    async def _request_dict(
        self, method: Method, endpoint: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call ``_request`` and assert the response is a JSON object."""
        result = await self._request(method, endpoint, payload=payload)
        if not isinstance(result, dict):
            raise ValueError(f"Expected JSON object from {method} {endpoint}, got {type(result).__name__}")
        return result

    async def authenticate(self) -> int:
        """Verify the API token by calling the Canvas self endpoint; returns the HTTP status code."""
        url = urljoin(self.base_url.rstrip("/") + "/", "users/self")

        def _extract(data: dict[str, Any]) -> str | None:
            errors = data.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    return first.get("message")
                if isinstance(first, str):
                    return first
            return None

        async with self.session.get(url, headers={"Authorization": f"Bearer {self.api_token}"}) as response:
            if response.status < 200 or response.status >= 300:
                err = await self._handle_error_response(Method.GET, url, response, error_extractor=_extract)
                raise AuthenticationError(response.status, err.message)
            return response.status

    async def get(self, endpoint: str) -> dict[str, Any]:
        """Send a GET request and return the response as a JSON object."""
        return await self._request_dict(Method.GET, endpoint)

    async def get_all(self, endpoint: str) -> list[Any]:
        """Send a GET request and return the response as a JSON array."""
        result = await self._request(Method.GET, endpoint)
        if not isinstance(result, list):
            raise ValueError(f"Expected JSON array from GET {endpoint}, got {type(result).__name__}")
        return result

    async def post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request with a JSON body and return the response as a JSON object."""
        return await self._request_dict(Method.POST, endpoint, payload)

    async def put(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a PUT request with a JSON body and return the response as a JSON object."""
        return await self._request_dict(Method.PUT, endpoint, payload)

    async def delete(self, endpoint: str) -> dict[str, Any]:
        """Send a DELETE request and return the response as a JSON object."""
        return await self._request_dict(Method.DELETE, endpoint)
