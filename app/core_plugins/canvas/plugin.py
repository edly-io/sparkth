"""
Canvas LMS Plugin
"""

from collections.abc import Callable
from typing import Any

import app.core_plugins.canvas.tools as canvas_tools
from app.core_plugins.canvas.config import CanvasConfig
from app.lib.config.hooks import CONFIG_SCHEMAS
from app.lib.mcp.hooks import MCP_TOOLS, Tool
from app.plugins.base import SparkthPlugin


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
            ("canvas-auth", [canvas_tools.canvas_authenticate]),
            (
                "canvas-courses",
                [
                    canvas_tools.canvas_get_courses,
                    canvas_tools.canvas_get_course,
                    canvas_tools.canvas_create_course,
                ],
            ),
            (
                "canvas-modules",
                [
                    canvas_tools.canvas_list_modules,
                    canvas_tools.canvas_get_module,
                    canvas_tools.canvas_create_module,
                    canvas_tools.canvas_update_module,
                    canvas_tools.canvas_delete_module,
                ],
            ),
            (
                "canvas-module-items",
                [
                    canvas_tools.canvas_list_module_items,
                    canvas_tools.canvas_get_module_item,
                    canvas_tools.canvas_create_module_item,
                    canvas_tools.canvas_update_module_item,
                    canvas_tools.canvas_delete_module_item,
                ],
            ),
            (
                "canvas-pages",
                [
                    canvas_tools.canvas_list_pages,
                    canvas_tools.canvas_get_page,
                    canvas_tools.canvas_create_page,
                    canvas_tools.canvas_update_page,
                    canvas_tools.canvas_delete_page,
                ],
            ),
            (
                "canvas-quizzes",
                [
                    canvas_tools.canvas_list_quizzes,
                    canvas_tools.canvas_get_quiz,
                    canvas_tools.canvas_create_quiz,
                    canvas_tools.canvas_update_quiz,
                    canvas_tools.canvas_delete_quiz,
                ],
            ),
            (
                "canvas-questions",
                [
                    canvas_tools.canvas_list_questions,
                    canvas_tools.canvas_get_question,
                    canvas_tools.canvas_create_question,
                    canvas_tools.canvas_update_question,
                    canvas_tools.canvas_delete_question,
                ],
            ),
        ]
        for category, handlers in tools_per_category:
            MCP_TOOLS.add_items(self, [Tool(handler, category=category) for handler in handlers])
