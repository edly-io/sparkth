import json
from typing import Any, Dict, Optional
import aiohttp

from sparkth_mcp.openedx.types import TokenResponse
from sparkth_mcp.request import handle_error_response
from sparkth_mcp.types import AuthenticationError, JsonParseError


class OpenEdxClient:
    def __init__(self, lms_url: str, access_token: Optional[str] = None):
        self.lms_url = lms_url.rstrip("/")
        self.client_id = "login-service-client-id"
        self.session = aiohttp.ClientSession()
        self.access_token = access_token
        self.refresh_token = None
        self.username = None

    async def get_token(self, username: str, password: str) -> Dict[str, Any]:
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
                raise JsonParseError(resp.status(), f"Expected JSON, got: {text[:200]}") from e

        token_response = TokenResponse(**data)
        if not token_response.access_token.strip():
            raise AuthenticationError(401, "empty access_token")

        self.access_token = token_response.access_token
        self.refresh_token = token_response.refresh_token
        return token_response.model_dump()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
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

    async def openedx_authenticate(self) -> Dict[str, Any]:
        return await self.request_jwt(
            method="GET",
            endpoint="api/user/v1/me",
            params=None,
            payload=None,
            base_url=self.lms_url,
        )

    async def request_jwt(
        self,
        method: str,
        endpoint: str,
        base_url: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.access_token:
            raise AuthenticationError(401, "Access token not set")

        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        headers = {"Authorization": f"JWT {self.access_token}"}

        async with self.session.request(
            method,
            url,
            params=params,
            json=payload,
            headers=headers,
        ) as resp:
            if not resp.status < 300:
                raise await handle_error_response(method, url, resp)

            try:
                return await resp.json()
            except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                raise JsonParseError(resp.status, str(e))

    async def close(self):
        await self.session.close()

    def get_username(self) -> Optional[str]:
        return self.username
