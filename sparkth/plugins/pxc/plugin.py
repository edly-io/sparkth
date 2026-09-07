"""The PXC plugin: hosts a PXC learning activity and owns its data.

Exception mappings are registered at module level, not in ``__init__``: the loader constructs
the plugin once but its own tests construct it again, and ``register_exception_handler`` raises
on a duplicate key.
"""

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
register_exception_handler(PxcActivityNotFound, 404)
register_exception_handler(PxcAssetNotFound, 404)
register_exception_handler(PxcInvalidLaunchToken, 401)
register_exception_handler(PxcActionRejected, 422)
register_exception_handler(PxcSandboxFailure, 502)
register_exception_handler(PxcDuplicateActivityName, 500)


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
