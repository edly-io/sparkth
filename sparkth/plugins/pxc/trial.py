"""Run an author's steps against one of their activities in a child process, for the author's agent.

The child is ``python -m sparkth.plugins.pxc.scratch``, started through the builder's
``run_bounded``. It gets a bare environment and the build timeout, and its whole process group is
killed if it outlives that. Its working directory is a fresh temporary directory holding
``steps.json``, and it writes ``result.json`` there, never into the activity's own files.
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import cast

from pxc.lib.fields import FieldType

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.builder import run_bounded
from sparkth.plugins.pxc.exceptions import PxcTrialFailed
from sparkth.plugins.pxc.schemas import TrialStep
from sparkth.plugins.pxc.scratch.schemas import ScratchReport, ScratchStep

logger = get_logger(__name__)


async def run_trial(directory: Path, steps: list[TrialStep]) -> ScratchReport:
    """Run ``steps`` against the activity in ``directory`` on a throwaway store, in a child process.

    Raises:
        PxcTrialFailed: if the child exits with an error or writes no report. Its stderr is logged
            here only, since a traceback names server paths.
        PxcBuildTimedOut: if the child outlives ``PXC_BUILD_TIMEOUT_SECONDS``, naming the step it hung in.
    """
    # The child checks each value against the manifest, so a value of the wrong shape is that step's error.
    scratch_steps = [
        ScratchStep(action=step.action, value=cast(FieldType, step.value), permission=step.permission.value)
        for step in steps
    ]
    with tempfile.TemporaryDirectory() as work:
        (Path(work) / "steps.json").write_text(json.dumps(scratch_steps), encoding="utf-8")
        argv = [sys.executable, "-m", "sparkth.plugins.pxc.scratch", str(directory)]
        returncode, stderr = await run_bounded(argv, Path(work), "Running the activity")
        result = Path(work) / "result.json"
        if returncode != 0 or not result.is_file():
            logger.error("PXC trial run of %s exited %s without a report: %s", directory.name, returncode, stderr)
            raise PxcTrialFailed(
                "Running the activity stopped before it could report. This is not a problem with the steps."
            )
        report: ScratchReport = json.loads(result.read_text(encoding="utf-8"))
    return report
