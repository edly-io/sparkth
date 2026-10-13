"""The stdout a scratch run names its steps on, kept clear of the sandbox's own output."""

import os
from typing import TextIO


def progress_stream() -> TextIO:
    """This process's stdout for naming the steps, with file descriptor 1 pointed at /dev/null.

    The sandbox writes its console output to file descriptor 1, so it cannot mix into the step names.
    """
    progress = os.fdopen(os.dup(1), "w")
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    os.close(null)
    return progress
