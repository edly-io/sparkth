"""Smoke-test a freshly built activity, run as ``python -m sparkth.plugins.pxc.scratch.smoke <dir>``.

The builder runs this on every build. On a throwaway store, it does the following:

1. Reads ``getState`` under ``play`` and ``edit``.
2. Runs ``config.save`` as ``edit`` with the field defaults.
3. Runs every other declared action as ``play`` and as ``edit``, with the simplest value its
   schema accepts.
4. Reads ``getState`` under both permissions again.

Exit status 0 means every step passed. On 1, stderr carries one entry per failed step: the step,
the sandbox's own error text (the message, then ``Stack:`` and its frames, so it can span several
lines) and the value, cut short when long. Each entry is written as soon as its step fails, so a
run that never ends keeps the ones before it. The builder hands them to the agent.

A passing run leaves ``sandbox.wasm.bin`` beside the wasm: pxc-lib's compiled-component cache.
It moves with the activity, so the first learner launch skips compiling the component.
"""

import json
import logging
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

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.constants import (
    PXC_CONFIG_SAVE_ACTION,
    PXC_SAMPLE_VALUES,
    PXC_SCRATCH_PERMISSIONS,
    PXC_SMOKE_VALUE_LIMIT,
)
from sparkth.plugins.pxc.scratch.progress import progress_stream
from sparkth.plugins.pxc.scratch.schemas import ScratchStep, StateOutcome, StepOutcome
from sparkth.plugins.pxc.scratch.steps import read_scratch_state, run_step

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


def state_failure(outcome: StateOutcome, when: str) -> str | None:
    """The failure line of a ``getState`` read, saying when in the run it was read."""
    if outcome["error"] is None:
        return None
    return f"getState as {outcome['permission']} {when}: {outcome['error']}"


def smoke_checks(directory: Path, progress: TextIO) -> Iterator[str | None]:
    """Run the smoke test on the activity in ``directory``, yielding each check's failure line, or None, as it ends.

    The checks share one fresh store: getState under both permissions, every step, then getState again.
    """
    manifest = PxcActivityManifest.model_validate_json((directory / "manifest.json").read_text(encoding="utf-8"))
    store = MemoryKVStore()
    for permission in PXC_SCRATCH_PERMISSIONS:
        yield state_failure(read_scratch_state(directory, store, permission, progress), "before any action")
    for step in smoke_steps(manifest):
        yield step_failure(run_step(directory, store, step, progress))
    for permission in PXC_SCRATCH_PERMISSIONS:
        yield state_failure(read_scratch_state(directory, store, permission, progress), "after the actions")


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


if __name__ == "__main__":
    # pxc-lib logs a traceback on failure; stderr should carry only the failure lines.
    logging.disable(logging.CRITICAL)
    sys.exit(main(sys.argv[1:], progress_stream()))
