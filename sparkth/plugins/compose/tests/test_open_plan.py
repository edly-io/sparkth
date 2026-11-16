"""Which plan a conversation's messages leave open for its next turn."""

import json
from dataclasses import asdict

from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.planner import OpenPlan, PlannedStep
from sparkth.plugins.compose.routes.utils import open_plan_of

PLAN = OpenPlan(
    (PlannedStep("stub", "Write the lesson"), PlannedStep("operator", "Publish it")), current=1, current_ran=True
)


def _reply(metadata: str | None) -> Message:
    return Message(conversation_id=1, role="assistant", content="Who are your learners?", model_metadata=metadata)


def _answer() -> Message:
    return Message(conversation_id=1, role="user", content="High school students")


def test_the_latest_replys_plan_is_open() -> None:
    assert open_plan_of([_reply(json.dumps({"plan": asdict(PLAN)})), _answer()]) == PLAN


def test_a_plan_of_an_earlier_reply_is_not() -> None:
    earlier = _reply(json.dumps({"plan": asdict(PLAN)}))

    assert open_plan_of([earlier, _answer(), _reply(json.dumps({"steps": ["stub"]})), _answer()]) is None


def test_a_conversation_without_a_reply_has_none() -> None:
    assert open_plan_of([_answer()]) is None


def test_a_reply_whose_metadata_cannot_be_read_has_none() -> None:
    assert open_plan_of([_reply("{not json"), _answer()]) is None


def test_an_error_after_the_reply_does_not_close_its_plan() -> None:
    """A failed turn stores what it wrote, with the plan, and then the error."""
    reply = _reply(json.dumps({"plan": asdict(PLAN)}))
    error = Message(conversation_id=1, role="assistant", content="Something went wrong.", is_error=True)

    assert open_plan_of([reply, error, _answer()]) == PLAN
