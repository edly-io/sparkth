"""Build an author's activity from the files an agent wrote, inside the web process."""

import asyncio
import os
import signal
from pathlib import Path

from pxc.lib.manifest_types import PxcActivityManifest
from pydantic import ValidationError

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_BUILD_ERROR_LIMIT
from sparkth.plugins.pxc.exceptions import PxcBuildTimedOut, PxcManifestInvalid

logger = get_logger(__name__)


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

    The step gets ``PXC_BUILD_TIMEOUT_SECONDS``. It starts in a session of its own, so its pid
    is also its process group, and a timeout kills grandchildren with it. node runs wizer as
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
        _kill_group(process.pid, step)
        await process.wait()
        raise PxcBuildTimedOut(
            f"{step} did not finish within {timeout} seconds. Look for a loop that never ends."
        ) from err
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
