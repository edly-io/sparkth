"""Moodle LMS Plugin"""

from collections.abc import Callable
from typing import Any

import sparkth.plugins.moodle.tools as moodle_tools
from sparkth.lib.config.hooks import CONFIG_SCHEMAS
from sparkth.lib.frontend.hooks import DISPLAY_INFO, DisplayInfo
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.moodle.config import MoodleConfig


class MoodlePlugin(SparkthPlugin):
    """
    Moodle LMS Integration Plugin

    Provides Moodle web services integration with MCP tools for:
    - Authentication and credential validation
    - Course creation and listing
    - Section, Page and Quiz authoring
    """

    def __init__(self) -> None:
        super().__init__("moodle")
        CONFIG_SCHEMAS.add_item(self, MoodleConfig)
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo(
                gettext_noop("Moodle"),
                gettext_noop("Moodle integration with tools for courses, sections, pages, and quizzes"),
            ),
        )
        tools_per_category: list[tuple[str, list[Callable[..., Any]]]] = [
            ("moodle-auth", [moodle_tools.moodle_authenticate]),
            (
                "moodle-courses",
                [
                    moodle_tools.moodle_list_courses,
                    moodle_tools.moodle_create_course,
                ],
            ),
            (
                "moodle-content",
                [
                    moodle_tools.moodle_create_section,
                    moodle_tools.moodle_create_page,
                    moodle_tools.moodle_create_quiz,
                ],
            ),
        ]
        for category, handlers in tools_per_category:
            MCP_TOOLS.add_items(self, [Tool(handler, category=category) for handler in handlers])
