"""Domain exceptions for the PXC plugin.

None of these carries an HTTP status. ``plugin.py`` registers each against exactly one status
with ``register_exception_handler``, so the routes just raise and the framework renders the
response.
"""


class PxcActivityNotFound(Exception):
    """No bundled activity type goes by this name."""


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
