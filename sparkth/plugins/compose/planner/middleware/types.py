"""Types the planner's middleware builds on."""

from collections.abc import Sequence
from dataclasses import dataclass

from sparkth.plugins.compose.planner.types import PlannedStep


@dataclass(frozen=True)
class Plan:
    """The plan a turn follows: its steps, the numbers of the steps that may run next, and whether
    it is the existing plan from an earlier message."""

    steps: Sequence[PlannedStep]
    allowed_numbers: tuple[int, ...]
    from_earlier_message: bool
