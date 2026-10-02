"""The PXC plugin: hosts a PXC learning activity and owns its data.

Exception mappings are registered at module level, not in ``__init__``: the loader constructs
the plugin once but its own tests construct it again, and ``register_exception_handler`` builds
a fresh handler closure on every call, so a second registration is a genuine duplicate rather
than a repeat of the same one.
"""

from fastapi import APIRouter, status

from sparkth.lib.content.hooks import ContentContributor, register_content_contributor
from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.frontend.hooks import DISPLAY_INFO, DisplayInfo
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.plugins import SparkthPlugin
from sparkth.lib.routes import register_router
from sparkth.plugins.pxc.activity_routes import router as activity_router
from sparkth.plugins.pxc.constants import PXC_CORS_HEADERS
from sparkth.plugins.pxc.contributor import build_pxc_block
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
# fine and the deployment is not. Errors the embed page can hit carry CORS headers so it can
# read them.
register_exception_handler(PxcActivityNotFound, status.HTTP_404_NOT_FOUND, PXC_CORS_HEADERS)
register_exception_handler(PxcAssetNotFound, status.HTTP_404_NOT_FOUND, PXC_CORS_HEADERS)
register_exception_handler(PxcInvalidLaunchToken, status.HTTP_401_UNAUTHORIZED, PXC_CORS_HEADERS)
register_exception_handler(PxcActionRejected, status.HTTP_422_UNPROCESSABLE_CONTENT, PXC_CORS_HEADERS)
register_exception_handler(PxcLaunchNotConfigured, status.HTTP_503_SERVICE_UNAVAILABLE)
register_exception_handler(PxcSandboxFailure, status.HTTP_502_BAD_GATEWAY, PXC_CORS_HEADERS)
register_exception_handler(PxcDuplicateActivityName, status.HTTP_500_INTERNAL_SERVER_ERROR)

# PLUGIN_ROUTERS keeps one router per plugin, so both surfaces go in under one parent.
pxc_router = APIRouter()
pxc_router.include_router(learner_router)
pxc_router.include_router(activity_router)


class PxcPlugin(SparkthPlugin):
    """Hosts PXC activities and serves them to learners inside another LMS's course."""

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
        register_content_contributor(
            ContentContributor(
                "pxc",
                "A portable, sandboxed PXC learning activity hosted by Sparkth",
                # The key is the publishing plugin's registered name, written as a literal so
                # this plugin does not import the Open edX plugin.
                # This is the only place where the pxc plugin is coupled with an LMS plugin.
                # The PXC plugin needs to know about the LMS plugin it is contributing to.
                {"open-edx": build_pxc_block},
            )
        )
