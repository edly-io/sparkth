import urllib
from typing import Any, Optional
from urllib.parse import quote

from app.core_plugins.openedx.client import OpenEdxClient
from app.core_plugins.openedx.config import OpenEdxConfig
from app.core_plugins.openedx.types import (
    AccessTokenPayload,
    Component,
    LMSAccess,
    RefreshTokenPayload,
    TokenResponse,
    openedx_settings,
)
from app.mcp.types import AuthenticationError, JsonParseError, LMSError
from app.plugins.base import SparkthPlugin, tool


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


class OpenEdxPlugin(SparkthPlugin):
    """
    Open edX Integration Plugin

    Provides comprehensive Open edX API integration with MCP tools for:
    - Authentication and credential validation
    - Course CRUD operations
    - Section and subsection management
    - Unit, Problem and HTML Component Management

    Tools are auto-registered via @tool decorator using metaclass magic!
    """

    def __init__(self, plugin_name: str) -> None:
        super().__init__(
            plugin_name,
            OpenEdxConfig,
            is_core=True,
            version="1.0.0",
            description="Open edX integration with MCP tools",
            author="Sparkth Team",
        )

    @tool(description="Authenticate the Openedx credentials", category="openedx-auth")
    async def openedx_authenticate(self) -> dict[str, Any]:
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
        lms_url = openedx_settings.lms_url
        studio_url = openedx_settings.studio_url
        username = openedx_settings.lms_username
        password = openedx_settings.lms_password

        async with OpenEdxClient(lms_url) as client:
            try:
                auth_json = await client.get_token(username, password)
                token_response = TokenResponse(**auth_json)
                who = client.get_username() or username

                return {
                    "access_token": token_response.access_token,
                    "refresh_token": token_response.refresh_token,
                    "studio_url": studio_url,
                    "message": f"Successfully authenticated as {who}",
                }

            except AuthenticationError as err:
                return {
                    "error": {
                        "status_code": err.status_code,
                        "message": f"Open edX authentication failed: {err.message}",
                    }
                }

    @tool(description="Refresh the Open edX access token using the provided refresh token.", category="openedx-auth")
    async def openedx_refresh_access_token(self, payload: RefreshTokenPayload) -> dict[str, Any]:
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
        lms_url = payload.lms_url or openedx_settings.lms_url
        studio_url = payload.studio_url or openedx_settings.studio_url
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

    @tool(description="Retrieve authenticated user information from an Open edX LMS instance.", category="openedx-user")
    async def openedx_get_user_info(self, payload: LMSAccess) -> dict[str, Any]:
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
        lms_url = payload.lms_url or openedx_settings.lms_url
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

    @tool(description="Create a new course run in an Open edX Studio instance.", category="openedx-course")
    async def openedx_create_course_run(
        self,
        org: str,
        number: str,
        run: str,
        title: str,
        pacing_type: str,
        access_token: str,
        # lms_url: str | None = None,
        # studio_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new course run in an Open edX Studio instance.

        Args:
            payload (CreateCourseArgs):
                An object containing:
                    - lms_url (str): Base LMS URL.
                    - studio_url (str): Base Studio URL for POST requests.
                    - access_token (str): Token used to authenticate requests.
                    - org (str): Organization identifier.
                    - number (str): Course number.
                    - run (str): Course run identifier.
                    - title (str): Course title.
                    - pacing_type (str): Course pacing type (e.g., "self_paced" or "instructor_paced").

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
        lms_url = openedx_settings.lms_url
        studio_url = openedx_settings.studio_url

        # Reconstruct course data from flat fields
        course_data = {
            "org": org,
            "number": number,
            "run": run,
            "title": title,
            "pacing_type": pacing_type,
        }
        endpoint = "api/v1/course_runs/"

        async with OpenEdxClient(lms_url, access_token) as client:
            try:
                res = await client.post(studio_url, endpoint, course_data)
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

    @tool(description="Retrieve a paginated list of course runs from open edX studio.", category="openedx-course")
    async def openedx_list_course_runs(
        self,
        access_token: str,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        # lms_url: str | None = None,
        # studio_url: str | None = None,
    ) -> dict[str, Any]:
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
        lms_url = openedx_settings.lms_url
        studio_url = openedx_settings.studio_url

        lms = lms_url.rstrip("/")
        base_url = studio_url.rstrip("/")
        page = page or 1
        page_size = page_size or 20
        endpoint = f"api/v1/course_runs/?page={page}&page_size={page_size}"

        async with OpenEdxClient(lms, access_token) as client:
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

    @tool(description="Create a new XBlock within an Open edX course.", category="openedx-course")
    async def openedx_create_xblock(
        self,
        access_token: str,
        course_id: str,
        parent_locator: str,
        category: str,
        display_name: str,
        # lms_url: str | None = None,
        # studio_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new XBlock within an Open edX course.

        Args:
            payload (XBlockPayload):
                An object containing:
                    - lms_url (str): LMS base URL.
                    - studio_url (str): Studio base URL for API calls.
                    - access_token (str): Token used for authenticated requests.
                    - course_id (str): The course identifier where the XBlock should be created.
                    - parent_locator (str): The parent XBlock locator.
                    - category (str): The XBlock category/type.
                    - display_name (str): The display name for the XBlock.

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
        lms_url = openedx_settings.lms_url
        studio_url = openedx_settings.studio_url

        # Reconstruct xblock data from flat fields
        xblock_data = {
            "parent_locator": parent_locator,
            "category": category,
            "display_name": display_name,
        }
        course_id = course_id
        endpoint = f"api/contentstore/v0/xblock/{course_id}"

        async with OpenEdxClient(lms_url, access_token) as client:
            try:
                res = await client.post(
                    studio_url,
                    endpoint,
                    xblock_data,
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

    @tool(description="Create a Problem or HTML XBlock component in a course.", category="openedx-course")
    async def openedx_create_problem_or_html(
        self,
        access_token: str,
        course_id: str,
        unit_locator: str,
        kind: Optional[Component] = None,
        display_name: Optional[str] = None,
        data: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        mcq_boilerplate: Optional[bool] = None,
        # lms_url: str | None = None,
        # studio_url: str | None = None,
    ) -> dict[str, Any]:
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
                access_token (str): Token used for authenticated requests.
                lms_url (str): LMS base URL.
                studio_url (str): Studio base URL for API calls.
                course_id (str): The course identifier.
                unit_locator (str): The unit locator where the component should be created.
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
        lms_url = openedx_settings.lms_url
        studio_url = openedx_settings.studio_url

        # Create AccessTokenPayload from flat fields for helper functions
        auth = AccessTokenPayload(
            access_token=access_token,
            lms_url=lms_url,
            studio_url=studio_url,
        )
        course_id = course_id
        unit_locator = unit_locator
        kind = kind
        display_name = display_name
        data = data
        metadata = metadata
        mcq_boilerplate = mcq_boilerplate

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

    @tool(
        description="Update an XBlock (chapter/section, sequential/subsection, or vertical/unit) in a course.",
        category="openedx-course",
    )
    async def openedx_update_xblock(
        self,
        access_token: str,
        course_id: str,
        locator: str,
        data: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        # lms_url: str | None = None,
        # studio_url: str | None = None,
    ) -> dict[str, Any]:
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
                access_token (str): Token used for authenticated requests.
                lms_url (str): LMS base URL.
                studio_url (str): Studio base URL for API calls.
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
        lms_url = openedx_settings.lms_url
        studio_url = openedx_settings.studio_url

        # Create AccessTokenPayload from flat fields for helper function
        auth = AccessTokenPayload(
            access_token=access_token,
            lms_url=lms_url,
            studio_url=studio_url,
        )

        try:
            response = await openedx_update_xblock_content(
                auth,
                course_id,
                locator,
                data,
                metadata,
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

    @tool(description="Fetch the full block graph (course tree) for a course.", category="openedx-course-tree")
    async def openedx_get_course_tree_raw(
        self, access_token: str, course_id: str,
        # lms_url: str | None = None,
        # studio_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch the full block graph ("course tree") for a course using the
        Open edX Course Blocks API.

        This returns raw block metadata including display names, block types,
        children lists, scheduling fields, URLs, and other structural information.

        API endpoint:
            GET /api/courses/v1/blocks/

        Parameters
        ----------
        access_token (str): Token used for authenticated requests.
        lms_url (str): LMS base URL.
        studio_url (str): Studio base URL.
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
        lms_url = openedx_settings.lms_url

        params = {
            "course_id": course_id,
            "depth": "all",
            "all_blocks": "true",
            "requested_fields": ("children,display_name,type,graded,student_view_url,block_id,due,start,format"),
        }

        async with OpenEdxClient(
            lms_url,
            access_token,
        ) as client:
            try:
                response = await client.get(
                    lms_url,
                    'api/courses/v1/blocks/',
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

    @tool(
        description="Read the content of a specific XBlock directly from the **Studio ContentStore**.",
        category="openedx-content-store",
    )
    async def openedx_get_block_contentstore(
        self,
        access_token: str,
        course_id: str,
        locator: str,
        # lms_url: str | None = None,
        # studio_url: str | None = None,
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
        payload : BlockContentArgs
            A Pydantic model containing:
                access_token (str): Token used for authenticated requests.
                lms_url (str): LMS base URL.
                studio_url (str): Studio base URL.
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
        lms_url = openedx_settings.lms_url
        studio_url = openedx_settings.studio_url

        encoded_locator = quote(locator, safe="")

        endpoint = f"api/contentstore/v0/xblock/{course_id}/{encoded_locator}"

        async with OpenEdxClient(lms_url, access_token) as client:
            try:
                response = await client.get(studio_url, endpoint)

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
            