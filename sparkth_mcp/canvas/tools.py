import json

from .client import CanvasClient
from ..server import mcp
from ..types import AuthenticationError
from .types import (
    AuthenticationPayload,
    CoursePayload,
    ListPagesRequest,
    ModuleItemParams,
    ModuleItemPayload,
    ModuleParams,
    ModulePayload,
    PagePayload,
    PageRequest,
    QuestionPayload,
    QuestionRequest,
    QuizPayload,
    QuizRequest,
    UpdateModuleItemPayload,
    UpdateModulePayload,
    UpdatePagePayload,
    UpdateQuestionPayload,
    UpdateQuizPayload,
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
    res = {}

    try:
        res = await CanvasClient.authenticate(api_url, api_token)
    except AuthenticationError as e:
        return {"status": e.status_code, "message": e.message}

    return {"status": res}


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

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
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

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
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

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (ModuleParams): Consist of auth (api_url, api_token), course_id and module_id
    """
    auth = params.auth
    course_id = params.course_id
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
async def canvas_delete_module(request: ModuleParams) -> json:
    """
    Delete a module specified in the request

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        request (ModuleParams): Consist of auth (api_url, api_token), course_id and module_id
    """
    auth = request.auth
    course_id = request.course_id
    module_id = request.module_id
    path = f"courses/{course_id}/modules/{module_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("DELETE", path)


@mcp.tool
async def canvas_list_module_items(request: ModuleParams) -> json:
    """
    List all module items in a specified module for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        request (ModuleParams): Consist of auth (api_url, api_token), course_id and module_id
    """
    auth = request.auth
    course_id = request.course_id
    module_id = request.module_id

    path = f"courses/{course_id}/modules/{module_id}/items"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", path)


@mcp.tool
async def canvas_get_module_item(request: ModuleItemParams) -> json:
    """
    List a single module item in a specified module for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        request (ModuleItemParams): Consist of auth (api_url, api_token), course_id, module_id and module_item_id
    """
    auth = request.auth
    course_id = request.course_id
    module_id = request.module_id
    module_item_id = request.module_item_id

    path = f"courses/{course_id}/modules/{module_id}/items/{module_item_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", path)


@mcp.tool
async def canvas_create_module_item(payload: ModuleItemPayload) -> json:
    """
    Create a module item in a specified module for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Only provide page_url if item type is "Page".

    Args:
        payload (ModuleItemPayload): Consist of auth (api_url, api_token), course_id, module_id and module item payload
    """
    auth = payload.auth
    course_id = payload.course_id
    module_id = payload.module_id

    path = f"courses/{course_id}/modules/{module_id}/items"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("POST", path, payload.model_dump())


@mcp.tool
async def canvas_update_module_item(payload: UpdateModuleItemPayload) -> json:
    """
    Update a specified module item for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (UpdateModuleItemPayload): Consist of auth (api_url, api_token), course_id, module_id, module_item_id and updated module item payload
    """
    auth = payload.auth
    course_id = payload.course_id
    module_id = payload.module_id
    item_id = payload.item_id

    path = f"courses/{course_id}/modules/{module_id}/items/{item_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("PUT", path, payload.model_dump())


@mcp.tool
async def canvas_delete_module_item(request: ModuleItemParams) -> json:
    """
    Delete a module item specified in the request

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        request (ModuleItemParams): Consist of auth (api_url, api_token), course_id, module_id and module_item_id
    """
    auth = request.auth
    course_id = request.course_id
    module_id = request.module_id
    module_item_id = request.module_item_id
    path = f"courses/{course_id}/modules/{module_id}/items/{module_item_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("DELETE", path)


@mcp.tool
async def canvas_list_pages(params: ListPagesRequest) -> json:
    """
    Retrieve all pages for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (ListPagesRequest): Consist of auth (api_url, api_token) and course_id
    """
    auth = params.auth
    course_id = params.course_id

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", f"courses/{course_id}/pages")


@mcp.tool
async def canvas_get_page(params: PageRequest) -> json:
    """
    Retrieve a page for a course by page_url

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (PageRequest): Consist of auth (api_url, api_token), course_id and page_url
    """
    auth = params.auth
    course_id = params.course_id
    page_url = params.page_url
    path = f"courses/{course_id}/pages/{page_url}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", path)


@mcp.tool
async def canvas_create_page(payload: PagePayload) -> json:
    """
    Create a page for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (PagePayload): Consist of auth (api_url, api_token), course_id and wiki_page payload
    """
    auth = payload.auth
    course_id = payload.course_id
    path = f"courses/{course_id}/pages"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("POST", path, payload.model_dump())


@mcp.tool
async def canvas_update_page(payload: UpdatePagePayload) -> json:
    """
    Update a page for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (UpdatePagePayload): Consist of auth (api_url, api_token), course_id and updated page details
    """
    auth = payload.auth
    course_id = payload.course_id
    page_url = payload.url_or_id
    path = f"courses/{course_id}/pages/{page_url}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("PUT", path, payload.model_dump())


@mcp.tool
async def canvas_delete_page(params: PageRequest) -> json:
    """
    Delete a page for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (PageRequest): Consist of auth (api_url, api_token), course_id and page url.
    """
    auth = params.auth
    course_id = params.course_id
    page_url = params.page_url
    path = f"courses/{course_id}/pages/{page_url}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("DELETE", path)


@mcp.tool
async def canvas_list_quizzes(auth: AuthenticationPayload, course_id: int) -> json:
    """
    List all quizzes for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        auth (AuthenticationPayload): Consist of api_url and api_token
        course_id (int): The course ID
    """
    path = f"courses/{course_id}/quizzes"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", path)


@mcp.tool
async def canvas_get_quizzes(params: QuizRequest) -> json:
    """
    Get a single quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuizRequest): Consist of auth (api_url, api_token), course_id and quiz_id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", path)


@mcp.tool
async def canvas_create_quiz(payload: QuizPayload) -> json:
    """
    Create a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (QuizPayload): Consist of auth (api_url, api_token), course_id and quiz payload
    """
    auth = payload.auth
    course_id = payload.course_id
    path = f"courses/{course_id}/quizzes"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("POST", path, payload.model_dump())


@mcp.tool
async def canvas_update_quiz(payload: UpdateQuizPayload) -> json:
    """
    Update a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (UpdateQuizPayload): Consist of auth (api_url, api_token), course_id and updated quiz details
    """
    auth = payload.auth
    course_id = payload.course_id
    quiz_id = payload.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("PUT", path, payload.model_dump())


@mcp.tool
async def canvas_delete_quiz(params: QuizRequest) -> json:
    """
    Delete a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuizRequest): Consist of auth (api_url, api_token), course_id and quiz id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("DELETE", path)


@mcp.tool
async def canvas_list_questions(request: QuizRequest) -> json:
    """
    List all questions in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        request (QuizRequest): Consist of auth (api_url and api_token), course_id and quiz_id
    """
    auth = request.auth
    course_id = request.course_id
    quiz_id = request.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", path)


@mcp.tool
async def canvas_get_question(params: QuestionRequest) -> json:
    """
    Get a single question of a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuestionRequest): Consist of auth (api_url, api_token), course_id, quiz_id and question_id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    question_id = params.question_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("GET", path)


@mcp.tool
async def canvas_create_question(payload: QuestionPayload) -> json:
    """
    Create a question in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (QuizPayload): Consist of auth (api_url, api_token), course_id, quiz_id and question payload
    """
    auth = payload.auth
    course_id = payload.course_id
    quiz_id = payload.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("POST", path, payload.model_dump())


@mcp.tool
async def canvas_update_question(payload: UpdateQuestionPayload) -> json:
    """
    Update a question in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (UpdateQuestionPayload): Consist of auth (api_url, api_token), course_id, quiz_id and updated question details
    """
    auth = payload.auth
    course_id = payload.course_id
    quiz_id = payload.quiz_id
    question_id = payload.question_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("PUT", path, payload.model_dump())


@mcp.tool
async def canvas_delete_question(params: QuestionRequest) -> json:
    """
    Delete a question in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuestionRequest): Consist of auth (api_url, api_token), course_id, quiz_id and question_id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    question_id = params.question_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    return await canvas_client.request_bearer("DELETE", path)
