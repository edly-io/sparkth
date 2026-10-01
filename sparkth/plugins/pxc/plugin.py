"""The PXC plugin: hosts a PXC learning activity and owns its data.

Exception mappings are registered at module level, not in ``__init__``: the loader constructs
the plugin once but its own tests construct it again, and ``register_exception_handler`` builds
a fresh handler closure on every call, so a second registration is a genuine duplicate rather
than a repeat of the same one. The chat responsibility and the MCP tools are per plugin instance,
so they register in ``__init__``.
"""

from fastapi import APIRouter, status

from sparkth.lib.chat.hooks import CHAT_RESPONSIBILITIES, ChatResponsibility
from sparkth.lib.content.hooks import ContentContributor, register_content_contributor
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.frontend.hooks import (
    DISPLAY_INFO,
    FRONTEND_APPS,
    SIDEBAR_ENTRIES,
    DisplayInfo,
    FrontendApp,
    SidebarEntry,
)
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.pxc import tools as pxc_tools
from sparkth.plugins.pxc.activity_routes import router as activity_router
from sparkth.plugins.pxc.constants import (
    PXC_ACTIVITY_SCOPE,
    PXC_ACTIVITY_SYSTEM_PROMPT,
    PXC_RESPONSIBILITY_NAME,
    PXC_TOOL_CATEGORY,
)
from sparkth.plugins.pxc.contributor import build_pxc_block, list_pxc_options
from sparkth.plugins.pxc.exceptions import (
    PxcActionRejected,
    PxcActivityNotFound,
    PxcAssetNotFound,
    PxcDuplicateActivityName,
    PxcInvalidLaunchToken,
    PxcLaunchNotConfigured,
    PxcSandboxFailure,
)
from sparkth.plugins.pxc.routes import router as learner_router

# A bad launch token is 401: the token is the learner's only credential here, and the caller
# can get a fresh one by reloading the unit. A duplicate activity name is 500 — it is a broken
# deployment, not a bad request. An unconfigured launch secret is 503: the author's request is
# fine and the deployment is not.
register_exception_handler(PxcActivityNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(PxcAssetNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(PxcInvalidLaunchToken, status.HTTP_401_UNAUTHORIZED)
register_exception_handler(PxcActionRejected, status.HTTP_422_UNPROCESSABLE_CONTENT)
register_exception_handler(PxcLaunchNotConfigured, status.HTTP_503_SERVICE_UNAVAILABLE)
register_exception_handler(PxcSandboxFailure, status.HTTP_502_BAD_GATEWAY)
register_exception_handler(PxcDuplicateActivityName, status.HTTP_500_INTERNAL_SERVER_ERROR)

# PLUGIN_ROUTERS keeps one router per plugin, so both surfaces go in under one parent.
pxc_router = APIRouter()
pxc_router.include_router(learner_router)
pxc_router.include_router(activity_router)

# The chat job that builds activities; it alone sees the pxc tools.
PXC_ACTIVITY = ChatResponsibility(
    PXC_RESPONSIBILITY_NAME,
    PXC_ACTIVITY_SCOPE,
    PXC_ACTIVITY_SYSTEM_PROMPT,
    frozenset({PXC_TOOL_CATEGORY}),
)


class PxcPlugin(SparkthPlugin):
    """Hosts PXC activities, builds new ones from chat, serves them to learners inside another
    LMS's course, and ships the authors' Activities page at ``/dashboard/pxc``."""

    def __init__(self) -> None:
        super().__init__("pxc")
        register_router(self, pxc_router)
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo(
                gettext_noop("PXC Activities"),
                gettext_noop("Portable, sandboxed learning activities hosted by Sparkth"),
            ),
        )
        SIDEBAR_ENTRIES.add_item(self, SidebarEntry(gettext_noop("Activities"), icon="blocks", order=2))
        FRONTEND_APPS.add_item(self, FrontendApp())
        CHAT_RESPONSIBILITIES.add_item(self, PXC_ACTIVITY)
        MCP_TOOLS.add_items(
            self,
            [
                Tool(handler, PXC_TOOL_CATEGORY)
                for handler in (
                    pxc_tools.pxc_about,
                    pxc_tools.pxc_build_activity,
                    pxc_tools.pxc_list_activities,
                    pxc_tools.pxc_get_activity_source,
                )
            ],
        )
        register_content_contributor(
            ContentContributor(
                "pxc",
                "A portable, sandboxed PXC learning activity hosted by Sparkth: a bundled sample "
                "or one of the author's own activities",
                # The key is the publishing plugin's registered name, written as a literal so
                # this plugin does not import the Open edX plugin.
                # This is the only place where the pxc plugin is coupled with an LMS plugin.
                # The PXC plugin needs to know about the LMS plugin it is contributing to.
                {"open-edx": build_pxc_block},
                list_pxc_options,
            )
        )
