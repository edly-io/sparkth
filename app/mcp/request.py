import json
from enum import Enum
from typing import Any, Optional

from aiohttp import ClientPayloadError, ClientResponse, ClientSession, ContentTypeError

from app.mcp.types import LMSError


class Auth(str, Enum):
    JWT = "Jwt"
    BEARER = "Bearer"


async def request(
    method: str = "GET",
    url: str = "",
    session: Optional[ClientSession] = None,
    auth: Auth = Auth.BEARER,
    token: str = "",
    params: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if session is None:
        raise ValueError("ClientSession instance is required.")

    headers = {
        "Authorization": f"{auth.value} {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    async with session.request(method, url, headers=headers, params=params, json=payload) as response:
        if response.status < 200 or response.status >= 300:
            raise await handle_error_response(method, url, response)

        text = await response.text()
        if not text.strip():
            return {}

        try:
            json_value: dict[str, Any] = await response.json()
        except (ContentTypeError, json.JSONDecodeError) as e:
            raise LMSError(method, url, response.status, str(e)) from e

        return json_value


async def handle_error_response(method: str, url: str, response: ClientResponse) -> LMSError:
    try:
        text = await response.text()
    except ClientPayloadError:
        text = ""

    message = text
    try:
        json_val = await response.json()
        if isinstance(json_val, dict) and "message" in json_val:
            message = json_val["message"]
    except ContentTypeError:
        pass

    return LMSError(method, url, response.status, message)
