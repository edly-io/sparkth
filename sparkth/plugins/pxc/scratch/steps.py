"""Run steps and read state on one throwaway store, naming each on a progress stream first.

Every step shares one in-memory field store that starts at the manifest's defaults, so a later
step sees what an earlier one saved. A step that fails records its error and the run goes on.
Every error is a manifest refusal or ``sandbox_error_text``, so none names a server path.
"""

import json
from pathlib import Path
from typing import TextIO

from pxc.lib.field_store import MemoryKVStore
from pxc.lib.fields import FieldType
from pxc.lib.permission import Permission

from sparkth.plugins.pxc.constants import PXC_SCRATCH_PERMISSIONS
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcSandboxFailure
from sparkth.plugins.pxc.runtime import read_state, run_action
from sparkth.plugins.pxc.scratch.runtime import scratch_runtime
from sparkth.plugins.pxc.scratch.schemas import ScratchEvent, ScratchReport, ScratchStep, StateOutcome, StepOutcome


def run_step(directory: Path, store: MemoryKVStore, step: ScratchStep, progress: TextIO) -> StepOutcome:
    """Run one step on ``store``: its events, or its error when the manifest refuses it or the sandbox fails."""
    print(f"{step['action']} as {step['permission']}", file=progress, flush=True)
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


def read_scratch_state(directory: Path, store: MemoryKVStore, permission: Permission, progress: TextIO) -> StateOutcome:
    """``getState`` under ``permission`` on ``store``, or why it failed."""
    print(f"getState as {permission.value}", file=progress, flush=True)
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


def run_scratch(directory: Path, steps: list[ScratchStep], progress: TextIO) -> ScratchReport:
    """Run ``steps`` in order on one fresh store, then read the state under each permission and the stored fields."""
    store = MemoryKVStore()
    outcomes = [run_step(directory, store, step, progress) for step in steps]
    states = [read_scratch_state(directory, store, permission, progress) for permission in PXC_SCRATCH_PERMISSIONS]
    fields: dict[str, FieldType] = scratch_runtime(directory, store, Permission.play).get_all_fields()
    return ScratchReport(steps=outcomes, state=states, fields=fields)
