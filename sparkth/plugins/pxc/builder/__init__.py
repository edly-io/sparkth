"""Build an author's activity from the files an agent wrote, inside the web process.

The steps run in this order:

1. Validate the manifest.
2. Compile ``sandbox.js`` with componentize-js.
3. Smoke-test the activity in a child process: getState, then every action, under play and edit.
4. Publish the result as the activity's live revision, then record its row.

An update stages its files the same way, then checks the field changes against the live revision
and the activity's placement, publishes a new revision, clears a draft's state on a field change,
prunes old revisions and saves the title and description.

Every failure raises a ``PxcBuildFailed`` subclass whose message is written for the agent that
submitted the code, so it can fix the code and retry.

Containment. componentize-js runs the module's top-level code at compile time, inside wizer.
wizer sees one directory as its filesystem root: the process's cwd, whenever the source sits
under it. So each compile runs with its cwd set to a directory holding only ``sandbox.js``, and
an import can reach nothing but that file. A relative or absolute import of any server file fails
to resolve. That is also what limits a sandbox to ``pxc:sandbox/*`` imports: builtins, packages
and unknown interfaces fail to load the same way. node and the smoke test get only ``PATH`` and
``NO_COLOR`` as their environment, and only the end of their stderr is kept.

Both child processes run in a session of their own and are killed as a group on timeout or
cancellation. node runs wizer as a grandchild, and killing node alone leaves wizer running.
"""

import asyncio
import json
import os
import shutil
import signal
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import cast
from uuid import UUID

from pxc.lib.manifest_types import PxcActivityManifest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_dir, state_file
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import (
    PXC_COMPILE_TOOLCHAIN_MISSING,
    PXC_SANDBOX_WIT,
    PXC_SMOKE_CUT_NOTICE,
    PXC_STEP_PREFIX,
)
from sparkth.plugins.pxc.exceptions import (
    PxcBuildTimedOut,
    PxcCompileFailed,
    PxcFieldsFrozen,
    PxcManifestInvalid,
    PxcSmokeTestFailed,
)
from sparkth.plugins.pxc.field_changes import incompatible_field_changes
from sparkth.plugins.pxc.field_store.sqlite import SqliteFieldStore
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.revisions import prune_revisions, publish_revision, remove_activity_files
from sparkth.plugins.pxc.schemas import ActivitySource
from sparkth.plugins.pxc.store import get_owned_activity, insert_activity, update_activity_details

logger = get_logger(__name__)

# TODO: move activity builds to a dedicated worker container to make this scale.
_BUILD_SLOTS = asyncio.Semaphore(get_pxc_settings().build_concurrency)


def _manifest_rule_violations(manifest: PxcActivityManifest) -> list[str]:
    """What a schema-valid manifest still gets wrong for a generated activity.

    An activity is exactly its two scripts, so ``assets`` is refused. The sandbox world imports
    only ``pxc:sandbox/state``, so a declared capability could never be used. The file names
    are the ones the build writes.
    """
    violations = []
    if manifest.assets:
        violations.append('"assets" is not supported: an activity is exactly ui.js and sandbox.js')
    if manifest.capabilities:
        violations.append('"capabilities" is not supported: the sandbox can import only pxc:sandbox/state')
    if manifest.ui != "ui.js":
        violations.append('"ui" must be "ui.js"')
    if manifest.sandbox != "sandbox.wasm":
        violations.append('"sandbox" must be "sandbox.wasm"')
    return violations


def validate_manifest(manifest: dict[str, object], activity_id: str) -> dict[str, object]:
    """The manifest to write for this activity, with ``name`` set to its id.

    The server owns the name: it is the id the activity is stored and launched under.

    Raises:
        PxcManifestInvalid: naming every problem found, for the agent to fix.
    """
    named = {**manifest, "name": activity_id}
    try:
        parsed = PxcActivityManifest.model_validate(named)
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'manifest'}: {error['msg']}"
            for error in err.errors(include_url=False)
        )
        logger.info("Refused the manifest of PXC activity %s: %s", activity_id, problems)
        raise PxcManifestInvalid(
            f"manifest.json does not match the PXC manifest schema: {problems}"[: get_pxc_settings().build_error_limit]
        ) from err
    violations = _manifest_rule_violations(parsed)
    if violations:
        raise PxcManifestInvalid("manifest.json breaks the build's rules: " + "; ".join(violations))
    return named


def _kill_group(pid: int, step: str) -> None:
    """Kill a step that is still running, and every process it started."""
    logger.warning("PXC build step %r is still running; killing its process group %s", step, pid)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        logger.info("PXC build step %r exited just as it was being killed", step)


async def _read_tail(stream: asyncio.StreamReader, tail: bytearray) -> None:
    """Read ``stream`` to its end into ``tail``, keeping only its last ``PXC_BUILD_STDERR_LIMIT_BYTES``.

    ``tail`` holds what was read so far even when the read is cancelled.
    """
    limit = get_pxc_settings().build_stderr_limit_bytes
    while chunk := await stream.read(limit):
        tail += chunk
        del tail[:-limit]


def _timed_out_message(step: str, timeout: int, stdout: bytearray, stderr: bytearray) -> str:
    """Name the step that timed out, the last step it named on stdout and what it wrote to stderr."""
    named = [
        line.removeprefix(PXC_STEP_PREFIX)
        for line in stdout.decode("utf-8", "replace").splitlines()
        if line.startswith(PXC_STEP_PREFIX)
    ]
    running = f" while running {named[-1]}" if named else ""
    message = f"{step} did not finish within {timeout} seconds{running}. Look for a loop that never ends."
    reported = stderr.decode("utf-8", "replace").strip()
    if reported:
        message += f"\nBefore that, it reported:\n{reported}"
    return message[: get_pxc_settings().build_error_limit]


async def run_bounded(argv: list[str], cwd: Path, step: str) -> tuple[int, str]:
    """Run one build step to completion and return its exit code and the end of its stderr.

    The step runs the agent's code, so it gets only ``_bare_env()`` as its environment. Its
    stdout and stderr are drained as they are written, keeping the last
    ``PXC_BUILD_STDERR_LIMIT_BYTES`` of each, so a step flooding them never blocks on a full
    pipe or grows this process's memory.

    The step gets ``PXC_BUILD_TIMEOUT_SECONDS``. Whenever this exits with the step still
    running (timeout, cancellation), the step's whole group is killed and reaped. It starts
    in a session of its own, so its pid is also its process group and the kill reaches
    grandchildren. node runs wizer as one, and wizer is where a compile-time loop would spin.

    A step may name what it is running on a stdout line starting with ``PXC_STEP_PREFIX``, so a
    timeout can say where it hung. Any other stdout, such as a compile's console output, is ignored.

    Raises:
        PxcBuildTimedOut: if the step outlives the timeout, with the last step it named on stdout
            and the stderr it wrote until then.
        asyncio.CancelledError: propagated after the step is killed, if the caller is cancelled.
    """
    timeout = get_pxc_settings().build_timeout_seconds
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=_bare_env(),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdout is not None and process.stderr is not None  # piped above
    stdout, stderr = bytearray(), bytearray()
    try:
        _, _, returncode = await asyncio.wait_for(
            asyncio.gather(_read_tail(process.stdout, stdout), _read_tail(process.stderr, stderr), process.wait()),
            timeout,
        )
    except TimeoutError as err:
        raise PxcBuildTimedOut(_timed_out_message(step, timeout, stdout, stderr)) from err
    finally:
        if process.returncode is None:
            _kill_group(process.pid, step)
            await process.wait()
    return returncode, stderr.decode("utf-8", "replace")


def _bare_env() -> dict[str, str]:
    """The environment for a child that runs the agent's code: no secret of this process reaches it."""
    return {"PATH": os.environ.get("PATH", os.defpath), "NO_COLOR": "1"}


def _toolchain_missing(detail: object) -> PxcCompileFailed:
    """Log that the toolchain cannot run, and the error that tells the agent it is not at fault."""
    logger.error("PXC build toolchain is not usable at %s: %s", get_pxc_settings().toolchain_dir, detail)
    return PxcCompileFailed(
        "The activity build toolchain is not installed on this server. This is not a problem with the code."
    )


async def compile_sandbox(sandbox_js: str, compile_dir: Path, output: Path) -> None:
    """Compile ``sandbox_js`` with the toolchain's ``compile.mjs`` into the component at ``output``.

    ``compile_dir`` must be empty and absolute. The compile runs there, so it is the module's
    whole filesystem at compile time, when its top-level code runs: componentize-js maps the
    process cwd as the root a source under it can import from. ``output`` lies outside it.

    ``compile.mjs`` writes only the cause of a failure, so its stderr goes to the agent as it is,
    keeping the last ``PXC_BUILD_ERROR_LIMIT`` characters.

    Raises:
        PxcCompileFailed: with the cause of the failure, or if the toolchain is missing.
        PxcBuildTimedOut: if the compile outlives the timeout.
    """
    script = get_pxc_settings().toolchain_dir.resolve() / "compile.mjs"
    if not script.is_file():
        raise _toolchain_missing(f"{script} does not exist")
    (compile_dir / "sandbox.js").write_text(sandbox_js, encoding="utf-8")
    argv = ["node", str(script), "sandbox.js", str(PXC_SANDBOX_WIT), str(output)]
    try:
        returncode, stderr = await run_bounded(argv, compile_dir, "Compiling sandbox.js")
    except (FileNotFoundError, PermissionError) as err:
        raise _toolchain_missing(err) from err
    if returncode == PXC_COMPILE_TOOLCHAIN_MISSING:
        raise _toolchain_missing(stderr.strip())
    if returncode != 0:
        raise PxcCompileFailed(
            f"sandbox.js failed to compile:\n{stderr.strip()[-get_pxc_settings().build_error_limit :]}"
        )


async def smoke_test_activity(directory: Path) -> None:
    """Run the smoke test (``scratch/smoke.py``) on ``directory`` in a child process.

    The child runs inside ``directory`` and is handed it as ``.``, so no server path can appear
    in what it reports. Its report lists the failing steps in order, so it keeps its start, up to
    ``PXC_BUILD_ERROR_LIMIT`` characters, and ends with ``PXC_SMOKE_CUT_NOTICE`` when more were cut.

    Raises:
        PxcSmokeTestFailed: naming the failing steps with the sandbox's own error text.
        PxcBuildTimedOut: if the smoke test does not finish within the timeout, naming the step
            it hung in and the failing steps before it.
    """
    argv = [sys.executable, "-m", "sparkth.plugins.pxc.scratch.smoke", "."]
    returncode, stderr = await run_bounded(argv, directory, "The smoke test")
    if returncode != 0:
        failures, limit = stderr.strip(), get_pxc_settings().build_error_limit
        if len(failures) > limit:
            failures = failures[:limit] + PXC_SMOKE_CUT_NOTICE
        raise PxcSmokeTestFailed(f"sandbox.js compiled, but running the activity failed:\n{failures}")


async def stage_activity(work: Path, manifest: dict[str, object], source: ActivitySource) -> Path:
    """Compile and smoke-test one activity inside ``work``, returning its finished directory.

    The compile gets a fresh directory of its own holding nothing but ``sandbox.js``, removed
    when the compile ends. The activity's files go in a separate directory, which is what is
    smoke-tested and moved into place.

    Raises:
        PxcCompileFailed, PxcSmokeTestFailed, PxcBuildTimedOut: from the step that failed.
    """
    staged = work / "activity"
    staged.mkdir()
    with tempfile.TemporaryDirectory(dir=work.parent) as compile_dir:
        await compile_sandbox(source.sandbox_js, Path(compile_dir), staged / "sandbox.wasm")
    (staged / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (staged / "ui.js").write_text(source.ui_js, encoding="utf-8")
    (staged / "sandbox.js").write_text(source.sandbox_js, encoding="utf-8")
    shutil.copyfile(PXC_SANDBOX_WIT, staged / "pxc.wit")
    await smoke_test_activity(staged)
    return staged


def _builds_dir() -> Path:
    """The build scratch directory, created on first use, on the activities' filesystem."""
    builds = get_pxc_settings().data_dir.resolve() / "builds"
    builds.mkdir(parents=True, exist_ok=True)
    return builds


async def build_activity(source: ActivitySource, owner_user_id: int) -> PxcActivity:
    """Build one activity from an agent's files, store it, and return its row.

    The work directory sits under ``PXC_DATA_DIR/builds``, on the same filesystem as the
    activities, so publishing a finished build is a rename. Any failure removes the work
    directory, plus the activity's link and revision if recording the row fails, and writes no row.

    Raises:
        PxcBuildFailed: a ``PxcManifestInvalid``, ``PxcCompileFailed``, ``PxcSmokeTestFailed``
            or ``PxcBuildTimedOut`` whose message tells the agent what to fix.
    """
    activity = PxcActivity(owner_user_id=owner_user_id, title=source.title, description=source.description)
    activity_id = str(activity.id)
    manifest = validate_manifest(source.manifest, activity_id)
    builds = _builds_dir()
    async with _BUILD_SLOTS:
        with tempfile.TemporaryDirectory(dir=builds) as work:
            staged = await stage_activity(Path(work), manifest, source)
            publish_revision(staged, activity_id)
    try:
        async with session_scope() as session:
            await insert_activity(session, activity)
    except SQLAlchemyError, asyncio.CancelledError:
        logger.warning("Recording PXC activity %s failed; removing its built files", activity_id)
        remove_activity_files(activity_id)
        raise
    logger.info("Built PXC activity %s for user %s", activity_id, owner_user_id)
    return activity


async def update_activity(activity_id: UUID, source: ActivitySource, owner_user_id: int) -> None:
    """Rebuild one of the owner's activities from an agent's files, in place under its id.

    Placement and the live fields are read after staging, so a placement made during the compile
    counts. A placed activity refuses an incompatible field change; a draft accepts it and has its
    state file cleared. Nothing is published until every check passes. A later failure (clearing
    the state file, saving the title and description) is logged and raised, leaving the new
    revision live.

    Raises:
        PxcActivityNotFound: if the caller does not own the activity, or its files are gone.
        PxcFieldsFrozen: if the activity is placed and the update removes or changes a field.
        PxcBuildFailed: any other build failure, whose message tells the agent what to fix.
    """
    name = str(activity_id)
    async with session_scope() as session:
        await get_owned_activity(session, activity_id, owner_user_id)
    # Refuses an activity whose files are gone, before any build runs.
    activity_dir(name)
    manifest = validate_manifest(source.manifest, name)
    async with _BUILD_SLOTS:
        with tempfile.TemporaryDirectory(dir=_builds_dir()) as work:
            staged = await stage_activity(Path(work), manifest, source)
            changes = await _checked_field_changes(activity_id, owner_user_id, manifest)
            publish_revision(staged, name)
    if changes:
        _clear_preview_state(name)
    prune_revisions(name, get_pxc_settings().revision_retention_seconds)
    try:
        async with session_scope() as session:
            await update_activity_details(session, activity_id, source.title, source.description)
    except SQLAlchemyError as err:
        logger.error("PXC activity %s was republished but its title and description were not saved: %s", name, err)
        raise
    logger.info("Updated PXC activity %s for user %s", name, owner_user_id)


def _clear_preview_state(name: str) -> None:
    """Clear a draft's state file, logging and re-raising if it cannot be cleared."""
    try:
        SqliteFieldStore(state_file(name)).clear()
    except sqlite3.Error as err:
        logger.error("PXC activity %s has its new revision live but its preview state was not cleared: %s", name, err)
        raise


async def _checked_field_changes(activity_id: UUID, owner_user_id: int, manifest: dict[str, object]) -> list[str]:
    """The field changes ``manifest`` makes to the live activity, refused if the activity is placed.

    Raises:
        PxcActivityNotFound: if the activity is not the caller's, or its files are gone.
        PxcFieldsFrozen: if the activity is placed and there is any change.
    """
    async with session_scope() as session:
        activity = await get_owned_activity(session, activity_id, owner_user_id)
    live = json.loads((activity_dir(str(activity_id)) / "manifest.json").read_text(encoding="utf-8"))
    changes = incompatible_field_changes(
        cast(dict[str, dict[str, object]], live.get("fields") or {}),
        cast(dict[str, dict[str, object]], manifest.get("fields") or {}),
    )
    if changes and activity.placed_at is not None:
        logger.info("Refused an update of placed PXC activity %s: %s", activity_id, "; ".join(changes))
        raise PxcFieldsFrozen(
            "Nothing was updated. This activity is already placed in a course, so the data it stores "
            f"cannot change: {'; '.join(changes)}. Do not build a new activity yet. Tell the author "
            "that this change needs a new activity, that courses using this one keep it until they "
            "place the new one, and ask whether to build it under a new title."
        )
    return changes
