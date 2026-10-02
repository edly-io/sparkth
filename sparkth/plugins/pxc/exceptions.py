"""Domain exceptions for the PXC plugin.

None of these carries an HTTP status. ``plugin.py`` registers each against exactly one status
with ``register_exception_handler``, so the routes just raise and the framework renders the
response.
"""


class PxcActivityNotFound(Exception):
    """No bundled or generated activity goes by this name, or the caller does not own the one asked for."""


class PxcDuplicateActivityName(Exception):
    """Two bundled activity directories declare the same manifest name.

    Sparkth is the LMS here, so it owns the uniqueness of activity names: the name is also the
    state file's name, and two types sharing one would share their learners' state.
    """


class PxcInvalidLaunchToken(Exception):
    """The launch token is missing, malformed, expired, or not signed with the shared secret."""


class PxcAssetNotFound(Exception):
    """The activity does not declare this asset, or it is missing on disk."""


class PxcActionRejected(Exception):
    """The activity's manifest does not accept this action, or its value has the wrong shape."""


class PxcSandboxFailure(Exception):
    """The activity's WebAssembly sandbox failed to run."""


class PxcLaunchNotConfigured(Exception):
    """Sparkth cannot mint a launch token because ``PXC_LAUNCH_SECRET`` is empty."""


class PxcBuildFailed(Exception):
    """An activity build failed.

    ``str()`` is written for the agent that submitted the code, not for an operator. It says
    what to fix, and the agent retries with a corrected version.
    """


class PxcManifestInvalid(PxcBuildFailed):
    """The manifest breaks pxc-lib's schema or one of the build's own rules."""


class PxcCompileFailed(PxcBuildFailed):
    """``sandbox.js`` did not compile: a syntax error, or an import other than ``pxc:sandbox/*``."""


class PxcSmokeTestFailed(PxcBuildFailed):
    """The sandbox compiled but ``get_state`` failed under ``play`` or ``edit``."""


class PxcBuildTimedOut(PxcBuildFailed):
    """A build step outlived ``PXC_BUILD_TIMEOUT_SECONDS`` and was killed."""
