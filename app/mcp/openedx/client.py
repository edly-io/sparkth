import json
from types import TracebackType
from typing import Any, Optional, Type

import aiohttp

from app.mcp.openedx.types import TokenResponse
from app.mcp.request import Auth, handle_error_response, request
from app.mcp.types import AuthenticationError, JsonParseError


class OpenEdxClient:
    def __init__(self, lms_url: str, access_token: Optional[str] = None):
        self.lms_url = lms_url.rstrip("/")
        self.client_id = "login-service-client-id"
        self.session = aiohttp.ClientSession()
        self.access_token = access_token
        self.refresh_token: Optional[str] = None
        self.username = None

    async def __aenter__(self) -> OpenEdxClient:
        return self

    async def __aexit__(
        self,
        _exc_type: Optional[Type[BaseException]],
        _exc_val: Optional[BaseException],
        _exc_tb: Optional[TracebackType],
    ) -> None:
        await self.close()

    async def get_token(self, username: str, password: str) -> dict[str, Any]:
        auth_url = f"{self.lms_url}/oauth2/access_token"
        form = {
            "client_id": self.client_id,
            "grant_type": "password",
            "token_type": "jwt",
            "username": username,
            "password": password,
        }

        async with self.session.post(auth_url, data=form) as resp:
            if not resp.status < 300:
                raise await handle_error_response("POST", auth_url, resp)

            try:
                data = await resp.json()
            except aiohttp.ContentTypeError as e:
                text = await resp.text()
                raise JsonParseError(resp.status, f"Expected JSON, got: {text}") from e

        token_response = TokenResponse(**data)
        if not token_response.access_token.strip():
            raise AuthenticationError(401, "empty access_token")

        self.access_token = token_response.access_token
        self.refresh_token = token_response.refresh_token
        return token_response.model_dump()

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        auth_url = f"{self.lms_url}/oauth2/access_token"
        form = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "token_type": "jwt",
            "refresh_token": refresh_token,
        }

        async with self.session.post(auth_url, data=form) as resp:
            if not resp.status < 300:
                raise await handle_error_response("POST", auth_url, resp)
            try:
                data = await resp.json()
            except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                raise JsonParseError(resp.status, str(e))

        token_response = TokenResponse(**data)

        if not token_response.access_token.strip():
            raise AuthenticationError(401, "empty access_token")

        self.access_token = token_response.access_token
        self.refresh_token = token_response.refresh_token or refresh_token
        return token_response.model_dump()

    async def authenticate(self) -> dict[str, Any]:
        return await self.get(self.lms_url, "api/user/v1/me")

    async def get(self, base_url: str, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return await self.request_jwt("GET", base_url, endpoint)

    async def post(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_jwt("POST", base_url, endpoint, payload=payload)

    async def patch(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.request_jwt("PATCH", base_url, endpoint, payload=payload)

    async def delete(self, base_url: str, endpoint: str) -> dict[str, Any]:
        return await self.request_jwt("DELETE", base_url, endpoint)

    async def request_jwt(
        self,
        method: str,
        base_url: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if not self.access_token:
            raise AuthenticationError(401, "Access token not set")

        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        return await request(method, url, self.session, Auth.JWT, self.access_token, params, payload)

    async def close(self) -> None:
        await self.session.close()

    def get_username(self) -> Optional[str]:
        return self.username
