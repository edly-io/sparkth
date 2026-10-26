"""
Canvas MCP tools, including:
- LMS vocabulary (about)
- Settings check
- Course management
- Module management
- Module items management
- Page management
- Quiz and question management
"""

from pathlib import Path
from typing import Any

from sparkth.lib.enums import Method
from sparkth.lib.exceptions import AuthenticationError, LMSRequestError
from sparkth.lib.plugins import load_user_plugin_config
from sparkth.plugins.canvas.client import CanvasClient
from sparkth.plugins.canvas.config import CanvasConfig
from sparkth.plugins.canvas.constants import CANVAS_PLUGIN_NAME
from sparkth.plugins.canvas.schemas import (
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


def _lms_error(e: LMSRequestError | AuthenticationError | ValueError) -> dict[str, Any]:
    """The tool error dict for a failed Canvas call. A malformed response carries no status code."""
    if isinstance(e, ValueError):
        return {"error": {"message": str(e)}}
    return {"error": {"status_code": e.status_code, "message": e.message}}


async def _canvas_call(method: Method, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make one Canvas request with the caller's stored settings, and return the object it answers.

    Every tool that is a single request goes through here, so the settings load and the error
    shape live in one place. A failed request returns the tool error dict; missing settings raise.
    """
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            return await client.request(method, path, payload)
    except (LMSRequestError, AuthenticationError, ValueError) as e:
        return _lms_error(e)


async def _canvas_list(path: str, key: str) -> dict[str, Any]:
    """Fetch a Canvas list with the caller's stored settings, and return it under ``key``.

    The list counterpart of ``_canvas_call``: a failed request returns the tool error dict.
    """
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            return {key: await client.get_all(path)}
    except (LMSRequestError, AuthenticationError, ValueError) as e:
        return _lms_error(e)


async def canvas_check_settings() -> dict[str, Any]:
    """Check that the user's stored Canvas settings work.

    Call this to learn whether Canvas is set up for the user. Never ask the user for their Canvas
    credentials, and never accept them in the chat.
    """
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            res = await client.authenticate()
        return {"status": res}
    except AuthenticationError as e:
        return _lms_error(e)


async def canvas_get_courses(page: int) -> dict[str, Any]:
    """Retrieve a paginated list of courses for the user."""
    return await _canvas_list(f"courses?page={page}", "courses")


async def canvas_get_course(params: CourseParams) -> dict[str, Any]:
    """Retrieve a single course for the user by course_id."""
    return await _canvas_call(Method.GET, f"courses/{params.course_id}")


async def canvas_create_course(payload: CoursePayload) -> dict[str, Any]:
    """Create a new course on Canvas."""
    return await _canvas_call(Method.POST, f"accounts/{payload.account_id}/courses", payload.model_dump())


async def canvas_list_modules(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of modules for a course."""
    page = getattr(params, "page", 1)
    return await _canvas_list(f"courses/{params.course_id}/modules?page={page}", "modules")


async def canvas_get_module(params: ModuleParams) -> dict[str, Any]:
    """Retrieve a single module for a course."""
    return await _canvas_call(Method.GET, f"courses/{params.course_id}/modules/{params.module_id}")


async def canvas_create_module(payload: ModulePayload) -> dict[str, Any]:
    """Create a module for a course."""
    return await _canvas_call(Method.POST, f"courses/{payload.course_id}/modules", payload.model_dump())


async def canvas_update_module(payload: UpdateModulePayload) -> dict[str, Any]:
    """Update a module of a course."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}"
    return await _canvas_call(Method.PUT, path, payload.model_dump())


async def canvas_delete_module(params: ModuleParams) -> dict[str, Any]:
    """Delete a module from a course."""
    return await _canvas_call(Method.DELETE, f"courses/{params.course_id}/modules/{params.module_id}")


async def canvas_list_module_items(params: ModuleParams) -> dict[str, Any]:
    """Retrieve a paginated list of module items in a module."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items?page={params.page}"
    return await _canvas_list(path, "items")


async def canvas_get_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """Retrieve a single module item."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
    return await _canvas_call(Method.GET, path)


async def canvas_create_module_item(payload: ModuleItemPayload) -> dict[str, Any]:
    """Create a module item in a module."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}/items"
    return await _canvas_call(Method.POST, path, payload.model_dump())


async def canvas_update_module_item(payload: UpdateModuleItemPayload) -> dict[str, Any]:
    """Update a module item."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}/items/{payload.item_id}"
    return await _canvas_call(Method.PUT, path, payload.model_dump())


async def canvas_delete_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """Delete a module item."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
    return await _canvas_call(Method.DELETE, path)


async def canvas_list_pages(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of pages for a course."""
    page = getattr(params, "page", 1)
    return await _canvas_list(f"courses/{params.course_id}/pages?page={page}", "pages")


async def canvas_get_page(params: PageRequest) -> dict[str, Any]:
    """Retrieve a page for a course by page_url."""
    return await _canvas_call(Method.GET, f"courses/{params.course_id}/pages/{params.page_url}")


async def canvas_create_page(payload: PagePayload) -> dict[str, Any]:
    """Create a page for a course."""
    return await _canvas_call(Method.POST, f"courses/{payload.course_id}/pages", payload.model_dump())


async def canvas_update_page(payload: UpdatePagePayload) -> dict[str, Any]:
    """Update a page for a course."""
    path = f"courses/{payload.course_id}/pages/{payload.url_or_id}"
    return await _canvas_call(Method.PUT, path, payload.model_dump())


async def canvas_delete_page(params: PageRequest) -> dict[str, Any]:
    """Delete a page for a course."""
    return await _canvas_call(Method.DELETE, f"courses/{params.course_id}/pages/{params.page_url}")


async def canvas_list_quizzes(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of quizzes for a course."""
    page = getattr(params, "page", 1)
    return await _canvas_list(f"courses/{params.course_id}/quizzes?page={page}", "quizzes")


async def canvas_get_quiz(params: QuizParams) -> dict[str, Any]:
    """Get a single quiz for a course."""
    return await _canvas_call(Method.GET, f"courses/{params.course_id}/quizzes/{params.quiz_id}")


async def canvas_create_quiz(payload: QuizPayload) -> dict[str, Any]:
    """Create a quiz for a course."""
    return await _canvas_call(Method.POST, f"courses/{payload.course_id}/quizzes", payload.model_dump())


async def canvas_update_quiz(payload: UpdateQuizPayload) -> dict[str, Any]:
    """Update a quiz for a course."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}"
    return await _canvas_call(Method.PUT, path, payload.model_dump())


async def canvas_delete_quiz(params: QuizParams) -> dict[str, Any]:
    """Delete a quiz for a course."""
    return await _canvas_call(Method.DELETE, f"courses/{params.course_id}/quizzes/{params.quiz_id}")


async def canvas_list_questions(params: QuizParams) -> dict[str, Any]:
    """Retrieve a paginated list of questions in a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions?page={params.page}"
    return await _canvas_list(path, "questions")


async def canvas_get_question(params: QuestionParams) -> dict[str, Any]:
    """Get a single question of a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
    return await _canvas_call(Method.GET, path)


async def canvas_create_question(payload: QuestionPayload) -> dict[str, Any]:
    """Create a question in a quiz."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions"
    return await _canvas_call(Method.POST, path, payload.model_dump())


async def canvas_update_question(payload: UpdateQuestionPayload) -> dict[str, Any]:
    """Update a question in a quiz."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions/{payload.question_id}"
    return await _canvas_call(Method.PUT, path, payload.model_dump())


async def canvas_delete_question(params: QuestionParams) -> dict[str, Any]:
    """Delete a question in a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
    return await _canvas_call(Method.DELETE, path)


async def canvas_about() -> dict[str, Any]:
    """Explain Canvas's vocabulary, course structure and what "publish" means in Canvas.

    Read this before creating, changing or publishing Canvas content, or when a Canvas
    term is ambiguous.
    """
    return {"about": (Path(__file__).parent / "assets" / "about.txt").read_text(encoding="utf-8")}
