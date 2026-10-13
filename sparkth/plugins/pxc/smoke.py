"""Smoke-test a freshly built activity, run as ``python -m sparkth.plugins.pxc.smoke <dir>``.

The builder runs this in a child process. A sandbox stuck in a loop cannot be stopped from a
thread, but a process can be killed. On a throwaway store, it does the following:

1. Reads ``getState`` under ``play`` and ``edit``.
2. Runs ``config.save`` as ``edit`` with the field defaults.
3. Runs every other declared action as ``play`` and as ``edit``, with the simplest value its
   schema accepts.
4. Reads ``getState`` under both permissions again.

Exit status 0 means every step passed. On 1, stderr carries one entry per failed step: the step,
the sandbox's own error text (the message, then ``Stack:`` and its frames, so it can span several
lines) and the value, cut short when long. The builder hands this to the agent.

A passing run leaves ``sandbox.wasm.bin`` beside the wasm: pxc-lib's compiled-component cache.
It moves with the activity, so the first learner launch skips compiling the component.
"""

import json
import logging
import sys
from pathlib import Path

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
from sparkth.plugins.pxc.scratch import (
    ScratchStep,
    StateOutcome,
    StepOutcome,
    read_scratch_state,
    run_scratch,
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


def step_failures(outcomes: list[StepOutcome]) -> list[str]:
    """One entry per failed step: the step, its full error, then its value cut to the value limit."""
    return [
        f"{outcome['action']} as {outcome['permission']} failed: {outcome['error']}\n"
        f"  with value {_cut(json.dumps(outcome['value']))}"
        for outcome in outcomes
        if outcome["error"] is not None
    ]


def state_failures(outcomes: list[StateOutcome], when: str) -> list[str]:
    """One entry per failed ``getState``, saying when in the run it was read."""
    return [
        f"getState as {outcome['permission']} {when}: {outcome['error']}"
        for outcome in outcomes
        if outcome["error"] is not None
    ]


def smoke_failures(directory: Path) -> list[str]:
    """Every failing step of the smoke run on the activity in ``directory``, in the order it ran."""
    manifest = PxcActivityManifest.model_validate_json((directory / "manifest.json").read_text(encoding="utf-8"))
    fresh = MemoryKVStore()
    before = [read_scratch_state(directory, fresh, permission) for permission in PXC_SCRATCH_PERMISSIONS]
    report = run_scratch(directory, smoke_steps(manifest))
    return [
        *state_failures(before, "before any action"),
        *step_failures(report["steps"]),
        *state_failures(report["state"], "after the actions"),
    ]


def main(argv: list[str]) -> int:
    """Smoke-test the activity directory named by ``argv[0]``, returning the exit status."""
    failures = smoke_failures(Path(argv[0]))
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    # pxc-lib logs a traceback on failure; stderr should carry only the failure lines.
    logging.disable(logging.CRITICAL)
    sys.exit(main(sys.argv[1:]))
