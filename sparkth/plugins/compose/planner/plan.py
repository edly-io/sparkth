"""Following a plan from one message to the next: how far a turn took it, and how it is read back from a reply."""

import re
from collections.abc import Sequence
from typing import Any

from pydantic import TypeAdapter, ValidationError

from sparkth.lib.log import get_logger
from sparkth.plugins.compose.constants import MAX_PLAN_STEPS, PLAN_TASK_MAX_CHARS, PLAN_TASK_PATTERN
from sparkth.plugins.compose.planner.types import OpenPlan, PlannedStep

logger = get_logger(__name__)

# The key of a reply's metadata that holds the plan it left open.
PLAN_KEY = "plan"

_OPEN_PLAN_ADAPTER = TypeAdapter(OpenPlan)


class PlanProgress:
    """How far a turn takes a plan: the one it was given from an earlier message, or one it makes."""

    def __init__(self, earlier: OpenPlan | None) -> None:
        self._steps = earlier.steps if earlier is not None else ()
        self._current = earlier.current if earlier is not None else 0
        self._carried_on = False
        self._current_ran = earlier.current_ran if earlier is not None else False

    def record_plan(self, steps: Sequence[PlannedStep]) -> None:
        """Note that the turn made a plan of ``steps``, which replaces any earlier one."""
        self._steps, self._current, self._carried_on, self._current_ran = tuple(steps), 0, False, False

    def record_step(self, number: int, *, ran: bool) -> None:
        """Note that the plan is at its step ``number``, which has ``ran``, or else has started or waits to start."""
        self._current, self._carried_on, self._current_ran = number, True, ran

    def left_open(self) -> OpenPlan | None:
        """The plan as the turn leaves it, or None when it is closed: the turn started none of its
        steps, or its last step has run."""
        finished = self._current_ran and self._current >= len(self._steps)
        if not self._carried_on or finished:
            return None
        return OpenPlan(self._steps, self._current, self._current_ran)


def _within_plan_limits(plan: OpenPlan) -> bool:
    """Whether ``plan`` keeps the limits a plan is shown under: as many steps as a plan holds, each
    task one short line, and a latest step of its own."""
    return (
        2 <= len(plan.steps) <= MAX_PLAN_STEPS
        and 1 <= plan.current <= len(plan.steps)
        and all(
            len(step.task) <= PLAN_TASK_MAX_CHARS and re.fullmatch(PLAN_TASK_PATTERN, step.task) is not None
            for step in plan.steps
        )
    )


def read_open_plan(metadata: dict[str, Any] | None) -> OpenPlan | None:
    """The plan a reply's ``metadata`` left open, or None when it holds none that could have been shown."""
    stored = (metadata or {}).get(PLAN_KEY)
    if stored is None:
        return None
    try:
        plan = _OPEN_PLAN_ADAPTER.validate_python(stored)
    except ValidationError:
        logger.warning("A reply's stored plan is not a whole plan; the conversation carries on without it")
        return None
    if not _within_plan_limits(plan):
        logger.warning("A reply's stored plan breaks a plan's limits; the conversation carries on without it")
        return None
    return plan
