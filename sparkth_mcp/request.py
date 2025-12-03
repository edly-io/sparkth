from enum import Enum
import json
from typing import Any, Dict, Optional
import aiohttp
from sparkth_mcp.types import LMSError
from sparkth_mcp.canvas.types import PayloadType


class Auth(str, Enum):
    Jwt = "Jwt"
    Bearer = "Bearer"


async def request(
    url: str,
    auth: Auth,
    token: str,
    method: str = "GET",
    payload: Optional[PayloadType] = None,
    session: aiohttp.ClientSession = None,
) -> Dict[str, Any]:
    if session is None:
        raise ValueError("ClientSession instance is required.")

    headers = {
        "Authorization": f"{auth.value} {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    async with session.request(method, url, headers=headers, json=payload) as response:
        if response.status < 200 or response.status >= 300:
            raise await handle_error_response(method, url, response)

        text = await response.text()
        if not text.strip():
            return {}

        try:
            json_value = await response.json()
        except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
            raise LMSError(method, url, response.status, e.message)

        return json_value


async def handle_error_response(method: str, url: str, response: aiohttp.ClientResponse) -> LMSError:
    try:
        text = await response.text()
    except aiohttp.ClientPayloadError:
        text = ""

    message = text
    try:
        json_val = await response.json()
        if isinstance(json_val, dict) and "message" in json_val:
            message = json_val["message"]
    except aiohttp.ContentTypeError:
        pass

    return LMSError(method, url, response.status, message)
