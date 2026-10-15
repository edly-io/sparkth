"""Run an agent's steps, as ``python -m sparkth.plugins.pxc.scratch <activity_dir>``.

The steps come from ``steps.json`` in the working directory, and the report goes to
``result.json`` beside it.
"""

import json
import logging
import sys
from pathlib import Path
from typing import TextIO

from sparkth.plugins.pxc.scratch.progress import progress_stream
from sparkth.plugins.pxc.scratch.schemas import ScratchStep
from sparkth.plugins.pxc.scratch.steps import run_scratch


def main(argv: list[str], progress: TextIO) -> int:
    """Run the steps in ``./steps.json`` against the activity in ``argv[0]`` and write ``./result.json``."""
    steps: list[ScratchStep] = json.loads(Path("steps.json").read_text(encoding="utf-8"))
    Path("result.json").write_text(json.dumps(run_scratch(Path(argv[0]), steps, progress)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    # pxc-lib logs a traceback for every failure, and the report already carries each one.
    logging.disable(logging.CRITICAL)
    sys.exit(main(sys.argv[1:], progress_stream()))
