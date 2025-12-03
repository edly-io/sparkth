from typing import Any, Dict, Optional

import urllib

from pydantic import ValidationError
from sparkth_mcp.types import AuthenticationError, LMSError
from sparkth_mcp.openedx.client import OpenEdxClient
from sparkth_mcp.openedx.types import OpenEdxAccessTokenPayload, OpenEdxAuth, TokenResponse
from sparkth_mcp.server import mcp


async def openedx_create_basic_component(
    auth: OpenEdxAccessTokenPayload,
    course_id: str,
    unit_locator: str,
    kind: str,
    display_name: str,
) -> str:
    studio = auth.studio_url.rstrip("/")
    client = OpenEdxClient(auth.lms_url, access_token=auth.access_token)

    create_url = f"api/contentstore/v0/xblock/{course_id}"

    payload = {
        "category": kind,
        "parent_locator": unit_locator,
        "display_name": display_name,
    }

    created = await client.request_jwt(
        method="POST",
        endpoint=create_url,
        params=None,
        payload=payload,
        base_url=studio,
    )

    if isinstance(created, dict):
        locator = created.get("locator") or created.get("usage_key") or created.get("id")
        if isinstance(locator, str):
            return locator

    if isinstance(created, list) and created:
        first = created[0]
        locator = first.get("locator") or first.get("usage_key") or first.get("id")
        if isinstance(locator, str):
            return locator


async def openedx_update_xblock_content(
    auth: OpenEdxAccessTokenPayload,
    course_id: str,
    locator: str,
    data: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    endpoint = f"api/contentstore/v0/xblock/{course_id}/{encoded}"

    if data is None and metadata is None:
        raise LMSError("PATCH", endpoint, 400, "Nothing to update: provide `data` and/or `metadata`")

    studio = auth.studio_url.rstrip("/")
    client = OpenEdxClient(auth.lms_url, access_token=auth.access_token)

    encoded = urllib.parse.quote(locator, safe="")

    body = {}
    if data is not None:
        body["data"] = data
    if metadata is not None:
        body["metadata"] = metadata

    response = await client.request_jwt(
        method="PATCH",
        endpoint=endpoint,
        params=None,
        payload=body,
        base_url=studio,
    )

    return response


@mcp.tool
async def openedx_authenticate(auth: OpenEdxAuth) -> Dict[str, Any]:
    """
    Authenticate the provided Openedx credentials.
    If either argument is missing, the client must supply it. Default values for required fields are never assumed.

    Args:
        payload (OpenEdxAuth): The credentials required for authentication. Include:
            lms_url (str): The open edx lms URL.
            studio_url (str): The open edx studio URL.
            username (str)
            password (str)
    """
    client = OpenEdxClient(auth.lms_url)
    try:
        auth_json = await client.get_token(auth.username, auth.password)
        try:
            token_response = TokenResponse(**auth_json)
        except ValidationError as e:
            raise LMSError(f"failed to parse auth payload: {e}")

    except AuthenticationError as e:
        return {"status": e.status_code, "message": e.message}
