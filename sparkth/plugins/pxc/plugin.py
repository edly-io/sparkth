"""The PXC plugin: hosts a PXC learning activity and owns its data.

Exception mappings are registered at module level, not in ``__init__``: the loader constructs
the plugin once but its own tests construct it again, and ``register_exception_handler`` builds
a fresh handler closure on every call, so a second registration is a genuine duplicate rather
than a repeat of the same one. The Compose agent and the MCP tools are per plugin instance,
so they register in ``__init__``.
"""

from fastapi import APIRouter, Depends, status

from sparkth.lib.compose.hooks import register_agent
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
from sparkth.lib.mcp.hooks import MCP_TOOLS
from sparkth.lib.permissions import PLUGIN_USE
from sparkth.lib.permissions.scopes import PLUGIN
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.pxc.agent import PXC_ACTIVITY_BUILDER
from sparkth.plugins.pxc.constants import PXC_CORS_HEADERS, PXC_PLUGIN_NAME
from sparkth.plugins.pxc.contributor import build_pxc_block, list_pxc_options, record_pxc_placement
from sparkth.plugins.pxc.exceptions import (
    PxcActionRejected,
    PxcActivityNotFound,
    PxcActivityNotPermitted,
    PxcAssetNotFound,
    PxcDuplicateActivityName,
    PxcInvalidLaunchToken,
    PxcLaunchNotConfigured,
    PxcSandboxFailure,
)
from sparkth.plugins.pxc.routes import router as learner_router
from sparkth.plugins.pxc.routes.activities import router as activity_router
from sparkth.plugins.pxc.tools import PXC_TOOLS

# A bad launch token is 401: the token is the learner's only credential here, and the caller
# can get a fresh one by reloading the page. A missing permission is 403: the account is known
# and lacks the permission, whether it is the caller of an author route or the account a launch
# token is checked for. A duplicate activity name is 500 — it is a broken deployment, not a bad
# request. An unconfigured launch secret is 503: the author's request is fine and the deployment
# is not. A sandbox failure is 422, like a refused action: the request was fine but the activity
# could not process it, and unlike a 5xx a proxy never sends it, so the embed page can drop that
# action without dropping one a redeploy refused. Errors the embed page can hit carry CORS
# headers so it can read them; a refused launch is one of them.
register_exception_handler(PxcActivityNotFound, status.HTTP_404_NOT_FOUND, PXC_CORS_HEADERS)
register_exception_handler(PxcActivityNotPermitted, status.HTTP_403_FORBIDDEN, PXC_CORS_HEADERS)
register_exception_handler(PxcAssetNotFound, status.HTTP_404_NOT_FOUND, PXC_CORS_HEADERS)
register_exception_handler(PxcInvalidLaunchToken, status.HTTP_401_UNAUTHORIZED, PXC_CORS_HEADERS)
register_exception_handler(PxcActionRejected, status.HTTP_422_UNPROCESSABLE_CONTENT, PXC_CORS_HEADERS)
register_exception_handler(PxcLaunchNotConfigured, status.HTTP_503_SERVICE_UNAVAILABLE)
register_exception_handler(PxcSandboxFailure, status.HTTP_422_UNPROCESSABLE_CONTENT, PXC_CORS_HEADERS)
register_exception_handler(PxcDuplicateActivityName, status.HTTP_500_INTERNAL_SERVER_ERROR)

# PLUGIN_ROUTERS keeps one router per plugin, so both surfaces go in under one parent.
pxc_router = APIRouter()
# The learner routes carry a launch token instead, so they need no plugin.use.
pxc_router.include_router(learner_router)
pxc_router.include_router(
    activity_router, dependencies=[Depends(PLUGIN_USE.require_for_object(PLUGIN, PXC_PLUGIN_NAME))]
)


class PxcPlugin(SparkthPlugin):
    """Hosts PXC activities, builds new ones from chat, serves them to learners inside another
    LMS's course."""

    def __init__(self) -> None:
        super().__init__(PXC_PLUGIN_NAME)
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
        MCP_TOOLS.add_items(self, PXC_TOOLS)
        register_agent(self, PXC_ACTIVITY_BUILDER)
        register_content_contributor(
            self,
            ContentContributor(
                "pxc",
                "A portable, sandboxed PXC learning activity hosted by Sparkth: a bundled sample "
                "or an activity the author may place",
                # Each key is an LMS publishing plugin's registered name, written as a literal so
                # this plugin imports no LMS plugin. These keys are the only place it names an LMS.
                {"openedx": build_pxc_block},
                list_pxc_options,
                record_pxc_placement,
            ),
        )
