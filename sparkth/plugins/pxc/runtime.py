"""Assemble a PXC :class:`~pxc.lib.runtime.ActivityRuntime` for one launch.

The runtime is built per request from the launch token's claims: which activity type, which
placement, which learner. ``pxc-lib``'s runtime is used unmodified — the plugin only supplies
the two backends it depends on, a :class:`~sparkth.plugins.pxc.field_store.SqliteFieldStore`
over the activity type's state file and a local file storage directory.

Every entry point here is synchronous and CPU-bound: the sandbox runs WebAssembly on the
calling thread. Routes must call these from a worker thread, never on the event loop.
"""

from pxc.lib.actions import ActionValidationError
from pxc.lib.fields import FieldType
from pxc.lib.file_storage import LocalFileStorage
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime, PendingEvent
from pxc.lib.sandbox import SandboxRuntimeError

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_dir, state_file
from sparkth.plugins.pxc.constants import PXC_DATA_DIR
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcSandboxFailure
from sparkth.plugins.pxc.field_store import SqliteFieldStore
from sparkth.plugins.pxc.tokens import LaunchClaims

logger = get_logger(__name__)


def build_runtime(claims: LaunchClaims) -> ActivityRuntime:
    """Build the runtime for the launch these claims describe.

    Permission is fixed to ``play``. It is never read from the request: a learner opening a
    unit may answer, and nothing in this slice grants ``edit``.

    Raises:
        PxcActivityNotFound: if the claimed activity type is not bundled.
    """
    return ActivityRuntime(
        activity_dir(claims.activity),
        SqliteFieldStore(state_file(claims.activity)),
        LocalFileStorage(PXC_DATA_DIR / "storage" / claims.activity),
        claims.placement,
        claims.course_id,
        claims.user_id,
        Permission.play,
    )


def read_state(runtime: ActivityRuntime) -> dict[str, FieldType]:
    """The activity state to hand the client.

    Raises:
        PxcSandboxFailure: if the activity's sandbox fails to produce it.
    """
    try:
        # pxc-lib ships no py.typed marker, so mypy sees get_state() as returning Any.
        state: dict[str, FieldType] = runtime.get_state()
    except SandboxRuntimeError as err:
        logger.error(
            "PXC sandbox failed reading state for %s (course=%s, placement=%s): %s",
            runtime.name,
            runtime.course_id,
            runtime.activity_id,
            err,
        )
        raise PxcSandboxFailure(f"Activity {runtime.name} failed to produce its state") from err
    return state


def run_action(runtime: ActivityRuntime, action_name: str, action_value: FieldType) -> list[PendingEvent]:
    """Run one action through the sandbox and return the events it produced.

    The events come back from the same call, which is why this slice needs no polling route and
    no WebSocket.

    Raises:
        PxcActionRejected: if the manifest does not accept this action or value.
        PxcSandboxFailure: if the sandbox itself failed — currently unreachable, see below.

    The ``SandboxRuntimeError`` clause is dormant, not dead. ``ActivityRuntime.on_action``
    catches that exception internally and only logs it, carrying the upstream comment "It's OK
    to ignore on-action errors, but we should report errors to the frontend". So a sandbox that
    crashes mid-action currently yields no events and no error rather than a 502. ``get_state``
    does re-raise, so ``read_state``'s equivalent clause is live. Keep this one: it costs
    nothing and becomes correct the moment upstream acts on that comment.
    """
    try:
        runtime.on_action(action_name, action_value)
    except ActionValidationError as err:
        raise PxcActionRejected(str(err)) from err
    except SandboxRuntimeError as err:
        # Unreachable today: on_action catches this internally and only logs it, so the raise
        # below never runs until pxc-lib starts letting it propagate. Kept for when it does.
        logger.error(
            "PXC sandbox failed running %s on %s (course=%s, placement=%s): %s",
            action_name,
            runtime.name,
            runtime.course_id,
            runtime.activity_id,
            err,
        )
        raise PxcSandboxFailure(f"Activity {runtime.name} failed to run {action_name}") from err
    # pxc-lib ships no py.typed marker, so mypy sees clear_pending_events() as returning Any.
    events: list[PendingEvent] = runtime.clear_pending_events()
    return events
