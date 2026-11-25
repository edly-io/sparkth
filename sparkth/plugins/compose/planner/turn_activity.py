"""What a turn has done so far, recorded from its events."""

from typing import Any

from sparkth.plugins.compose.enums import TurnEventType
from sparkth.plugins.compose.planner.types import ExistingPlan, PlanSnapshot, TurnRouting


class TurnActivity:
    """What a turn has done so far: who answered it last, the agents and operator its steps went to,
    in order, how far it took a plan, the existing one it was given or one it made, and whether it showed
    that plan."""

    def __init__(self, existing_plan: ExistingPlan | None) -> None:
        # A turn stopped before a hand-off returned has no agent.
        self.routing = TurnRouting()
        self.agents: list[str] = []
        self._plan_steps = existing_plan.steps if existing_plan is not None else ()
        self._current_step = existing_plan.current_step if existing_plan is not None else 0
        self._has_current_step_run = existing_plan.has_current_step_run if existing_plan is not None else False
        self._is_plan_shown = False

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
                self._has_current_step_run = False
                self._is_plan_shown = True
            case TurnEventType.PLAN_STEP:
                self._current_step = event["number"]
                self._has_current_step_run = event["ran"]
                self._is_plan_shown = True

    def get_plan_in_progress(self) -> ExistingPlan | None:
        """The plan still in progress when the turn has run to its end, or None if:
        1. None of its steps has started
        2. Its last step has run
        3. It is an existing plan the turn didn't carry on, which ends it."""
        return self.get_plan_left_when_cut_short() if self._is_plan_shown else None

    def get_plan_left_when_cut_short(self) -> ExistingPlan | None:
        """The plan still in progress when the turn is cut short, stopped by the author or by a failure, or
        None when none of its steps has started or its last step has run. An existing plan the turn hadn't
        carried on yet is left unchanged."""
        finished = self._has_current_step_run and self._current_step >= len(self._plan_steps)
        if self._current_step == 0 or finished:
            return None
        return ExistingPlan(self._plan_steps, self._current_step, self._has_current_step_run)

    def get_plan_snapshot(self) -> PlanSnapshot | None:
        """The plan as it stands, or None when the turn neither made a plan nor started a step of one."""
        if not self._is_plan_shown:
            return None
        return PlanSnapshot(
            tasks=tuple(step.task for step in self._plan_steps),
            current_step=self._current_step,
            has_current_step_run=self._has_current_step_run,
        )
