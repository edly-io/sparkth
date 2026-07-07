from collections.abc import Callable
from typing import Any

from sparkth.core_plugins.openedx import tools as openedx_tools
from sparkth.core_plugins.openedx.config import OpenEdxConfig
from sparkth.lib.config.hooks import CONFIG_SCHEMAS
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.plugins import SparkthPlugin


class OpenEdxPlugin(SparkthPlugin):
    """
    Open edX Integration Plugin

    Provides comprehensive Open edX API integration with MCP tools for:
    - Authentication and credential validation
    - Course CRUD operations
    - Section and subsection management
    - Unit, Problem and HTML Component Management

    Tools are contributed to the MCP_TOOLS hook in ``__init__``; each tool's
    description comes from its handler docstring.
    """

    def __init__(self, plugin_name: str) -> None:
        super().__init__(plugin_name)
        CONFIG_SCHEMAS.add_item(self, OpenEdxConfig)
        tools_per_category: list[tuple[str, list[Callable[..., Any]]]] = [
            (
                "openedx-auth",
                [
                    openedx_tools.openedx_authenticate,
                    openedx_tools.openedx_refresh_access_token,
                ],
            ),
            (
                "openedx-user",
                [
                    openedx_tools.openedx_get_user_info,
                ],
            ),
            (
                "openedx-course",
                [
                    openedx_tools.openedx_create_course_run,
                    openedx_tools.openedx_list_course_runs,
                    openedx_tools.openedx_create_xblock,
                    openedx_tools.openedx_create_problem_or_html,
                    openedx_tools.openedx_update_xblock,
                ],
            ),
            ("openedx-course-tree", [openedx_tools.openedx_get_course_tree_raw]),
            ("openedx-content-store", [openedx_tools.openedx_get_block_contentstore]),
        ]
        for category, handlers in tools_per_category:
            MCP_TOOLS.add_items(self, [Tool(handler, category=category) for handler in handlers])
