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

from typing import Any
import sys
from pathlib import Path

# Add parent directory to path for imports
plugin_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(plugin_dir))

from app.plugins.base import SparkthPlugin, tool
from sparkth_mcp.types import AuthenticationError

# Import Canvas-specific modules from the same directory
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


class CanvasPlugin(SparkthPlugin):
    """
    Canvas LMS Integration Plugin
    
    Provides comprehensive Canvas LMS API integration with 30+ MCP tools for:
    - Authentication and credential validation
    - Course CRUD operations
    - Module and module item management
    - Wiki page management
    - Quiz and question management
    
    Tools are auto-registered via @tool decorator using metaclass magic!
    """
    
    def __init__(self):
        super().__init__(
            name="canvas-plugin",
            version="1.0.0",
            description="Canvas LMS integration with 30+ MCP tools",
            author="Sparkth Team"
        )
        # Tools auto-register via metaclass - no manual registration needed!
    
    # ==================== Authentication Tools ====================
    
    @tool(description="Authenticate Canvas API URL and token", category="canvas-auth")
    async def canvas_authenticate(self, auth: AuthenticationPayload) -> dict[str, Any]:
        """Authenticate the provided Canvas API URL and token."""
        try:
            res = await CanvasClient.authenticate(auth.api_url, auth.api_token)
            return {"status": res}
        except AuthenticationError as e:
            return {"status": e.status_code, "message": e.message}
    
    # ==================== Course Tools ====================
    
    @tool(description="Retrieve a paginated list of courses", category="canvas-courses")
    async def canvas_get_courses(self, auth: AuthenticationPayload, page: int) -> dict[str, Any]:
        """Retrieve a paginated list of courses for the user."""
        async with CanvasClient(auth.api_url, auth.api_token) as client:
            courses = await client.get(f"courses?page={page}")
        return {"courses": courses}
    
    @tool(description="Retrieve a single course by course_id", category="canvas-courses")
    async def canvas_get_course(self, params: CourseParams) -> dict[str, Any]:
        """Retrieve a single course for the user by course_id."""
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(f"courses/{params.course_id}")
        return result
    
    @tool(description="Create a new course on Canvas", category="canvas-courses")
    async def canvas_create_course(self, payload: CoursePayload) -> dict[str, Any]:
        """Create a new course on Canvas."""
        path = f"accounts/{payload.account_id}/courses"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.post(path, payload.model_dump())
        return result
    
    # ==================== Module Tools ====================
    
    @tool(description="Retrieve a paginated list of modules for a course", category="canvas-modules")
    async def canvas_list_modules(self, params: CourseParams) -> dict[str, Any]:
        """Retrieve a paginated list of modules for a course."""
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            modules = await client.get(f"courses/{params.course_id}/modules?page={params.page}")
        return {"modules": modules}
    
    @tool(description="Retrieve a single module for a course", category="canvas-modules")
    async def canvas_get_module(self, params: ModuleParams) -> dict[str, Any]:
        """Retrieve a single module for a course."""
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(f"courses/{params.course_id}/modules/{params.module_id}")
        return result
    
    @tool(description="Create a module for a course", category="canvas-modules")
    async def canvas_create_module(self, payload: ModulePayload) -> dict[str, Any]:
        """Create a module for a course."""
        path = f"courses/{payload.course_id}/modules"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.post(path, payload.model_dump())
        return result
    
    @tool(description="Update a module of a course", category="canvas-modules")
    async def canvas_update_module(self, payload: UpdateModulePayload) -> dict[str, Any]:
        """Update a module of a course."""
        path = f"courses/{payload.course_id}/modules/{payload.module_id}"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.put(path, payload.model_dump())
        return result
    
    @tool(description="Delete a module from a course", category="canvas-modules")
    async def canvas_delete_module(self, params: ModuleParams) -> dict[str, Any]:
        """Delete a module from a course."""
        path = f"courses/{params.course_id}/modules/{params.module_id}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.delete(path)
        return result
    
    # ==================== Module Item Tools ====================
    
    @tool(description="Retrieve a paginated list of module items in a module", category="canvas-module-items")
    async def canvas_list_module_items(self, params: ModuleParams) -> dict[str, Any]:
        """Retrieve a paginated list of module items in a module."""
        path = f"courses/{params.course_id}/modules/{params.module_id}/items?page={params.page}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(path)
        return result
    
    @tool(description="Retrieve a single module item", category="canvas-module-items")
    async def canvas_get_module_item(self, params: ModuleItemParams) -> dict[str, Any]:
        """Retrieve a single module item."""
        path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(path)
        return result
    
    @tool(description="Create a module item in a module", category="canvas-module-items")
    async def canvas_create_module_item(self, payload: ModuleItemPayload) -> dict[str, Any]:
        """Create a module item in a module."""
        path = f"courses/{payload.course_id}/modules/{payload.module_id}/items"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.post(path, payload.model_dump())
        return result
    
    @tool(description="Update a module item", category="canvas-module-items")
    async def canvas_update_module_item(self, payload: UpdateModuleItemPayload) -> dict[str, Any]:
        """Update a module item."""
        path = f"courses/{payload.course_id}/modules/{payload.module_id}/items/{payload.item_id}"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.put(path, payload.model_dump())
        return result
    
    @tool(description="Delete a module item", category="canvas-module-items")
    async def canvas_delete_module_item(self, params: ModuleItemParams) -> dict[str, Any]:
        """Delete a module item."""
        path = f"courses/{params.course_id}/modules/{params.module_id}/items/{params.module_item_id}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.delete(path)
        return result
    
    # ==================== Page Tools ====================
    
    @tool(description="Retrieve a paginated list of pages for a course", category="canvas-pages")
    async def canvas_list_pages(self, params: CourseParams) -> dict[str, Any]:
        """Retrieve a paginated list of pages for a course."""
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(f"courses/{params.course_id}/pages?page={params.page}")
        return result
    
    @tool(description="Retrieve a page for a course by page_url", category="canvas-pages")
    async def canvas_get_page(self, params: PageRequest) -> dict[str, Any]:
        """Retrieve a page for a course by page_url."""
        path = f"courses/{params.course_id}/pages/{params.page_url}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(path)
        return result
    
    @tool(description="Create a page for a course", category="canvas-pages")
    async def canvas_create_page(self, payload: PagePayload) -> dict[str, Any]:
        """Create a page for a course."""
        path = f"courses/{payload.course_id}/pages"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.post(path, payload.model_dump())
        return result
    
    @tool(description="Update a page for a course", category="canvas-pages")
    async def canvas_update_page(self, payload: UpdatePagePayload) -> dict[str, Any]:
        """Update a page for a course."""
        path = f"courses/{payload.course_id}/pages/{payload.url_or_id}"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.put(path, payload.model_dump())
        return result
    
    @tool(description="Delete a page for a course", category="canvas-pages")
    async def canvas_delete_page(self, params: PageRequest) -> dict[str, Any]:
        """Delete a page for a course."""
        path = f"courses/{params.course_id}/pages/{params.page_url}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.delete(path)
        return result
    
    # ==================== Quiz Tools ====================
    
    @tool(description="Retrieve a paginated list of quizzes for a course", category="canvas-quizzes")
    async def canvas_list_quizzes(self, params: CourseParams) -> dict[str, Any]:
        """Retrieve a paginated list of quizzes for a course."""
        path = f"courses/{params.course_id}/quizzes?page={params.page}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            quizzes = await client.get(path)
        return {"quizzes": quizzes}
    
    @tool(description="Get a single quiz for a course", category="canvas-quizzes")
    async def canvas_get_quiz(self, params: QuizParams) -> dict[str, Any]:
        """Get a single quiz for a course."""
        path = f"courses/{params.course_id}/quizzes/{params.quiz_id}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(path)
        return result
    
    @tool(description="Create a quiz for a course", category="canvas-quizzes")
    async def canvas_create_quiz(self, payload: QuizPayload) -> dict[str, Any]:
        """Create a quiz for a course."""
        path = f"courses/{payload.course_id}/quizzes"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.post(path, payload.model_dump())
        return result
    
    @tool(description="Update a quiz for a course", category="canvas-quizzes")
    async def canvas_update_quiz(self, payload: UpdateQuizPayload) -> dict[str, Any]:
        """Update a quiz for a course."""
        path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.put(path, payload.model_dump())
        return result
    
    @tool(description="Delete a quiz for a course", category="canvas-quizzes")
    async def canvas_delete_quiz(self, params: QuizParams) -> dict[str, Any]:
        """Delete a quiz for a course."""
        path = f"courses/{params.course_id}/quizzes/{params.quiz_id}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.delete(path)
        return result
    
    # ==================== Question Tools ====================
    
    @tool(description="Retrieve a paginated list of questions in a quiz", category="canvas-questions")
    async def canvas_list_questions(self, params: QuizParams) -> dict[str, Any]:
        """Retrieve a paginated list of questions in a quiz."""
        path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions?page={params.page}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            questions = await client.get(path)
        return {"questions": questions}
    
    @tool(description="Get a single question of a quiz", category="canvas-questions")
    async def canvas_get_question(self, params: QuestionParams) -> dict[str, Any]:
        """Get a single question of a quiz."""
        path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.get(path)
        return result
    
    @tool(description="Create a question in a quiz", category="canvas-questions")
    async def canvas_create_question(self, payload: QuestionPayload) -> dict[str, Any]:
        """Create a question in a quiz."""
        path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.post(path, payload.model_dump())
        return result
    
    @tool(description="Update a question in a quiz", category="canvas-questions")
    async def canvas_update_question(self, payload: UpdateQuestionPayload) -> dict[str, Any]:
        """Update a question in a quiz."""
        path = f"courses/{payload.course_id}/quizzes/{payload.quiz_id}/questions/{payload.question_id}"
        async with CanvasClient(payload.auth.api_url, payload.auth.api_token) as client:
            result = await client.put(path, payload.model_dump())
        return result
    
    @tool(description="Delete a question in a quiz", category="canvas-questions")
    async def canvas_delete_question(self, params: QuestionParams) -> dict[str, Any]:
        """Delete a question in a quiz."""
        path = f"courses/{params.course_id}/quizzes/{params.quiz_id}/questions/{params.question_id}"
        async with CanvasClient(params.auth.api_url, params.auth.api_token) as client:
            result = await client.delete(path)
        return result
