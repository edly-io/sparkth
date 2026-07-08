import json
from typing import Any

from pydantic import ValidationError

from sparkth.lib.enums import Auth, Method
from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.lib.http import BaseHttpClient
from sparkth.plugins.openedx.schemas import TokenResponse


class OpenEdxClient(BaseHttpClient):
    """HTTP client for the Open edX LMS and Studio REST APIs."""

    def __init__(self, lms_url: str, access_token: str | None = None) -> None:
        super().__init__(lms_url, Auth.JWT)
        self.client_id = "login-service-client-id"
        self.access_token = access_token
        self.refresh_token: str | None = None
        self.username = None

    @property
    def token(self) -> str | None:
        return self.access_token

    async def get_token(self, username: str, password: str) -> dict[str, Any]:
        """Exchange username/password credentials for a JWT access token via the OAuth2 password grant."""
        auth_url = f"{self.base_url}/oauth2/access_token"
        form = {
            "client_id": self.client_id,
            "grant_type": "password",
            "token_type": "jwt",
            "username": username,
            "password": password,
        }

        async with self.session.post(auth_url, data=form) as resp:
            if resp.status >= 300:
                raise await self._handle_error_response(Method.POST, auth_url, resp)

            text = await resp.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise LMSRequestError(Method.POST, auth_url, resp.status, f"Expected JSON, got: {text}") from e

        try:
            token_response = TokenResponse(**data)
        except ValidationError as e:
            raise LMSRequestError(Method.POST, auth_url, 200, f"Unexpected token response shape: {e}") from e

        if not token_response.access_token.strip():
            raise AuthenticationError(401, "empty access_token")

        self.access_token = token_response.access_token
        self.refresh_token = token_response.refresh_token
        return token_response.model_dump()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Obtain a new access token using the OAuth2 refresh token grant."""
        auth_url = f"{self.base_url}/oauth2/access_token"
        form = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "token_type": "jwt",
            "refresh_token": refresh_token,
        }

        async with self.session.post(auth_url, data=form) as resp:
            if resp.status >= 300:
                raise await self._handle_error_response(Method.POST, auth_url, resp)
            text = await resp.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise LMSRequestError(Method.POST, auth_url, resp.status, f"Expected JSON, got: {text}") from e

        try:
            token_response = TokenResponse(**data)
        except ValidationError as e:
            raise LMSRequestError(Method.POST, auth_url, 200, f"Unexpected token response shape: {e}") from e

        if not token_response.access_token.strip():
            raise AuthenticationError(401, "empty access_token")

        self.access_token = token_response.access_token
        self.refresh_token = token_response.refresh_token or refresh_token
        return token_response.model_dump()

    async def _request_dict(
        self,
        method: Method,
        endpoint: str,
        *,
        base_url: str | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call ``_request`` and assert the response is a JSON object."""
        result = await self._request(method, endpoint, base_url=base_url, params=params, payload=payload)
        if not isinstance(result, dict):
            raise ValueError(f"Expected JSON object from {method} {endpoint}, got {type(result).__name__}")
        return result

    async def authenticate(self) -> dict[str, Any]:
        """Return the authenticated user's profile from the LMS user API."""
        return await self._request_dict(Method.GET, "api/user/v1/me")

    async def get(self, base_url: str, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a GET request to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.GET, endpoint, base_url=base_url, params=params)

    async def post(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request with a JSON body to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.POST, endpoint, base_url=base_url, payload=payload)

    async def patch(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a PATCH request with a JSON body to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.PATCH, endpoint, base_url=base_url, payload=payload)

    async def delete(self, base_url: str, endpoint: str) -> dict[str, Any]:
        """Send a DELETE request to ``base_url/endpoint`` and return the response as a JSON object."""
        return await self._request_dict(Method.DELETE, endpoint, base_url=base_url)

    def get_username(self) -> str | None:
        """Return the username set during token exchange, if available."""
        return self.username
