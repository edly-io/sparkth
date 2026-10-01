"""Build an author's activity from the files an agent wrote, inside the web process.

The steps run in this order:

1. Validate the manifest.
2. Compile ``sandbox.js`` with componentize-js.
3. Smoke-test ``get_state`` in a child process.
4. Move the result to ``PXC_DATA_DIR/activities/<id>/`` and record its row.

Every failure raises a ``PxcBuildFailed`` subclass whose message is written for the agent that
submitted the code, so it can fix the code and retry.

Containment. componentize-js runs the module's top-level code at compile time, inside wizer.
wizer sees one directory as its filesystem root: the process's cwd, whenever the source sits
under it. So each compile runs with its cwd set to a directory holding only ``sandbox.js``, and
an import can reach nothing but that file. A relative or absolute import of any server file fails
to resolve. That is also what limits a sandbox to ``pxc:sandbox/*`` imports: builtins, packages
and unknown interfaces fail to load the same way. node and the smoke test get only ``PATH`` and ``NO_COLOR``
as their environment.

Both child processes run in a session of their own and are killed as a group on timeout. node
runs wizer as a grandchild, and killing node alone leaves wizer running.
"""

import asyncio
import json
import os
import shutil
import signal
import sys
import tempfile
from pathlib import Path

from pxc.lib.manifest_types import PxcActivityManifest
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import generated_activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_BUILD_ERROR_LIMIT, PXC_SANDBOX_WIT
from sparkth.plugins.pxc.exceptions import PxcBuildTimedOut, PxcCompileFailed, PxcManifestInvalid, PxcSmokeTestFailed
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.schemas import ActivitySource
from sparkth.plugins.pxc.store import insert_activity

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
            f"manifest.json does not match the PXC manifest schema: {problems}"[:PXC_BUILD_ERROR_LIMIT]
        ) from err
    violations = _manifest_rule_violations(parsed)
    if violations:
        raise PxcManifestInvalid("manifest.json breaks the build's rules: " + "; ".join(violations))
    return named


def _kill_group(pid: int, step: str) -> None:
    """Kill a timed-out step and every process it started."""
    logger.warning("PXC build step %r timed out; killing its process group %s", step, pid)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        logger.info("PXC build step %r exited just as its timeout fired", step)


async def run_bounded(argv: list[str], cwd: Path, step: str, env: dict[str, str] | None) -> tuple[int, str]:
    """Run one build step to completion and return its exit code and stderr.

    The step gets ``PXC_BUILD_TIMEOUT_SECONDS``. Whenever this exits with the step still
    running (timeout, cancellation), the step's whole group is killed and reaped.
    It starts in a session of its own, so its pid is also its process group and the kill
    reaches grandchildren. node runs wizer as
    one, and wizer is where a compile-time loop would spin. ``env`` of ``None`` inherits this
    process's environment.

    Raises:
        PxcBuildTimedOut: if the step outlives the timeout.
    """
    timeout = get_pxc_settings().build_timeout_seconds
    process = await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError as err:
        raise PxcBuildTimedOut(
            f"{step} did not finish within {timeout} seconds. Look for a loop that never ends."
        ) from err
    finally:
        if process.returncode is None:
            _kill_group(process.pid, step)
            await process.wait()
    return await process.wait(), stderr.decode("utf-8", "replace")


def agent_error(stderr: str, build_dir: Path) -> str:
    """A step's stderr cut down to what helps the agent fix its code.

    Lines from the toolchain's own stack (``    at`` frames and paths into ``node_modules``)
    say where the compiler failed, not where the activity did. The build directory's path is
    noise to the agent. What remains is capped at ``PXC_BUILD_ERROR_LIMIT`` characters, keeping
    the end, where the cause is.
    """
    kept = [line for line in stderr.splitlines() if not line.startswith("    at ") and "/node_modules/" not in line]
    text = "\n".join(kept).replace(f"{build_dir}/", "").replace(str(build_dir), "").strip()
    return text[-PXC_BUILD_ERROR_LIMIT:]


def _bare_env() -> dict[str, str]:
    """The environment for a child that runs the agent's code: no secret of this process reaches it."""
    return {"PATH": os.environ.get("PATH", os.defpath), "NO_COLOR": "1"}


async def compile_sandbox(sandbox_js: str, compile_dir: Path, output: Path) -> None:
    """Compile ``sandbox_js`` with componentize-js into the component at ``output``.

    ``compile_dir`` must be empty and absolute. The compile runs there, so it is the module's
    whole filesystem at compile time, when its top-level code runs: componentize-js maps the
    process cwd as the root a source under it can import from. ``output`` lies outside it.

    Raises:
        PxcCompileFailed: with the compiler's trimmed stderr, or if the toolchain is missing.
        PxcBuildTimedOut: if the compile outlives the timeout.
    """
    (compile_dir / "sandbox.js").write_text(sandbox_js, encoding="utf-8")
    compiler = get_pxc_settings().toolchain_dir.resolve() / "node_modules" / ".bin" / "componentize-js"
    argv = [str(compiler), "sandbox.js", "--wit", str(PXC_SANDBOX_WIT), "--world-name", "activity"]
    argv += ["--disable", "http", "--disable", "fetch-event", "-o", str(output)]
    try:
        returncode, stderr = await run_bounded(argv, compile_dir, "Compiling sandbox.js", _bare_env())
    except (FileNotFoundError, PermissionError) as err:
        logger.error("PXC build toolchain is not usable at %s: %s", compiler, err)
        raise PxcCompileFailed(
            "The activity build toolchain is not installed on this server. This is not a problem with the code."
        ) from err
    if returncode != 0:
        raise PxcCompileFailed(f"sandbox.js failed to compile:\n{agent_error(stderr, compile_dir)}")


async def smoke_test_activity(directory: Path) -> None:
    """Run ``get_state`` under ``play`` and ``edit`` in a child process.

    Raises:
        PxcSmokeTestFailed: with the sandbox's own error output, trimmed.
        PxcBuildTimedOut: if ``get_state`` does not return within the timeout.
    """
    argv = [sys.executable, "-m", "sparkth.plugins.pxc.smoke", str(directory)]
    returncode, stderr = await run_bounded(argv, directory, "The get_state smoke test", _bare_env())
    if returncode != 0:
        raise PxcSmokeTestFailed(f"sandbox.js compiled, but get_state failed:\n{agent_error(stderr, directory)}")


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


async def build_activity(source: ActivitySource, owner_user_id: int) -> PxcActivity:
    """Build one activity from an agent's files, store it, and return its row.

    The work directory sits under ``PXC_DATA_DIR/builds``, on the same filesystem as the
    activities, so moving a finished build into place is an atomic rename. Any failure removes
    the work directory (and the moved files, if recording the row fails) and writes no row.

    Raises:
        PxcBuildFailed: a ``PxcManifestInvalid``, ``PxcCompileFailed``, ``PxcSmokeTestFailed``
            or ``PxcBuildTimedOut`` whose message tells the agent what to fix.
    """
    activity = PxcActivity(owner_user_id=owner_user_id, title=source.title, description=source.description)
    activity_id = str(activity.id)
    manifest = validate_manifest(source.manifest, activity_id)
    builds = get_pxc_settings().data_dir.resolve() / "builds"
    builds.mkdir(parents=True, exist_ok=True)
    async with _BUILD_SLOTS:
        with tempfile.TemporaryDirectory(dir=builds) as work:
            staged = await stage_activity(Path(work), manifest, source)
            target = generated_activity_dir(activity_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            staged.rename(target)
    try:
        async with session_scope() as session:
            await insert_activity(session, activity)
    except SQLAlchemyError, asyncio.CancelledError:
        logger.warning("Recording PXC activity %s failed; removing its built files", activity_id)
        shutil.rmtree(generated_activity_dir(activity_id), ignore_errors=True)
        raise
    logger.info("Built PXC activity %s for user %s", activity_id, owner_user_id)
    return activity
