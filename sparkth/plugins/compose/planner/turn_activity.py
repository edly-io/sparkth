"""What a turn has done so far, recorded from its events."""

from typing import Any

from sparkth.plugins.compose.enums import TurnEventType
from sparkth.plugins.compose.planner.types import ExistingPlan, TurnRouting


class TurnActivity:
    """What a turn has done so far: who answered it last, the agents and operator its steps went to,
    in order, and how far it took a plan, the existing one it was given or one it made."""

    def __init__(self, existing_plan: ExistingPlan | None) -> None:
        # A turn stopped before a hand-off returned has no agent.
        self.routing = TurnRouting()
        self.agents: list[str] = []
        self._plan_steps = existing_plan.steps if existing_plan is not None else ()
        self._current_step = existing_plan.current if existing_plan is not None else 0
        self._current_step_done = False

    def record(self, event: dict[str, Any]) -> None:
        """Note what the turn's ``event`` says it did: a hand-off, a plan it made, or a plan step that
        started or ran. Other events are ignored."""
        match event["type"]:
            case TurnEventType.ROUTED:
                self.routing = event["routing"]
                if self.routing.agent is not None:
                    self.agents.append(self.routing.agent)
            case TurnEventType.PLAN:
                self._plan_steps = tuple(event["steps"])
                self._current_step = 0
                self._current_step_done = False
            case TurnEventType.PLAN_STEP:
                self._current_step = event["number"]
                self._current_step_done = event["ran"]

    def get_plan_in_progress(self) -> ExistingPlan | None:
        """The plan still in progress when the turn ends, or None if:
        1. None of its steps has started
        2. Its last step is done.
        An existing plan the turn didn't touch is returned unchanged."""
        finished = self._current_step_done and self._current_step >= len(self._plan_steps)
        if self._current_step == 0 or finished:
            return None
        return ExistingPlan(self._plan_steps, self._current_step)
