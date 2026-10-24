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


def _lms_error(e: LMSRequestError | AuthenticationError) -> dict[str, Any]:
    return {"error": {"status_code": e.status_code, "message": e.message}}


async def canvas_authenticate() -> dict[str, Any]:
    """Check that the user's stored Canvas settings work.

    Call this to learn whether Canvas is set up for the user.
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
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            courses = await client.get_all(f"courses?page={page}")
        return {"courses": courses}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_get_course(params: CourseParams) -> dict[str, Any]:
    """Retrieve a single course for the user by course_id."""
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get(f"courses/{params.course_id}")
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_create_course(payload: CoursePayload) -> dict[str, Any]:
    """Create a new course on Canvas."""
    path = f"accounts/{payload.account_id}/courses"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.post(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_list_modules(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of modules for a course."""
    page = getattr(params, "page", 1)
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            modules = await client.get_all(f"courses/{params.course_id}/modules?page={page}")
        return {"modules": modules}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_get_module(params: ModuleParams) -> dict[str, Any]:
    """Retrieve a single module for a course."""
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get(f"courses/{params.course_id}/modules/{params.module_id}")
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_create_module(payload: ModulePayload) -> dict[str, Any]:
    """Create a module for a course."""
    path = f"courses/{payload.course_id}/modules"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.post(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_update_module(payload: UpdateModulePayload) -> dict[str, Any]:
    """Update a module of a course."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.put(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_delete_module(params: ModuleParams) -> dict[str, Any]:
    """Delete a module from a course."""
    path = f"courses/{params.course_id}/modules/{params.module_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.delete(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_list_module_items(params: ModuleParams) -> dict[str, Any]:
    """Retrieve a paginated list of module items in a module."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items?page={params.page}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get_all(path)
        return {"items": result}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_get_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """Retrieve a single module item."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_create_module_item(payload: ModuleItemPayload) -> dict[str, Any]:
    """Create a module item in a module."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}/items"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.post(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_update_module_item(payload: UpdateModuleItemPayload) -> dict[str, Any]:
    """Update a module item."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}/items/{payload.item_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.put(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_delete_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """Delete a module item."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.delete(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_list_pages(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of pages for a course."""
    page = getattr(params, "page", 1)
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get_all(f"courses/{params.course_id}/pages?page={page}")
        return {"pages": result}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_get_page(params: PageRequest) -> dict[str, Any]:
    """Retrieve a page for a course by page_url."""
    path = f"courses/{params.course_id}/pages/{params.page_url}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_create_page(payload: PagePayload) -> dict[str, Any]:
    """Create a page for a course."""
    path = f"courses/{payload.course_id}/pages"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.post(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_update_page(payload: UpdatePagePayload) -> dict[str, Any]:
    """Update a page for a course."""
    path = f"courses/{payload.course_id}/pages/{payload.url_or_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.put(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_delete_page(params: PageRequest) -> dict[str, Any]:
    """Delete a page for a course."""
    path = f"courses/{params.course_id}/pages/{params.page_url}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.delete(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_list_quizzes(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of quizzes for a course."""
    page = getattr(params, "page", 1)
    path = f"courses/{params.course_id}/quizzes?page={page}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            quizzes = await client.get_all(path)
        return {"quizzes": quizzes}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_get_quiz(params: QuizParams) -> dict[str, Any]:
    """Get a single quiz for a course."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_create_quiz(payload: QuizPayload) -> dict[str, Any]:
    """Create a quiz for a course."""
    path = f"courses/{payload.course_id}/quizzes"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.post(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_update_quiz(payload: UpdateQuizPayload) -> dict[str, Any]:
    """Update a quiz for a course."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.put(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_delete_quiz(params: QuizParams) -> dict[str, Any]:
    """Delete a quiz for a course."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.delete(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_list_questions(params: QuizParams) -> dict[str, Any]:
    """Retrieve a paginated list of questions in a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions?page={params.page}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            questions = await client.get_all(path)
        return {"questions": questions}
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_get_question(params: QuestionParams) -> dict[str, Any]:
    """Get a single question of a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.get(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_create_question(payload: QuestionPayload) -> dict[str, Any]:
    """Create a question in a quiz."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.post(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_update_question(payload: UpdateQuestionPayload) -> dict[str, Any]:
    """Update a question in a quiz."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions/{payload.question_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.put(path, payload.model_dump())
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_delete_question(params: QuestionParams) -> dict[str, Any]:
    """Delete a question in a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
    config = await load_user_plugin_config(CANVAS_PLUGIN_NAME, CanvasConfig)
    try:
        async with CanvasClient(config) as client:
            result = await client.delete(path)
        return result
    except (LMSRequestError, AuthenticationError) as e:
        return _lms_error(e)
    except ValueError as e:
        return {"error": {"message": str(e)}}


async def canvas_about() -> dict[str, Any]:
    """Explain Canvas's vocabulary, course structure and what "publish" means in Canvas.

    Read this before creating, changing or publishing Canvas content, or when a Canvas
    term is ambiguous.
    """
    return {"about": (Path(__file__).parent / "assets" / "about.txt").read_text(encoding="utf-8")}
