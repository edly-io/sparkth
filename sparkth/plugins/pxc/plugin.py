"""The PXC plugin: hosts a PXC learning activity and owns its data.

Exception mappings are registered at module level, not in ``__init__``: the loader constructs
the plugin once but its own tests construct it again, and ``register_exception_handler`` raises
on a duplicate key.
"""

from fastapi import status

from sparkth.lib.exceptions.handlers import register_exception_handler
from sparkth.lib.frontend.hooks import DISPLAY_INFO, DisplayInfo
from sparkth.lib.i18n import gettext_noop
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.pxc.exceptions import (
    PxcActionRejected,
    PxcActivityNotFound,
    PxcAssetNotFound,
    PxcDuplicateActivityName,
    PxcInvalidLaunchToken,
    PxcSandboxFailure,
)

# A bad launch token is 401: the token is the learner's only credential here, and the caller
# can get a fresh one by reloading the unit. A duplicate activity name is 500 — it is a broken
# deployment, not a bad request.
register_exception_handler(PxcActivityNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(PxcAssetNotFound, status.HTTP_404_NOT_FOUND)
register_exception_handler(PxcInvalidLaunchToken, status.HTTP_401_UNAUTHORIZED)
register_exception_handler(PxcActionRejected, status.HTTP_422_UNPROCESSABLE_CONTENT)
register_exception_handler(PxcSandboxFailure, status.HTTP_502_BAD_GATEWAY)
register_exception_handler(PxcDuplicateActivityName, status.HTTP_500_INTERNAL_SERVER_ERROR)


class PxcPlugin(SparkthPlugin):
    """Hosts PXC activities and serves them to learners inside another LMS's course."""

    def __init__(self) -> None:
        super().__init__("pxc")
        DISPLAY_INFO.add_item(
            self,
            DisplayInfo(
                gettext_noop("PXC Activities"),
                gettext_noop("Portable, sandboxed learning activities hosted by Sparkth"),
            ),
        )
