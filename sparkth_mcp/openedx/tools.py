from typing import Any, Dict, Optional

import urllib

from pydantic import ValidationError
from sparkth_mcp.types import AuthenticationError, BaseError, JsonParseError, LMSError
from sparkth_mcp.openedx.client import OpenEdxClient
from sparkth_mcp.openedx.types import (
    AccessTokenPayload,
    Auth,
    CreateCourseArgs,
    LMSAccess,
    ListCourseRunsArgs,
    TokenResponse,
    RefreshTokenPayload,
)
from sparkth_mcp.server import mcp


async def openedx_create_basic_component(
    auth: AccessTokenPayload,
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

    created = await client.request_jwt("POST", create_url, studio, payload=payload)

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
    auth: AccessTokenPayload,
    course_id: str,
    locator: str,
    data: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    encoded = urllib.parse.quote(locator, safe="")
    endpoint = f"api/contentstore/v0/xblock/{course_id}/{encoded}"

    if data is None and metadata is None:
        raise LMSError("PATCH", endpoint, 400, "Nothing to update: provide `data` and/or `metadata`")

    studio = auth.studio_url.rstrip("/")
    client = OpenEdxClient(auth.lms_url, access_token=auth.access_token)

    body = {}
    if data is not None:
        body["data"] = data
    if metadata is not None:
        body["metadata"] = metadata

    response = await client.request_jwt("PATCH", endpoint, studio, payload=body)

    return response


@mcp.tool
async def openedx_authenticate(auth: Auth) -> Dict[str, Any]:
    """
    Authenticate the provided Openedx credentials.
    If either argument is missing, the client must supply it. Default values for required fields are never assumed.

    Args:
        payload (Auth): The credentials required for authentication. Include:
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
            raise JsonParseError(401, f"failed to parse auth payload: {e}")

        who = client.get_username() or auth.username

        return {
            "access_token": token_response.access_token,
            "refresh_token": token_response.refresh_token,
            "studio_url": auth.studio_url,
            "message": f"Successfully authenticated as {who}",
        }

    except AuthenticationError as e:
        return {"status": e.status_code, "message": e.message}


@mcp.tool
async def openedx_refresh_access_token(payload: RefreshTokenPayload) -> Dict[str, Any]:
    lms_url = payload.lms_url
    studio_url = payload.studio_url
    refresh_token = payload.refresh_token

    client = OpenEdxClient(lms_url, access_token=None)

    try:
        auth_json = await client.refresh_access_token(refresh_token)

        try:
            token_response = TokenResponse(**auth_json)
        except ValidationError as e:
            raise JsonParseError(401, f"failed to parse refresh payload: {e}")

        new_refresh = token_response.refresh_token or refresh_token

        response = {
            "access_token": token_response.access_token,
            "refresh_token": new_refresh,
            "studio_url": studio_url,
            "message": "Access token refreshed",
        }

        return {"response": response}

    except (JsonParseError, AuthenticationError) as err:
        raise BaseError(err.status_code, err.message)


@mcp.tool
async def openedx_get_user_info(payload: LMSAccess) -> Dict[str, Any]:
    lms_url = payload.lms_url
    access_token = payload.access_token

    client = OpenEdxClient(lms_url, access_token=access_token)

    try:
        res = await client.openedx_authenticate()
        return {"response": res}

    except (JsonParseError, AuthenticationError) as err:
        raise BaseError(err.status_code, err.message)


@mcp.tool
async def openedx_create_course_run(payload: CreateCourseArgs) -> Dict[str, Any]:
    auth = payload.auth
    course = payload.course

    client = OpenEdxClient(auth.lms_url, access_token=auth.access_token)

    try:
        res = await client.request_jwt("POST", "api/v1/course_runs/", auth.studio_url, payload=course.model_dump())

        return {"response": res}

    except (JsonParseError, AuthenticationError) as err:
        raise BaseError(err.status_code, err.message)


@mcp.tool
async def openedx_list_course_runs(payload: ListCourseRunsArgs) -> str:
    auth = payload.auth

    lms = auth.lms_url.rstrip("/")
    studio = auth.studio_url.rstrip("/")

    client = OpenEdxClient(lms, access_token=auth.access_token)
    page = payload.page or 1
    page_size = payload.page_size or 20
    endpoint = f"api/v1/course_runs/?page={page}&page_size={page_size}"

    try:
        res = await client.request_jwt("GET", endpoint, studio)

        return {"courses": res}
    except (JsonParseError, AuthenticationError) as err:
        raise LMSError(err.status_code, f"List course runs failed: {err.message}")
