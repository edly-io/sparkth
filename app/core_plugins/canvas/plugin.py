"""
Canvas LMS Plugin

Provides MCP tools for interacting with Canvas LMS API including:
- Authentication
- Course management
- Module management
- Module items management
- Page management
- Quiz and question management
"""

from collections.abc import Callable
from typing import Any

from app.core_plugins.canvas.config import CanvasConfig
from app.lib.config.hooks import CONFIG_SCHEMAS
from app.lib.mcp.hooks import MCP_TOOLS, Tool
from app.mcp.types import AuthenticationError
from app.plugins.base import SparkthPlugin

from .client import CanvasClient
from .types import (
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


class CanvasPlugin(SparkthPlugin):
    """
    Canvas LMS Integration Plugin

    Provides comprehensive Canvas LMS API integration with 30+ MCP tools for:
    - Authentication and credential validation
    - Course CRUD operations
    - Module and module item management
    - Wiki page management
    - Quiz and question management

    Tools are contributed to the MCP_TOOLS hook in ``__init__``; each tool's
    description comes from its handler docstring.
    """

    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        CONFIG_SCHEMAS.add_item(self, CanvasConfig)
        tools_per_category: list[tuple[str, list[Callable[..., Any]]]] = [
            ("canvas-auth", [canvas_authenticate]),
            (
                "canvas-courses",
                [
                    canvas_get_courses,
                    canvas_get_course,
                    canvas_create_course,
                ],
            ),
            (
                "canvas-modules",
                [
                    canvas_list_modules,
                    canvas_get_module,
                    canvas_create_module,
                    canvas_update_module,
                    canvas_delete_module,
                ],
            ),
            (
                "canvas-module-items",
                [
                    canvas_list_module_items,
                    canvas_get_module_item,
                    canvas_create_module_item,
                    canvas_update_module_item,
                    canvas_delete_module_item,
                ],
            ),
            (
                "canvas-pages",
                [
                    canvas_list_pages,
                    canvas_get_page,
                    canvas_create_page,
                    canvas_update_page,
                    canvas_delete_page,
                ],
            ),
            (
                "canvas-quizzes",
                [
                    canvas_list_quizzes,
                    canvas_get_quiz,
                    canvas_create_quiz,
                    canvas_update_quiz,
                    canvas_delete_quiz,
                ],
            ),
            (
                "canvas-questions",
                [
                    canvas_list_questions,
                    canvas_get_question,
                    canvas_create_question,
                    canvas_update_question,
                    canvas_delete_question,
                ],
            ),
        ]
        for category, handlers in tools_per_category:
            MCP_TOOLS.add_items(self, [Tool(handler, category=category) for handler in handlers])


async def canvas_authenticate(auth: AuthenticationPayload) -> dict[str, Any]:
    """Authenticate the provided Canvas API URL and token."""
    try:
        res = await CanvasClient.authenticate(auth.api_url, auth.api_token)
        return {"status": res}
    except AuthenticationError as e:
        return {"status": e.status_code, "message": e.message}


async def canvas_get_courses(auth: AuthenticationPayload, page: int) -> dict[str, Any]:
    """Retrieve a paginated list of courses for the user."""
    async with CanvasClient(auth.api_url, auth.api_token) as client:
        courses = await client.get(f"courses?page={page}")
    return {"courses": courses}


async def canvas_get_course(params: CourseParams) -> dict[str, Any]:
    """Retrieve a single course for the user by course_id."""
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(f"courses/{params.course_id}")
    return result


async def canvas_create_course(payload: CoursePayload) -> dict[str, Any]:
    """Create a new course on Canvas."""
    path = f"accounts/{payload.account_id}/courses"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.post(path, payload.model_dump())
    return result


async def canvas_list_modules(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of modules for a course."""
    page = getattr(params, "page", 1)
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        modules = await client.get(f"courses/{params.course_id}/modules?page={page}")
    return {"modules": modules}


async def canvas_get_module(params: ModuleParams) -> dict[str, Any]:
    """Retrieve a single module for a course."""
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(f"courses/{params.course_id}/modules/{params.module_id}")
    return result


async def canvas_create_module(payload: ModulePayload) -> dict[str, Any]:
    """Create a module for a course."""
    path = f"courses/{payload.course_id}/modules"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.post(path, payload.model_dump())
    return result


async def canvas_update_module(payload: UpdateModulePayload) -> dict[str, Any]:
    """Update a module of a course."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.put(path, payload.model_dump())
    return result


async def canvas_delete_module(params: ModuleParams) -> dict[str, Any]:
    """Delete a module from a course."""
    path = f"courses/{params.course_id}/modules/{params.module_id}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.delete(path)
    return result


async def canvas_list_module_items(params: ModuleParams) -> dict[str, Any]:
    """Retrieve a paginated list of module items in a module."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items?page={params.page}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(path)
    return result


async def canvas_get_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """Retrieve a single module item."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(path)
    return result


async def canvas_create_module_item(payload: ModuleItemPayload) -> dict[str, Any]:
    """Create a module item in a module."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}/items"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.post(path, payload.model_dump())
    return result


async def canvas_update_module_item(payload: UpdateModuleItemPayload) -> dict[str, Any]:
    """Update a module item."""
    path = f"courses/{payload.course_id}/modules/{payload.module_id}/items/{payload.item_id}"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.put(path, payload.model_dump())
    return result


async def canvas_delete_module_item(params: ModuleItemParams) -> dict[str, Any]:
    """Delete a module item."""
    path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.delete(path)
    return result


async def canvas_list_pages(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of pages for a course."""
    page = getattr(params, "page", 1)
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(f"courses/{params.course_id}/pages?page={page}")
    return result


async def canvas_get_page(params: PageRequest) -> dict[str, Any]:
    """Retrieve a page for a course by page_url."""
    path = f"courses/{params.course_id}/pages/{params.page_url}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(path)
    return result


async def canvas_create_page(payload: PagePayload) -> dict[str, Any]:
    """Create a page for a course."""
    path = f"courses/{payload.course_id}/pages"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.post(path, payload.model_dump())
    return result


async def canvas_update_page(payload: UpdatePagePayload) -> dict[str, Any]:
    """Update a page for a course."""
    path = f"courses/{payload.course_id}/pages/{payload.url_or_id}"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.put(path, payload.model_dump())
    return result


async def canvas_delete_page(params: PageRequest) -> dict[str, Any]:
    """Delete a page for a course."""
    path = f"courses/{params.course_id}/pages/{params.page_url}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.delete(path)
    return result


async def canvas_list_quizzes(params: CourseParams) -> dict[str, Any]:
    """Retrieve a paginated list of quizzes for a course."""
    page = getattr(params, "page", 1)
    path = f"courses/{params.course_id}/quizzes?page={page}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        quizzes = await client.get(path)
    return {"quizzes": quizzes}


async def canvas_get_quiz(params: QuizParams) -> dict[str, Any]:
    """Get a single quiz for a course."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(path)
    return result


async def canvas_create_quiz(payload: QuizPayload) -> dict[str, Any]:
    """Create a quiz for a course."""
    path = f"courses/{payload.course_id}/quizzes"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.post(path, payload.model_dump())
    return result


async def canvas_update_quiz(payload: UpdateQuizPayload) -> dict[str, Any]:
    """Update a quiz for a course."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.put(path, payload.model_dump())
    return result


async def canvas_delete_quiz(params: QuizParams) -> dict[str, Any]:
    """Delete a quiz for a course."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.delete(path)
    return result


async def canvas_list_questions(params: QuizParams) -> dict[str, Any]:
    """Retrieve a paginated list of questions in a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions?page={params.page}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        questions = await client.get(path)
    return {"questions": questions}


async def canvas_get_question(params: QuestionParams) -> dict[str, Any]:
    """Get a single question of a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.get(path)
    return result


async def canvas_create_question(payload: QuestionPayload) -> dict[str, Any]:
    """Create a question in a quiz."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.post(path, payload.model_dump())
    return result


async def canvas_update_question(payload: UpdateQuestionPayload) -> dict[str, Any]:
    """Update a question in a quiz."""
    path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions/{payload.question_id}"
    async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
        result = await client.put(path, payload.model_dump())
    return result


async def canvas_delete_question(params: QuestionParams) -> dict[str, Any]:
    """Delete a question in a quiz."""
    path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
    async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
        result = await client.delete(path)
    return result
