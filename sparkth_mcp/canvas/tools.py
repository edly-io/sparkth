from typing import Any, Dict

from sparkth_mcp.canvas.client import CanvasClient
from sparkth_mcp.server import mcp
from sparkth_mcp.types import AuthenticationError
from sparkth_mcp.canvas.types import (
    AuthenticationPayload,
    CourseParams,
    CoursePayload,
    ModuleItemParams,
    ModuleItemPayload,
    ModuleParams,
    ModulePayload,
    PagePayload,
    PageRequest,
    QuestionPayload,
    QuestionParams,
    QuizPayload,
    QuizParams,
    UpdateModuleItemPayload,
    UpdateModulePayload,
    UpdatePagePayload,
    UpdateQuestionPayload,
    UpdateQuizPayload,
)


@mcp.tool
async def canvas_authenticate(auth: AuthenticationPayload) -> Dict[str, Any]:
    """
    Authenticate the provided Canvas API URL and token.
    If either argument is missing, the client must supply it. Default values for required fields are never assumed.

    Args:
        payload (AuthenticationPayload): The credentials required for authentication. Include:
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
async def canvas_get_courses(params: AuthenticationPayload, page: int) -> Dict[str, Any]:
    """
    Retrieve a paginated list of courses for the user.

    If either argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the course list.

    Args:
        params (AuthenticationPayload): The credentials required for authentication. Include:
            api_url (str): The Canvas API base URL (e.g., https://canvas.instructure.com/api/v1/).
            api_token (str): The user's Canvas API token used for authentication.
    """
    canvas_client = CanvasClient(params.api_url, params.api_token)
    try:
        courses = await canvas_client.get(f"courses?page={page}")
    finally:
        await canvas_client.close()

    return {"courses": courses}


@mcp.tool
async def canvas_get_course(params: CourseParams) -> Dict[str, Any]:
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
    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        result = await canvas_client.get(f"courses/{params.course_id}")
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_create_course(payload: CoursePayload) -> Dict[str, Any]:
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

    client = CanvasClient(api_url, api_token)
    account_id = payload.account_id
    path = f"accounts/{account_id}/courses"

    try:
        result = await client.post(
            path,
            payload.model_dump(),
        )
    finally:
        await client.close()

    return result


@mcp.tool
async def canvas_list_modules(params: CourseParams) -> Dict[str, Any]:
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
    canvas_client = CanvasClient(auth.api_url, auth.api_token)

    try:
        modules = await canvas_client.get(f"courses/{params.course_id}/modules?page={params.page}")
    finally:
        await canvas_client.close()

    return {"modules": modules}


@mcp.tool
async def canvas_gets_module(params: ModuleParams) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.get(f"courses/{course_id}/modules/{module_id}")
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_create_module(payload: ModulePayload) -> Dict[str, Any]:
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

    try:
        result = await canvas_client.post(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_update_module(payload: UpdateModulePayload) -> Dict[str, Any]:
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

    try:
        result = await canvas_client.put(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_delete_module(params: ModuleParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        result = await canvas_client.delete(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_list_module_items(params: ModuleParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)

    try:
        result = await canvas_client.get(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_get_module_item(params: ModuleItemParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)

    try:
        result = await canvas_client.get(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_create_module_item(payload: ModuleItemPayload) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.post(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_update_module_item(payload: UpdateModuleItemPayload) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.put(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_delete_module_item(params: ModuleItemParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        result = await canvas_client.delete(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_list_pages(params: CourseParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        result = await canvas_client.get(f"courses/{course_id}/pages?page={page}")

    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_get_page(params: PageRequest) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.get(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_create_page(payload: PagePayload) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.post(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_update_page(payload: UpdatePagePayload) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.put(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_delete_page(params: PageRequest) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.delete(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_list_quizzes(params: CourseParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        quizzes = await canvas_client.get(path)
    finally:
        await canvas_client.close()

    return {"quizzes": quizzes}


@mcp.tool
async def canvas_get_quiz(params: QuizParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        result = await canvas_client.get(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_create_quiz(payload: QuizPayload) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.post(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_update_quiz(payload: UpdateQuizPayload) -> Dict[str, Any]:
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
    try:
        result = await canvas_client.put(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_delete_quiz(params: QuizParams) -> Dict[str, Any]:
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

    try:
        result = await canvas_client.delete(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_list_questions(params: QuizParams) -> Dict[str, Any]:
    """
    Retrieve a paginated list of questions in a quiz for a course

    If any argument is missing, the client must provide it. Default values for required fields are never assumed.
    If the credentials have not already been authenticated, they must be validated before
    retrieving the modules list.

    Args:
        params (QuizRequest): Consist of auth (api_url and api_token), course_id, quiz_id and page index
    """
    auth = params.auth
    course_id = params.course_id
    quiz_id = params.quiz_id
    page = params.page
    path = f"courses/{course_id}/quizzes/{quiz_id}/questions?page={page}"

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        questions = await canvas_client.get(path)
    finally:
        await canvas_client.close()

    return {"questions": questions}


@mcp.tool
async def canvas_get_question(params: QuestionParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        result = await canvas_client.get(path)
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_create_question(payload: QuestionPayload) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)

    try:
        result = await canvas_client.post(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_update_question(payload: UpdateQuestionPayload) -> Dict[str, Any]:
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

    try:
        result = await canvas_client.put(path, payload.model_dump())
    finally:
        await canvas_client.close()

    return result


@mcp.tool
async def canvas_delete_question(params: QuestionParams) -> Dict[str, Any]:
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

    canvas_client = CanvasClient(auth.api_url, auth.api_token)
    try:
        result = await canvas_client.delete(path)
    finally:
        await canvas_client.close()

    return result
