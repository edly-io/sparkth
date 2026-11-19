"""Which plan a conversation's saved messages hand to its next message."""

import json
from dataclasses import asdict
from typing import Any

import pytest

from sparkth.lib.compose.constants import OPERATOR_AGENT_NAME
from sparkth.plugins.compose.constants import MAX_PLAN_STEPS
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.planner import ExistingPlan, PlannedStep
from sparkth.plugins.compose.routes.utils import get_existing_plan_or_none
from sparkth.plugins.compose.tests.conftest import STUB_AGENT

STEPS = (PlannedStep(STUB_AGENT.name, "Write the lesson"), PlannedStep(OPERATOR_AGENT_NAME, "Publish it"))
PLAN = ExistingPlan(STEPS, current_step=1)


def _reply(metadata: dict[str, Any] | None, *, is_error: bool = False) -> Message:
    """A saved reply with ``metadata``, or an error message when ``is_error``."""
    return Message(
        conversation_id=1,
        role="assistant",
        content="Who are your learners?",
        model_metadata=json.dumps(metadata) if metadata is not None else None,
        is_error=is_error,
    )


@pytest.mark.parametrize(
    ("current", "has_current_step_run"),
    [(1, True), (2, True), (2, False)],
    ids=["first_step", "last_step", "a_step_that_never_ran"],
)
def test_a_saved_plan_reads_back_as_it_was(current: int, has_current_step_run: bool) -> None:
    plan = ExistingPlan(STEPS, current, has_current_step_run)

    assert get_existing_plan_or_none([_reply({"plan": asdict(plan)})]) == plan


@pytest.mark.parametrize(
    "stored",
    [
        "soon",
        {"steps": [], "current_step": 1},
        {"steps": [{"agent": "a"}, {"agent": "b"}], "current_step": 1},
        {"steps": [asdict(step) for step in STEPS], "current_step": 0},
        {"steps": [asdict(step) for step in STEPS], "current_step": 3},
        {"steps": [asdict(STEPS[0])] * (MAX_PLAN_STEPS + 1), "current_step": 1},
    ],
    ids=["not_a_plan", "no_steps", "half_a_step", "before_its_first_step", "past_its_last_step", "too_many_steps"],
)
def test_a_saved_plan_that_is_not_whole_holds_none(stored: object) -> None:
    assert get_existing_plan_or_none([_reply({"plan": stored})]) is None


@pytest.mark.parametrize("metadata", [None, {}], ids=["no_metadata", "no_plan"])
def test_metadata_without_a_plan_holds_none(metadata: dict[str, Any] | None) -> None:
    assert get_existing_plan_or_none([_reply(metadata)]) is None


def test_an_error_message_is_not_the_latest_reply() -> None:
    """A failed turn saves its partial reply, plan included, before the error message."""
    failed = _reply(None, is_error=True)

    assert get_existing_plan_or_none([_reply({"plan": asdict(PLAN)}), failed]) == PLAN


def test_a_latest_reply_without_a_plan_hides_an_earlier_one() -> None:
    assert get_existing_plan_or_none([_reply({"plan": asdict(PLAN)}), _reply({})]) is None


def test_metadata_that_is_not_json_holds_none() -> None:
    reply = Message(conversation_id=1, role="assistant", content="Who are your learners?", model_metadata="{not json")

    assert get_existing_plan_or_none([reply]) is None
