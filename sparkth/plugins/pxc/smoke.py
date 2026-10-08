"""Smoke-test a freshly built activity, run as ``python -m sparkth.plugins.pxc.smoke <dir>``.

The builder runs this in a child process. A sandbox stuck in a loop cannot be stopped from a
thread, but a process can be killed. It reads ``get_state`` under ``play`` and under ``edit``,
the two permissions a launch hands out, against throwaway in-memory storage.

Exit status 0 means it passed. On 1, stderr carries the sandbox's own error output (pxc-lib
passes the wasm's stderr through) followed by one summary line. The builder hands that text to
the agent.

A passing run leaves ``sandbox.wasm.bin`` beside the wasm: pxc-lib's compiled-component cache.
It moves with the activity, so the first learner launch skips compiling the component.
"""

import json
import logging
import sys
from pathlib import Path

from pxc.lib.field_store import MemoryKVStore
from pxc.lib.file_storage import MemoryFileStorage
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime

from sparkth.plugins.pxc.constants import PXC_SMOKE_CONTEXT_ID
from sparkth.plugins.pxc.exceptions import PxcSandboxFailure
from sparkth.plugins.pxc.runtime import read_state


def smoke_test(directory: Path) -> None:
    """Read the activity's state under each permission a launch can carry.

    Raises:
        PxcSandboxFailure: if the sandbox fails, or returns something other than a JSON object.
        json.JSONDecodeError: if ``get_state`` returns text that is not JSON.
    """
    for permission in (Permission.play, Permission.edit):
        runtime = ActivityRuntime(
            directory,
            MemoryKVStore(),
            MemoryFileStorage(),
            PXC_SMOKE_CONTEXT_ID,
            PXC_SMOKE_CONTEXT_ID,
            PXC_SMOKE_CONTEXT_ID,
            permission,
        )
        state: object = read_state(runtime)
        if not isinstance(state, dict):
            raise PxcSandboxFailure(
                f"get_state under {permission.value} must return a JSON object, not {type(state).__name__}"
            )


def main(argv: list[str]) -> int:
    """Smoke-test the activity directory named by ``argv[0]``, returning the exit status."""
    try:
        smoke_test(Path(argv[0]))
    except PxcSandboxFailure as err:
        print(f"get_state failed: {err}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as err:
        print(f"get_state failed: it must return JSON text ({err})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # pxc-lib logs a traceback on failure; stderr should carry only the sandbox's own error.
    logging.disable(logging.CRITICAL)
    sys.exit(main(sys.argv[1:]))
