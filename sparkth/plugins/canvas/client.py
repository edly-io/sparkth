from typing import Any
from urllib.parse import urljoin

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import AuthenticationError
from sparkth.lib.http import BaseHttpClient
from sparkth.plugins.canvas.config import CanvasConfig


class CanvasClient(BaseHttpClient):
    """HTTP client for the Canvas LMS REST API."""

    def __init__(self, config: CanvasConfig) -> None:
        super().__init__(str(config.api_url))
        self.api_token = config.api_key

    @property
    def token(self) -> str | None:
        return self.api_token or None

    async def request(self, method: Method, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a request, with ``payload`` as its JSON body if given, and return the JSON object it answers."""
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

    async def get_all(self, endpoint: str) -> list[Any]:
        """Send a GET request and return the response as a JSON array."""
        result = await self._request(Method.GET, endpoint)
        if not isinstance(result, list):
            raise ValueError(f"Expected JSON array from GET {endpoint}, got {type(result).__name__}")
        return result
