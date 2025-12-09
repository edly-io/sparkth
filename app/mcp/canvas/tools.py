from typing import Any

from app.mcp.canvas.client import CanvasClient
from app.mcp.canvas.types import (
    AuthenticationPayload,
    CourseParams,
    CoursePayload,
    ModuleItemParams,
    ModuleItemPayload,
    ModuleParams,
    ModulePayload,
    PagePayload,
    PageRequest,
    QuestionParams,
    QuestionPayload,
    QuizParams,
    QuizPayload,
    UpdateModuleItemPayload,
    UpdateModulePayload,
    UpdatePagePayload,
    UpdateQuestionPayload,
    UpdateQuizPayload,
)
from app.mcp.server import mcp
from app.mcp.types import AuthenticationError


@mcp.tool
async def canvas_authenticate(auth: AuthenticationPayload) -> dict[str, Any]:
    """
    Authenticate the provided Canvas API URL and token.
    If either argument is missing, the client must supply it. Default values for required fields are never assumed.

    Args:
        auth (AuthenticationPayload): The credentials required for authentication. Include:
            api_url (str): The Canvas API base URL (e.g. https://canvas.instructure.com/api/v1/).
            api_token (str): The user's Canvas API token used for authentication.
    """
    res = {}

    try:
        res = await CanvasClient.authenticate(auth.api_url, auth.api_token)
    except AuthenticationError as e:
        return {"status": e.status_code, "message": e.message}

    return {"status": res}


@mcp.tool
async def canvas_get_courses(auth: AuthenticationPayload, page: int) -> dict[str, Any]:
    """
    Retrieve a paginated list of courses for the user.

    If either argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the course list.

    Args:
        auth (AuthenticationPayload): The credentials required for authentication. Include:
            api_url (str): The Canvas API base URL (e.g., https://canvas.instructure.com/api/v1/).
            api_token (str): The user's Canvas API token used for authentication.
    """
    async with CanvasClient(auth.api_url, auth.api_token) as client:
        courses = await client.get(f"courses?page={page}")

    return {"courses": courses}


@mcp.tool
async def canvas_get_course(params: CourseParams) -> dict[str, Any]:
    """
    Retrieve a single course for the user by course_id.

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the course list.

    Args:
        params (CourseParams): The parameters to fetch a course. Consist of:
            auth (AuthenticationPayload): The credentials required for authentication, i.e., api_url and api_token.
            course_id (int): The id for the course to be retrieved
    """
    auth = params.auth
    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(f"courses/{params.course_id}")

    return result


@mcp.tool
async def canvas_create_course(payload: CoursePayload) -> dict[str, Any]:
    """
    Create a new course on Canvas.

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the course list.

    Args:
        payload (CoursePayload): The payload to create a course
    """

    api_url = payload.auth.api_url
    api_token = payload.auth.api_token
    account_id = payload.account_id
    path = f"accounts/{account_id}/courses"

    async with CanvasClient(api_url, api_token) as client:
        result = await client.post(
            path,
            payload.model_dump(),
        )

    return result


@mcp.tool
async def canvas_list_modules(params: CourseParams) -> dict[str, Any]:
    """
    Retrieve a paginated list of modules for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
         params (CourseParams): The parameters for the couse whose modules are to be fetched. Consist of:
            auth (AuthenticationPayload): The credentials required for authentication, i.e., api_url and api_token.
            course_id (int): The id for the course whose modules are to be fetched
            page (int): The page index
    """
    auth = params.auth
    async with CanvasClient(auth.api_url, auth.api_token) as client:
        modules = await client.get(f"courses/{params.course_id}/modules?page={params.page}")

    return {"modules": modules}


@mcp.tool
async def canvas_get_module(params: ModuleParams) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(f"courses/{course_id}/modules/{module_id}")

    return result


@mcp.tool
async def canvas_create_module(payload: ModulePayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.post(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_update_module(payload: UpdateModulePayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.put(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_delete_module(params: ModuleParams) -> dict[str, Any]:
    """
    Delete a module specified in the params.

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (ModuleParams): Consist of auth (api_url, api_token), course_id and module_id
    """
    auth = params.auth
    course_id = params.course_id
    module_id = params.module_id
    path = f"courses/{course_id}/modules/{module_id}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.delete(path)

    return result


@mcp.tool
async def canvas_list_module_items(params: ModuleParams) -> dict[str, Any]:
    """
    Retrieve a paginated list of module items in a specified module for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (ModuleParams): Consist of auth (api_url, api_token), course_id, module_id and page index
    """
    auth = params.auth
    course_id = params.course_id
    module_id = params.module_id
    page = params.page

    path = f"courses/{course_id}/modules/{module_id}/items?page={page}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(path)

    return result


@mcp.tool
async def canvas_get_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """
    List a single module item in a specified module for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (ModuleItemParams): Consist of auth (api_url, api_token), course_id, module_id and module_item_id
    """
    auth = params.auth
    course_id = params.course_id
    module_id = params.module_id
    module_item_id = params.module_item_id

    path = f"courses/{course_id}/modules/{module_id}/items/{module_item_id}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(path)

    return result


@mcp.tool
async def canvas_create_module_item(payload: ModuleItemPayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.post(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_update_module_item(payload: UpdateModuleItemPayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.put(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_delete_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """
    Delete a module item specified in the params.

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (ModuleItemParams): Consist of auth (api_url, api_token), course_id, module_id and module_item_id
    """
    auth = params.auth
    course_id = params.course_id
    module_id = params.module_id
    module_item_id = params.module_item_id
    path = f"courses/{course_id}/modules/{module_id}/items/{module_item_id}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.delete(path)

    return result


@mcp.tool
async def canvas_list_pages(params: CourseParams) -> dict[str, Any]:
    """
    Retrieve a paginated list of pages for a course.

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (CourseParams): Consist of auth (api_url, api_token), course_id and page index
    """
    auth = params.auth
    course_id = params.course_id
    page = params.page

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(f"courses/{course_id}/pages?page={page}")

    return result


@mcp.tool
async def canvas_get_page(params: PageRequest) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(path)

    return result


@mcp.tool
async def canvas_create_page(payload: PagePayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.post(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_update_page(payload: UpdatePagePayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.put(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_delete_page(params: PageRequest) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.delete(path)

    return result


@mcp.tool
async def canvas_list_quizzes(params: CourseParams) -> dict[str, Any]:
    """
    Retrieve a paginated list of quizzes for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (CourseParams): The params for the request, consist of
            auth (AuthenticationPayload): Consist of api_url and api_token
            course_id (int): The course ID
            page (int): The page index

    """
    auth = params.auth
    path = f"courses/{params.course_id}/quizzes?page={params.page}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        quizzes = await client.get(path)

    return {"quizzes": quizzes}


@mcp.tool
async def canvas_get_quiz(params: QuizParams) -> dict[str, Any]:
    """
    Get a single quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuizParams): Consist of auth (api_url, api_token), course_id and quiz_id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(path)

    return result


@mcp.tool
async def canvas_create_quiz(payload: QuizPayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.post(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_update_quiz(payload: UpdateQuizPayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.put(path, payload.model_dump())
    return result


@mcp.tool
async def canvas_delete_quiz(params: QuizParams) -> dict[str, Any]:
    """
    Delete a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuizParams): Consist of auth (api_url, api_token), course_id and quiz id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.delete(path)

    return result


@mcp.tool
async def canvas_list_questions(params: QuizParams) -> dict[str, Any]:
    """
    Retrieve a paginated list of questions in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuizParams): Consist of auth (api_url and api_token), course_id, quiz_id and page index
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    page = params.page
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions?page={page}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        questions = await client.get(path)

    return {"questions": questions}


@mcp.tool
async def canvas_get_question(params: QuestionParams) -> dict[str, Any]:
    """
    Get a single question of a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuestionParams): Consist of auth (api_url, api_token), course_id, quiz_id and question_id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    question_id = params.question_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.get(path)

    return result


@mcp.tool
async def canvas_create_question(payload: QuestionPayload) -> dict[str, Any]:
    """
    Create a question in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        payload (QuestionPayload): Consist of auth (api_url, api_token), course_id, quiz_id and question payload
    """
    auth = payload.auth
    course_id = payload.course_id
    quiz_id = payload.quiz_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.post(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_update_question(payload: UpdateQuestionPayload) -> dict[str, Any]:
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

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.put(path, payload.model_dump())

    return result


@mcp.tool
async def canvas_delete_question(params: QuestionParams) -> dict[str, Any]:
    """
    Delete a question in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuestionParams): Consist of auth (api_url, api_token), course_id, quiz_id and question_id.
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    question_id = params.question_id
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions/{question_id}"

    async with CanvasClient(auth.api_url, auth.api_token) as client:
        result = await client.delete(path)

    return result
