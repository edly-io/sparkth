"""Assemble a PXC :class:`~pxc.lib.runtime.ActivityRuntime` for one launch.

Every entry point here is synchronous and CPU-bound: the sandbox runs WebAssembly on the
calling thread. Routes must call these from a worker thread, never on the event loop.
"""

from pathlib import Path

from pxc.lib.actions import ActionValidationError
from pxc.lib.capabilities import CapabilityError
from pxc.lib.events import EventValidationError
from pxc.lib.fields import FieldType, FieldValidationError
from pxc.lib.file_storage import LocalFileStorage
from pxc.lib.runtime import ActivityRuntime, AssetAccessError, PendingEvent
from pxc.lib.sandbox import SandboxRuntimeError

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_dir, state_file
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import (
    PXC_SANDBOX_ABORT_NOTICE,
    PXC_SANDBOX_OUTPUT_LIMIT,
    PXC_SANDBOX_SILENT_FAILURE,
)
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcSandboxFailure
from sparkth.plugins.pxc.field_store.sqlite import SqliteFieldStore
from sparkth.plugins.pxc.revisions import revision_dir
from sparkth.plugins.pxc.tokens import LaunchClaims

logger = get_logger(__name__)


def launch_dir(claims: LaunchClaims) -> Path:
    """The activity files a launch reads: the revision its token pins, else the live ones.

    Raises:
        PxcActivityNotFound: if the activity, or the revision the token pins, is not on disk.
    """
    if claims.revision is None:
        return activity_dir(claims.activity)
    return revision_dir(claims.activity, claims.revision)


def build_runtime(claims: LaunchClaims) -> ActivityRuntime:
    """Build the runtime for the launch these claims describe.

    Permission comes from the launch token's verified claims, not from the request: the
    signature is what makes it trustworthy. The LMS decides it, because only the LMS knows who
    may author the course.

    Raises:
        PxcActivityNotFound: if the claimed activity is neither bundled nor a generated
            activity on disk, or the revision the token pins is gone.
    """
    return ActivityRuntime(
        launch_dir(claims),
        SqliteFieldStore(state_file(claims.activity)),
        LocalFileStorage(get_pxc_settings().data_dir / "storage" / claims.activity),
        claims.activity_instance,
        claims.course_id,
        claims.user_id,
        claims.permission,
    )


def _sandbox_output(stderr: str) -> str:
    """What ``sandbox.js`` wrote to stderr, without blank lines, the abort notice or stack frames outside sandbox.js.

    Only its last ``PXC_SANDBOX_OUTPUT_LIMIT`` characters are kept, where a throw's message is, so
    a sandbox that logs in a loop cannot bury it.
    """
    output = "\n".join(
        line
        for line in stderr.splitlines()
        if line.strip()
        and not line.startswith(PXC_SANDBOX_ABORT_NOTICE)
        # A JS stack frame is indented "fn@file:line:col"; only sandbox.js's own frames are the author's.
        and not (line.startswith(" ") and "@" in line and "sandbox.js:" not in line)
    )
    return output if len(output) <= PXC_SANDBOX_OUTPUT_LIMIT else "..." + output[-PXC_SANDBOX_OUTPUT_LIMIT:]


def sandbox_error_text(err: SandboxRuntimeError) -> str:
    """Why the sandbox failed, with no server paths: safe for logs and the author's agent.

    A host call pxc-lib refused gives its own message, anything else gives what ``sandbox.js``
    printed: another cause, such as an ``OSError`` from file storage, can name a server path.
    """
    output = _sandbox_output(err.stderr)
    cause = err.__cause__
    if isinstance(cause, (FieldValidationError, AssetAccessError, CapabilityError, EventValidationError)):
        return f"{cause}\nsandbox.js output before it:\n{output}" if output else str(cause)
    return output or PXC_SANDBOX_SILENT_FAILURE


def read_state(runtime: ActivityRuntime) -> dict[str, FieldType]:
    """The activity state to hand the client.

    Raises:
        PxcSandboxFailure: if the activity's sandbox fails to produce it.
    """
    try:
        # pxc-lib ships no py.typed marker, so mypy sees get_state() as returning Any.
        state: dict[str, FieldType] = runtime.get_state()
    except SandboxRuntimeError as err:
        error_text = sandbox_error_text(err)
        logger.error(
            "PXC sandbox failed reading state for %s (course=%s, activity_instance=%s): %s",
            runtime.name,
            runtime.course_id,
            runtime.activity_id,
            error_text,
        )
        raise PxcSandboxFailure(f"Activity {runtime.name} failed to produce its state", error_text) from err
    return state


def run_action(runtime: ActivityRuntime, action_name: str, action_value: FieldType) -> list[PendingEvent]:
    """Run one action through the sandbox and return the events it produced.

    Callers hand the returned list to ``publish_events``; this function does no fan-out of its own.
    A failed action's pending events are discarded, so none reach a subscriber.

    Raises:
        PxcActionRejected: if the manifest does not accept this action or value.
        PxcSandboxFailure: if the sandbox failed; its error_text says how.
    """
    try:
        runtime.on_action_or_raise(action_name, action_value)
    except ActionValidationError as err:
        raise PxcActionRejected(str(err)) from err
    except SandboxRuntimeError as err:
        # Events sent before the throw must not ride along with this connection's next action.
        runtime.clear_pending_events()
        error_text = sandbox_error_text(err)
        logger.error(
            "PXC sandbox failed running %s on %s (course=%s, activity_instance=%s): %s",
            action_name,
            runtime.name,
            runtime.course_id,
            runtime.activity_id,
            error_text,
        )
        raise PxcSandboxFailure(f"Activity {runtime.name} failed to run {action_name}", error_text) from err
    # pxc-lib ships no py.typed marker, so mypy sees clear_pending_events() as returning Any.
    events: list[PendingEvent] = runtime.clear_pending_events()
    return events
