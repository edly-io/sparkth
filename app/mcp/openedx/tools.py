import urllib
from typing import Any, Optional
from urllib.parse import quote

from app.mcp.types import AuthenticationError, JsonParseError, LMSError
from app.mcp.openedx.client import OpenEdxClient
from app.mcp.openedx.types import (
    AccessTokenPayload,
    Auth,
    BlockContentArgs,
    Component,
    CourseTreeRequest,
    CreateCourseArgs,
    ListCourseRunsArgs,
    LMSAccess,
    ProblemOrHtmlArgs,
    RefreshTokenPayload,
    TokenResponse,
    UpdateXBlockPayload,
    XBlockPayload,
)
from app.mcp.server import mcp


async def openedx_create_basic_component(
    auth: AccessTokenPayload,
    course_id: str,
    unit_locator: str,
    kind: str,
    display_name: str,
) -> str:
    studio = auth.studio_url.rstrip("/")
    create_url = f"api/contentstore/v0/xblock/{course_id}"

    payload = {
        "category": kind,
        "parent_locator": unit_locator,
        "display_name": display_name,
    }

    async with OpenEdxClient(auth.lms_url, auth.access_token) as client:
        try:
            created = await client.post(studio, create_url, payload)
        except (AuthenticationError, JsonParseError) as e:
            raise LMSError("POST", create_url, e.status_code, e.message) from e

        if isinstance(created, dict):
            locator = created.get("locator") or created.get("usage_key") or created.get("id")
            if isinstance(locator, str):
                return locator

        if isinstance(created, list) and created:
            first = created[0]
            locator = first.get("locator") or first.get("usage_key") or first.get("id")
            if isinstance(locator, str):
                return locator

        raise LMSError("POST", create_url, 500, "Invalid response format: missing locator")


async def openedx_update_xblock_content(
    auth: AccessTokenPayload,
    course_id: str,
    locator: str,
    data: Optional[str],
    metadata: Optional[dict[str, Any]],
) -> dict[str, Any]:
    encoded = urllib.parse.quote(locator, safe="")
    endpoint = f"api/contentstore/v0/xblock/{course_id}/{encoded}"

    if data is None and metadata is None:
        raise LMSError("PATCH", endpoint, 400, "Nothing to update: provide `data` and/or `metadata`")

    studio = auth.studio_url.rstrip("/")

    body: dict[str, Any] = {}
    if data is not None:
        body["data"] = data
    if metadata is not None:
        body["metadata"] = metadata

    async with OpenEdxClient(auth.lms_url, auth.access_token) as client:
        try:
            response = await client.patch(studio, endpoint, body)
        except (JsonParseError, AuthenticationError) as err:
            raise LMSError(
                "PATCH",
                endpoint,
                err.status_code,
                f"Updating XBlock {locator} for course ({course_id}) failed: {err.message}",
            ) from err

        return response


@mcp.tool
async def openedx_authenticate(auth: Auth) -> dict[str, Any]:
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
    async with OpenEdxClient(auth.lms_url) as client:
        try:
            auth_json = await client.get_token(auth.username, auth.password)
            token_response = TokenResponse(**auth_json)
            who = client.get_username() or auth.username

            return {
                "access_token": token_response.access_token,
                "refresh_token": token_response.refresh_token,
                "studio_url": auth.studio_url,
                "message": f"Successfully authenticated as {who}",
            }

        except AuthenticationError as err:
            return {
                "error": {
                    "status_code": err.status_code,
                    "message": f"Open edX authentication failed: {err.message}",
                }
            }


@mcp.tool
async def openedx_refresh_access_token(payload: RefreshTokenPayload) -> dict[str, Any]:
    """
    Refresh the Open edX access token using the provided refresh token.

    Args:
        payload (RefreshTokenPayload):
            An object containing:
                - lms_url (str): Base URL of the LMS instance.
                - studio_url (str): Corresponding Studio URL to include in the response.
                - refresh_token (str): The refresh token used to obtain a new access token.

    Returns:
        dict[str, Any]:
            A dictionary with one of the following shapes:

            Successful response:
            {
                "response": {
                    "access_token": str,
                    "refresh_token": str,
                    "studio_url": str,
                    "message": "Access token refreshed",
                }
            }

            Error response:
            {
                "error": {
                    "status_code": int,
                    "message": str,
                }
            }
    """
    lms_url = payload.lms_url
    studio_url = payload.studio_url
    refresh_token = payload.refresh_token

    async with OpenEdxClient(lms_url) as client:
        try:
            auth_json = await client.refresh_access_token(refresh_token)
            token_response = TokenResponse(**auth_json)
            new_refresh = token_response.refresh_token or refresh_token

            response = {
                "access_token": token_response.access_token,
                "refresh_token": new_refresh,
                "studio_url": studio_url,
                "message": "Access token refreshed",
            }

            return {"response": response}

        except (JsonParseError, AuthenticationError) as err:
            return {"error": {"status_code": err.status_code, "message": f"Refresh token failed: {err.message}"}}


@mcp.tool
async def openedx_get_user_info(payload: LMSAccess) -> dict[str, Any]:
    """
    Retrieve authenticated user information from an Open edX LMS instance.

    Args:
        payload (LMSAccess):
            An object containing:
                - lms_url (str): Base URL of the LMS instance.
                - access_token (str): The access token used to authenticate the request.

    Returns:
        dict[str, Any]:
            A dictionary with one of the following shapes:

            Successful response:
            {
                "response": <user_info_dict>
            }

            Error response:
            {
                "error": {
                    "status_code": int,
                    "message": str,
                }
            }
    """
    lms_url = payload.lms_url
    access_token = payload.access_token

    async with OpenEdxClient(lms_url, access_token) as client:
        try:
            res = await client.authenticate()
            return {"response": res}

        except (JsonParseError, AuthenticationError) as err:
            return {
                "error": {
                    "status_code": err.status_code,
                    "message": err.message,
                }
            }


@mcp.tool
async def openedx_create_course_run(payload: CreateCourseArgs) -> dict[str, Any]:
    """
    Create a new course run in an Open edX Studio instance.

    Args:
        payload (CreateCourseArgs):
            An object containing:
                - auth: Authentication information including:
                    * lms_url (str): Base LMS URL.
                    * studio_url (str): Base Studio URL for POST requests.
                    * access_token (str): Token used to authenticate requests.
                - course: A Pydantic model with the course run data to submit.

    Returns:
        dict[str, Any]:
            A dictionary with one of the following shapes:

            Successful response:
            {
                "response": <course_run_response_dict>
            }

            Error response:
            {
                "error": {
                    "method": "POST",
                    "endpoint": "api/v1/course_runs/",
                    "status_code": int,
                    "message": str,
                }
            }
    """
    auth = payload.auth
    course = payload.course
    endpoint = "api/v1/course_runs/"

    async with OpenEdxClient(auth.lms_url, auth.access_token) as client:
        try:
            res = await client.post(auth.studio_url, endpoint, course.model_dump())
            return {"response": res}
        except (JsonParseError, AuthenticationError) as err:
            return {
                "error": {
                    "method": "POST",
                    "endpoint": endpoint,
                    "status_code": err.status_code,
                    "message": f"Course runs creation failed: {err.message}",
                }
            }


@mcp.tool
async def openedx_list_course_runs(payload: ListCourseRunsArgs) -> dict[str, Any]:
    """
    Retrieve a paginated list of course runs from an Open edX Studio instance.

    Args:
        payload (ListCourseRunsArgs):
            An object containing:
                - auth: Authentication data including:
                    * lms_url (str): LMS base URL.
                    * studio_url (str): Studio base URL for API access.
                    * access_token (str): Token used for API authentication.
                - page (int, optional): Page number for pagination. Defaults to 1.
                - page_size (int, optional): Number of results per page.
                  Defaults to 20.

    Returns:
        dict[str, Any]:
            A dictionary with one of the following shapes:

            Successful response:
            {
                "courses": <list_or_paginated_result_dict>
            }

            Error response:
            {
                "error": {
                    "method": "GET",
                    "endpoint": str,
                    "status_code": int,
                    "message": str,
                }
            }
    """
    auth = payload.auth

    lms = auth.lms_url.rstrip("/")
    base_url = auth.studio_url.rstrip("/")
    page = payload.page or 1
    page_size = payload.page_size or 20
    endpoint = f"api/v1/course_runs/?page={page}&page_size={page_size}"

    async with OpenEdxClient(lms, auth.access_token) as client:
        try:
            res = await client.get(base_url, endpoint)
            return {"courses": res}

        except (JsonParseError, AuthenticationError) as err:
            return {
                "error": {
                    "method": "GET",
                    "endpoint": endpoint,
                    "status_code": err.status_code,
                    "message": f"List course runs failed: {err.message}",
                }
            }


@mcp.tool
async def openedx_create_xblock(payload: XBlockPayload) -> dict[str, Any]:
    """
    Create a new XBlock within an Open edX course.

    Args:
        payload (XBlockPayload):
            An object containing:
                - auth: Authentication details including:
                    * lms_url (str): LMS base URL.
                    * studio_url (str): Studio base URL for API calls.
                    * access_token (str): Token used for authenticated requests.
                - xblock: A Pydantic model with the XBlock fields to be created.
                - course_id (str): The course identifier where the XBlock
                  should be created.

    Returns:
        dict[str, Any]:
            A dictionary with one of the following shapes:

            Successful response:
            {
                "response": <xblock_creation_response_dict>
            }

            Error response:
            {
                "error": {
                    "method": "POST",
                    "endpoint": str,
                    "status_code": int,
                    "message": str,
                }
            }
    """
    auth = payload.auth
    xblock = payload.xblock
    course_id = payload.course_id
    endpoint = f"api/contentstore/v0/xblock/{course_id}"

    async with OpenEdxClient(auth.lms_url, auth.access_token) as client:
        try:
            res = await client.post(
                auth.studio_url,
                endpoint,
                xblock.model_dump(),
            )

            return {"response": res}

        except (JsonParseError, AuthenticationError) as err:
            return {
                "error": {
                    "method": "POST",
                    "endpoint": endpoint,
                    "status_code": err.status_code,
                    "message": f"XBlock creation failed: {err.message}",
                }
            }


@mcp.tool
async def openedx_create_problem_or_html(payload: ProblemOrHtmlArgs) -> dict[str, Any]:
    """
    Create either a Problem or HTML XBlock component, then update the XBlock
    using the `update` tool.

    This function supports creating two types of components:
    - **problem**: An OLX problem component. (Default)
    - **html**: An HTML content component.

    Behavior:
        • The HTML component is created in the same unit.
        • The Problem component is created in a separate unit.
        • After creation, the XBlock is automatically updated via the update tool.

    Parameters:
        payload (ProblemOrHtmlArgs): Consists of:
            kind (str, optional):
                The type of component to create. Accepts "Problem" or "HTML".
                Defaults to "Problem".

            data (str, optional):
                Raw OLX (for problems) or HTML (for HTML components).
                If provided, this content fully defines the component.

            mcq_boilerplate (bool, optional):
                When True and no custom `data` is supplied, generates a minimal
                multiple-choice problem template. Only valid if `kind="problem"`.
                Default template used:

                <problem>
                    <p>Your question here</p>
                    <multiplechoiceresponse>
                        <choicegroup type="MultipleChoice" shuffle="true">
                        <choice correct="true">Correct</choice>
                        <choice correct="false">Incorrect</choice>
                        </choicegroup>
                    </multiplechoiceresponse>
                </problem>

            metadata (dict, optional):
                Optional component metadata, such as:
                - display_name
                - weight
                - max_attempts
                - any other supported XBlock fields.

    Returns:
        dict[str, Any]: A dictionary containing the XBlock creation result:
            `{
                "response": {
                    "locator": <str>,
                    "result": <Any>
                }
            }`

    """
    auth = payload.auth
    course_id = payload.course_id
    unit_locator = payload.unit_locator
    kind = payload.kind
    display_name = payload.display_name
    data = payload.data
    metadata = payload.metadata
    mcq_boilerplate = payload.mcq_boilerplate

    component = kind or Component.PROBLEM

    if display_name:
        name = display_name
    else:
        name = "New Problem" if component == Component.PROBLEM else "New HTML"

    try:
        locator = await openedx_create_basic_component(auth, course_id, unit_locator, component, name)
    except LMSError as err:
        return {
            "error": {
                "method": err.method,
                "endpoint": err.url,
                "status_code": err.status_code,
                "message": err.message,
            }
        }

    if data is not None:
        final_data = data
    elif component == Component.PROBLEM and mcq_boilerplate:
        final_data = """<problem>
                  <p>Your question here</p>
                  <multiplechoiceresponse>
                    <choicegroup type="MultipleChoice" shuffle="true">
                      <choice correct="true">Correct</choice>
                      <choice correct="false">Incorrect</choice>
                    </choicegroup>
                  </multiplechoiceresponse>
               </problem>"""
    else:
        final_data = None

    if final_data is not None or metadata is not None:
        try:
            updated = await openedx_update_xblock_content(
                auth,
                course_id,
                locator,
                final_data,
                metadata,
            )
        except LMSError as err:
            return {
                "error": {
                    "method": err.method,
                    "endpoint": err.url,
                    "status_code": err.status_code,
                    "message": err.message,
                }
            }

        result_value = updated

    else:
        result_value = {"detail": "Component created; no content/metadata to update"}

    out = {"locator": locator, "result": result_value}

    return {"response": out}


@mcp.tool
async def openedx_update_xblock(payload: UpdateXBlockPayload) -> dict[str, Any]:
    """
    Update an XBlock (chapter/section, sequential/subsection, or vertical/unit)
    in an Open edX course.

    This updates either the component's raw content (`data`) or its metadata
    fields (`metadata`). At least one must be provided.

    Expected locator format:
        block-v1:ORG+COURSE+RUN+type@course+block@course

    Parameters
    ----------
    payload : UpdateXBlockPayload
        A Pydantic model containing:
            auth (AccessTokenPayload):
                Authentication info required to authorize the update.
            course_id (str):
                The course key (e.g., "course-v1:ORG+COURSE+RUN").
            locator (str):
                The usage key of the XBlock to update.
            data (str, optional):
                OLX or HTML markup to replace the XBlock body.
            metadata (dict, optional):
                Metadata fields to update (e.g., display_name, weight, max_attempts).

    Returns
    -------
    dict[str, Any]: A dictionary containing the XBlock update result

    """
    try:
        response = await openedx_update_xblock_content(
            payload.auth,
            payload.course_id,
            payload.locator,
            payload.data,
            payload.metadata,
        )
        return {"response": response}

    except LMSError as err:
        return {
            "error": {
                "method": err.method,
                "endpoint": err.url,
                "status_code": err.status_code,
                "message": err.message,
            }
        }


@mcp.tool
async def openedx_get_course_tree_raw(payload: CourseTreeRequest) -> dict[str, Any]:
    """
    Fetch the full block graph ("course tree") for a course using the
    Open edX Course Blocks API.

    This returns raw block metadata including display names, block types,
    children lists, scheduling fields, URLs, and other structural information.

    API endpoint:
        GET /api/courses/v1/blocks/

    Parameters
    ----------
    payload : CourseTreeRequest
        A Pydantic model containing:
            auth (AccessTokenPayload):
                LMS URL and access token for authentication.
            course_id (str):
                Course key (e.g. "course-v1:ORG+COURSE+RUN").

    Returns
    -------
    dict[str, Any]
        A dictionary with one of the following shapes:
            {"response": <parsed API response>}
        or on error:
            {"error": "<message>"}
    """
    params = {
        "course_id": payload.course_id,
        "depth": "all",
        "all_blocks": "true",
        "requested_fields": ("children,display_name,type,graded,student_view_url,block_id,due,start,format"),
    }

    async with OpenEdxClient(
        payload.auth.lms_url,
        payload.auth.access_token,
    ) as client:
        try:
            response = await client.get(
                payload.auth.lms_url,
                "api/courses/v1/blocks/",
                params,
            )

            return {"response": response}

        except LMSError as err:
            return {
                "error": {
                    "method": err.method,
                    "endpoint": err.url,
                    "status_code": err.status_code,
                    "message": f"Failed to get course tree: {err.message}",
                }
            }


@mcp.tool
async def openedx_get_block_contentstore(
    payload: BlockContentArgs,
) -> dict[str, Any]:
    """
    Read the content of a specific XBlock directly from the **Studio ContentStore**.

    This is the API to use when a user requests reading (and then updating)
    the raw content of components—especially:
        • HTML blocks
        • MCQ / OLX-based problems
        • Any block whose OLX content must be patched or rewritten

    This endpoint REQUIRES a valid XBlock locator.

    Endpoint format:
        GET /api/contentstore/v0/xblock/{course_id}/{encoded_locator}

    Parameters
    ----------
    payload : GetBlockContentArgs
        A Pydantic model containing:
            auth (AccessTokenPayload):
                LMS + Studio URLs and the access token.
            course_id (str):
                Course key (e.g., "course-v1:ORG+COURSE+RUN").
            locator (str):
                Usage key of the XBlock to fetch (must be non-empty).

    Returns
    -------
    dict[str, Any]
        A dictionary containing:
            {"response": <normalized contentstore response>}
        OR
            {"error": "<details>"} when an LMS error occurs.
    """
    encoded_locator = quote(payload.locator, safe="")

    endpoint = f"api/contentstore/v0/xblock/{payload.course_id}/{encoded_locator}"

    async with OpenEdxClient(payload.auth.lms_url, payload.auth.access_token) as client:
        try:
            response = await client.get(payload.auth.studio_url, endpoint)

            return {"response": response}

        except LMSError as err:
            return {
                "error": {
                    "method": err.method,
                    "endpoint": err.url,
                    "status_code": err.status_code,
                    "message": err.message,
                }
            }
