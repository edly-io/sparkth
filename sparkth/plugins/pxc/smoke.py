"""Smoke-test a freshly built activity, run as ``python -m sparkth.plugins.pxc.smoke <dir>``.

The builder runs this in a child process. A sandbox stuck in a loop cannot be stopped from a
thread, but a process can be killed. On a throwaway store, it does the following:

1. Reads ``getState`` under ``play`` and ``edit``.
2. Runs ``config.save`` as ``edit`` with the field defaults.
3. Runs every other declared action as ``play`` and as ``edit``, with the simplest value its
   schema accepts.
4. Reads ``getState`` under both permissions again.

Each check is named on its own line of stdout before it runs, and each failure goes to stderr as
soon as it is found, so a check that never ends is named and the failures before it are kept. The
sandbox's own stdout is discarded, so it cannot mix into those lines.

Exit status 0 means every step passed. On 1, stderr carries one entry per failed step: the step,
the sandbox's own error text (the message, then ``Stack:`` and its frames, so it can span several
lines) and the value, cut short when long. The builder hands this to the agent.

A passing run leaves ``sandbox.wasm.bin`` beside the wasm: pxc-lib's compiled-component cache.
It moves with the activity, so the first learner launch skips compiling the component.
"""

import json
import logging
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

from pxc.lib.actions import ActionChecker, ActionValidationError
from pxc.lib.field_store import MemoryKVStore
from pxc.lib.fields import FieldChecker, FieldType
from pxc.lib.manifest_types import (
    ArrayType,
    BooleanType,
    IntegerType,
    LogField,
    NumberType,
    ObjectType,
    PxcActivityManifest,
    StringType,
)
from pxc.lib.permission import Permission

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.constants import (
    PXC_CONFIG_SAVE_ACTION,
    PXC_SAMPLE_VALUES,
    PXC_SCRATCH_PERMISSIONS,
    PXC_SMOKE_VALUE_LIMIT,
)
from sparkth.plugins.pxc.scratch import (
    ScratchStep,
    StepOutcome,
    read_scratch_state,
    run_step,
)

logger = get_logger(__name__)


def sample_value(schema: IntegerType | NumberType | StringType | BooleanType | ArrayType | ObjectType) -> FieldType:
    """The simplest value ``schema`` accepts: 0, "", false, [], or an object of its properties' samples."""
    if isinstance(schema, ArrayType):
        return []
    if isinstance(schema, ObjectType):
        return {key: sample_value(prop.root) for key, prop in schema.properties.items()}
    return PXC_SAMPLE_VALUES[schema.type]


def _default_or(fields: FieldChecker, key: str, sample: FieldType) -> FieldType:
    """The default of the field named ``key``, or ``sample`` when there is no such field or it is a log."""
    if key not in fields.field_names or isinstance(fields.get_definition(key), LogField):
        return sample
    return fields.get_default(key)


def config_save_value(manifest: PxcActivityManifest) -> FieldType:
    """``config.save``'s sample, with each property named after a field set to that field's default.

    A log field has no default to merge, so its property keeps the plain sample.

    The plain sample is used instead when those defaults do not fit the action's own schema, so a
    valid activity is never refused over a default.
    """
    sample = sample_value(manifest.actions[PXC_CONFIG_SAVE_ACTION].root)
    if not isinstance(sample, dict):
        return sample
    fields = FieldChecker(manifest.fields)
    merged = {key: _default_or(fields, key, value) for key, value in sample.items()}
    try:
        ActionChecker(manifest.actions).validate(PXC_CONFIG_SAVE_ACTION, merged)
    except ActionValidationError as err:
        logger.info("The field defaults do not fit config.save's schema, so it gets a plain sample: %s", err)
        return sample
    return merged


def smoke_steps(manifest: PxcActivityManifest) -> list[ScratchStep]:
    """``config.save`` as ``edit`` when declared, then every other action as ``play`` and as ``edit``."""
    actions = manifest.actions or {}
    steps: list[ScratchStep] = []
    if PXC_CONFIG_SAVE_ACTION in actions:
        steps.append(ScratchStep(action=PXC_CONFIG_SAVE_ACTION, value=config_save_value(manifest), permission="edit"))
    for name, schema in actions.items():
        if name != PXC_CONFIG_SAVE_ACTION:
            steps.extend(
                ScratchStep(action=name, value=sample_value(schema.root), permission=permission.value)
                for permission in PXC_SCRATCH_PERMISSIONS
            )
    return steps


def _cut(text: str) -> str:
    """``text``, ended with an ellipsis when it is over the value limit."""
    return text if len(text) <= PXC_SMOKE_VALUE_LIMIT else text[:PXC_SMOKE_VALUE_LIMIT] + "..."


def step_failure(outcome: StepOutcome) -> str | None:
    """The failure line of a step: the step, its full error, then its value cut to the value limit."""
    if outcome["error"] is None:
        return None
    return (
        f"{outcome['action']} as {outcome['permission']} failed: {outcome['error']}\n"
        f"  with value {_cut(json.dumps(outcome['value']))}"
    )


def check_state(
    permission: Permission, when: str, directory: Path, store: MemoryKVStore, progress: TextIO
) -> str | None:
    """Read ``getState`` under ``permission``, naming it on ``progress`` first: its failure line, or None."""
    label = f"getState as {permission.value} {when}"
    print(label, file=progress, flush=True)
    error = read_scratch_state(directory, store, permission)["error"]
    return None if error is None else f"{label}: {error}"


def check_step(step: ScratchStep, directory: Path, store: MemoryKVStore, progress: TextIO) -> str | None:
    """Run ``step``, naming it on ``progress`` first: its failure line, or None."""
    print(f"{step['action']} as {step['permission']}", file=progress, flush=True)
    return step_failure(run_step(directory, store, step))


def smoke_checks(directory: Path, progress: TextIO) -> Iterator[str | None]:
    """Run the smoke test on the activity in ``directory``, yielding each check's failure line, or None, as it ends.

    The checks share one fresh store: getState under both permissions, every step, then getState again.
    """
    manifest = PxcActivityManifest.model_validate_json((directory / "manifest.json").read_text(encoding="utf-8"))
    store = MemoryKVStore()
    for permission in PXC_SCRATCH_PERMISSIONS:
        yield check_state(permission, "before any action", directory, store, progress)
    for step in smoke_steps(manifest):
        yield check_step(step, directory, store, progress)
    for permission in PXC_SCRATCH_PERMISSIONS:
        yield check_state(permission, "after the actions", directory, store, progress)


def main(argv: list[str], progress: TextIO) -> int:
    """Smoke-test the activity directory named by ``argv[0]``, returning the exit status.

    Each check is named on ``progress`` before it runs, and each failure goes to stderr as it is found.
    """
    failed = False
    for failure in smoke_checks(Path(argv[0]), progress):
        if failure is not None:
            print(failure, file=sys.stderr, flush=True)
            failed = True
    return 1 if failed else 0


def _progress_stream() -> TextIO:
    """This process's stdout for naming the checks, with file descriptor 1 pointed at /dev/null.

    The sandbox writes its console output to file descriptor 1, so it cannot mix into the check names.
    """
    progress = os.fdopen(os.dup(1), "w")
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    os.close(null)
    return progress


if __name__ == "__main__":
    # pxc-lib logs a traceback on failure; stderr should carry only the failure lines.
    logging.disable(logging.CRITICAL)
    sys.exit(main(sys.argv[1:], _progress_stream()))
