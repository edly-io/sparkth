"""Run an activity's actions against a throwaway store, in this process or as a child process.

Every step shares one in-memory field store that starts at the manifest's defaults, and one
course, activity instance and learner, so a later step sees what an earlier one saved. A step
that fails records its error and the run goes on.

Run as ``python -m sparkth.plugins.pxc.scratch <activity_dir>``, it reads the steps from
``steps.json`` in its working directory and writes the report to ``result.json`` beside it. Every
error in a report is a manifest refusal or ``sandbox_error_text``, so none names a server path.
"""

import json
import logging
import sys
from pathlib import Path
from typing import TypedDict

from pxc.lib.field_store import MemoryKVStore
from pxc.lib.fields import FieldType
from pxc.lib.file_storage import MemoryFileStorage
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime

from sparkth.plugins.pxc.constants import PXC_SCRATCH_CONTEXT_ID, PXC_SCRATCH_PERMISSIONS
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcSandboxFailure
from sparkth.plugins.pxc.runtime import read_state, run_action


class ScratchStep(TypedDict):
    """One action to run: its name, its value and the permission it runs under."""

    action: str
    value: FieldType
    permission: str


class ScratchEvent(TypedDict):
    """One event an action sent, with its value parsed."""

    name: str
    value: FieldType
    permission: str


class StepOutcome(TypedDict):
    """What one step did: the events it sent, or why it failed."""

    action: str
    permission: str
    value: FieldType
    events: list[ScratchEvent]
    error: str | None


class StateOutcome(TypedDict):
    """``getState`` under one permission, or why it failed."""

    permission: str
    state: dict[str, FieldType] | None
    error: str | None


class ScratchReport(TypedDict):
    """Every step's outcome, then the state under each permission and the learner's stored fields."""

    steps: list[StepOutcome]
    state: list[StateOutcome]
    fields: dict[str, FieldType]


def scratch_runtime(directory: Path, store: MemoryKVStore, permission: Permission) -> ActivityRuntime:
    """A runtime for the activity in ``directory`` on ``store``, as the throwaway learner."""
    return ActivityRuntime(
        directory,
        store,
        MemoryFileStorage(),
        PXC_SCRATCH_CONTEXT_ID,
        PXC_SCRATCH_CONTEXT_ID,
        PXC_SCRATCH_CONTEXT_ID,
        permission,
    )


def run_step(directory: Path, store: MemoryKVStore, step: ScratchStep) -> StepOutcome:
    """Run one step on ``store``: its events, or its error when the manifest refuses it or the sandbox fails."""
    outcome = StepOutcome(
        action=step["action"], permission=step["permission"], value=step["value"], events=[], error=None
    )
    runtime = scratch_runtime(directory, store, Permission(step["permission"]))
    try:
        pending = run_action(runtime, step["action"], step["value"])
    except PxcActionRejected as err:
        outcome["error"] = str(err)
    except PxcSandboxFailure as err:
        outcome["error"] = err.error_text
    else:
        outcome["events"] = [
            ScratchEvent(name=event["name"], value=json.loads(event["value"]), permission=event["permission"])
            for event in pending
        ]
    return outcome


def read_scratch_state(directory: Path, store: MemoryKVStore, permission: Permission) -> StateOutcome:
    """``getState`` under ``permission`` on ``store``, or why it failed."""
    outcome = StateOutcome(permission=permission.value, state=None, error=None)
    try:
        state: object = read_state(scratch_runtime(directory, store, permission))
    except PxcSandboxFailure as err:
        outcome["error"] = err.error_text
    except json.JSONDecodeError as err:
        outcome["error"] = f"getState must return JSON text ({err})"
    else:
        if isinstance(state, dict):
            outcome["state"] = state
        else:
            outcome["error"] = f"getState must return a JSON object, not {type(state).__name__}"
    return outcome


def run_scratch(directory: Path, steps: list[ScratchStep]) -> ScratchReport:
    """Run ``steps`` in order on one fresh store, then read the state under each permission and the stored fields."""
    store = MemoryKVStore()
    outcomes = [run_step(directory, store, step) for step in steps]
    states = [read_scratch_state(directory, store, permission) for permission in PXC_SCRATCH_PERMISSIONS]
    fields: dict[str, FieldType] = scratch_runtime(directory, store, Permission.play).get_all_fields()
    return ScratchReport(steps=outcomes, state=states, fields=fields)


def main(argv: list[str]) -> int:
    """Run the steps in ``./steps.json`` against the activity in ``argv[0]`` and write ``./result.json``."""
    steps: list[ScratchStep] = json.loads(Path("steps.json").read_text(encoding="utf-8"))
    Path("result.json").write_text(json.dumps(run_scratch(Path(argv[0]), steps)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    # pxc-lib logs a traceback for every failure, and the report already carries each one.
    logging.disable(logging.CRITICAL)
    sys.exit(main(sys.argv[1:]))
