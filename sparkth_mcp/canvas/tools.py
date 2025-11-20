import json

from .client import CanvasClient
from ..server import mcp
from ..types import AuthenticationError
from .types import (
    AuthenticationPayload,
    CoursePayload,
    ModuleParams,
    ModulePayload,
    UpdateModulePayload,
)


@mcp.tool
async def canvas_authenticate(api_url: str, api_token: str) -> json:
    """
    Authenticate the provided Canvas API URL and token.
    If either argument is missing, the client must supply it. Default values for required fields are never assumed.

    Args:
        api_url (str): The Canvas API base URL (e.g. https://canvas.instructure.com/api/v1/).
        api_token (str): The user's Canvas API token used for authentication.
    """
    try:
        res = await CanvasClient.authenticate(api_url, api_token)
        if res:
            return {"authenticated": True, "message": "Authentication successful."}

    except AuthenticationError:
        return {"authenticated": False, "message": "Invalid API token or URL."}

    return {
        "authenticated": False,
        "message": "Authentication failed for unknown reasons.",
    }


@mcp.tool
async def canvas_get_courses(api_url: str, api_token: str) -> json:
    """
    Retrieve all courses for the user.

    If either argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the course list.

    Args:
        api_url (str): The Canvas API base URL (e.g., https://canvas.instructure.com/api/v1/).
        api_token (str): The user's Canvas API token used for authentication.
    """
    canvas_client = CanvasClient(api_url, api_token)
    return await canvas_client.request_bearer("GET", "courses")


@mcp.tool
async def canvas_get_course(api_url: str, api_token: str, course_id) -> json:
    """
    Retrieve a single course for the user by course_id.

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the course list.

    Args:
        api_url (str): The Canvas API base URL (e.g., https://canvas.instructure.com/api/v1/).
        api_token (str): The user's Canvas API token used for authentication.
        course_id (int): The id for the course to be retrieved
    """
    canvas_client = CanvasClient(api_url, api_token)
    return await canvas_client.request_bearer("GET", f"courses/{course_id}")


@mcp.tool
async def canvas_create_course(payload: CoursePayload) -> json:
    """
    Create a new course on Canvas.

    If any argument is missing, the client must provide it. Default values for required fields are never assumed..
    If the credentials have not already been authenticated, they must be validated before
    retrieving the course list.

    Args:
        api_url (str): The Canvas API base URL (e.g., https://canvas.instructure.com/api/v1/).
        api_token (str): The user's Canvas API token used for authentication.
        payload (CoursePayload): The payload to create a course
    """

    api_url = payload.auth.api_url
    api_token = payload.auth.api_token

    client = CanvasClient(api_url, api_token)
    account_id = payload.account_id
    path = f"accounts/{account_id}/courses"

    response = await client.request_bearer(
        "POST",
        path,
        payload.model_dump(),
    )

    return {
        "success": True,
        "course": response,
    }


@mcp.tool
async def canvas_list_modules(auth: AuthenticationPayload, course_id: int) -> json:
    """
    Retrieve all modules for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed..
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        auth (AuthenticationPayload): The api_url and api_token needed for authentication
        course_id (int): The id for the course whose modules are to be retrieved
    """
    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", f"courses/{course_id}/modules")


@mcp.tool
async def canvas_list_module(params: ModuleParams) -> json:
    """
    Retrieve a single module for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed..
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (ModuleParams): Consist of auth (api_url, api_token), course_id and module_id
    """
    auth = params.auth
    course_id = (params.course_id,)
    module_id = params.module_id

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer(
        "GET", f"courses/{course_id}/modules/{module_id}"
    )


@mcp.tool
async def canvas_create_module(payload: ModulePayload) -> json:
    """
    Create a module for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (ModulePayload): Consist of auth (api_url, api_token), course_id and module
        (name, position, unlock_at, require_sequential_progress, prerequisite_module_ids, publish_final_grade)
    """
    auth = payload.auth
    course_id = payload.course_id
    path = f"courses/{course_id}/modules"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("POST", path, payload.model_dump())


@mcp.tool
async def canvas_update_module(payload: UpdateModulePayload) -> json:
    """
    Update a module of a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (UpdateModulePayload): The payload for updating a module
    """
    auth = payload.auth
    course_id = payload.course_id
    module_id = payload.module_id
    path = f"courses/{course_id}/modules/{module_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("PUT", path, payload.model_dump())


@mcp.tool
async def canvas_delete_module(payload: ModuleParams) -> json:
    """
    Deelete a module specified in the module

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (ModuleParams): Consist of auth (api_url, api_token), course_id and module_id
    """
    auth = payload.auth
    course_id = payload.course_id
    path = f"courses/{course_id}/modules"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("DELETE", path)
