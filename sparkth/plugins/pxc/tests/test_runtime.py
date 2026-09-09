from pathlib import Path

import pytest
from pxc.lib.permission import Permission

from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcActivityNotFound
from sparkth.plugins.pxc.runtime import build_runtime, read_state, run_action
from sparkth.plugins.pxc.tokens import LaunchClaims

CLAIMS = LaunchClaims("mcq", "placement-1", "course-v1:X+Y+Z", "learner-7")


def test_the_runtime_is_built_for_the_claimed_placement_and_learner() -> None:
    runtime = build_runtime(CLAIMS)

    assert runtime.name == "mcq"
    assert runtime.activity_id == "placement-1"
    assert runtime.course_id == "course-v1:X+Y+Z"
    assert runtime.user_id == "learner-7"


def test_permission_is_fixed_to_play_and_never_taken_from_the_request() -> None:
    assert build_runtime(CLAIMS).permission is Permission.play


def test_an_unknown_activity_is_rejected() -> None:
    with pytest.raises(PxcActivityNotFound):
        build_runtime(LaunchClaims("absent", "placement-1", "course-v1:X+Y+Z", "learner-7"))


def test_the_state_file_is_the_activity_types_own(tmp_path: Path) -> None:
    build_runtime(CLAIMS)

    assert (tmp_path / "mcq.sqlite3").exists()


@pytest.mark.wasm
def test_state_reads_the_seeded_configuration() -> None:
    runtime = build_runtime(CLAIMS)
    # "question" is scoped "activity" in the manifest, which blanks the learner segment.
    runtime.field_store.set("course-v1:X+Y+Z", "mcq", "placement-1", "", "question", "What is 2 + 2?")

    assert read_state(runtime)["question"] == "What is 2 + 2?"


@pytest.mark.wasm
def test_an_undeclared_action_is_rejected() -> None:
    with pytest.raises(PxcActionRejected):
        run_action(build_runtime(CLAIMS), "no.such.action", [])


@pytest.mark.wasm
def test_submitting_an_answer_returns_the_activitys_events() -> None:
    runtime = build_runtime(CLAIMS)
    # All three fields are scoped "activity" in the manifest, which blanks the learner segment.
    scope = ("course-v1:X+Y+Z", "mcq", "placement-1", "")
    runtime.field_store.set(*scope, "question", "What is 2 + 2?")
    runtime.field_store.set(*scope, "answers", ["3", "4"])
    runtime.field_store.set(*scope, "correct_answers", [1])

    events = run_action(runtime, "answer.submit", [1])

    assert any(event["name"] == "answer.result" for event in events)
