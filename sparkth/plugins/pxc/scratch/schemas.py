"""The steps a scratch run takes and what it reports for them."""

from typing import TypedDict

from pxc.lib.fields import FieldType


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
