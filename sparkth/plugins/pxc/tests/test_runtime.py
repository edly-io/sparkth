import json
from pathlib import Path

import pytest
from pxc.lib.permission import Permission
from uuid6 import uuid7

from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.exceptions import PxcActionRejected, PxcActivityNotFound
from sparkth.plugins.pxc.runtime import build_runtime, read_state, run_action
from sparkth.plugins.pxc.tokens import LaunchClaims

CLAIMS = LaunchClaims("mcq", "instance-1", "course-1", "learner-7", Permission.play)
EDIT_CLAIMS = LaunchClaims("mcq", "instance-1", "course-1", "learner-7", Permission.edit)


def test_the_runtime_is_built_for_the_claimed_activity_instance_and_learner() -> None:
    runtime = build_runtime(CLAIMS)

    assert runtime.name == "mcq"
    assert runtime.activity_id == "instance-1"
    assert runtime.course_id == "course-1"
    assert runtime.user_id == "learner-7"


def test_the_runtime_takes_its_permission_from_the_claims() -> None:
    # Paired with test_escalating_the_permission_claim_breaks_the_signature in test_tokens.py:
    # that one proves the claim cannot be forged, this one proves it is not ignored. Either
    # test alone passes an implementation that hardcodes a permission.
    assert build_runtime(CLAIMS).permission is Permission.play
    assert build_runtime(EDIT_CLAIMS).permission is Permission.edit


def test_an_unknown_activity_is_rejected() -> None:
    with pytest.raises(PxcActivityNotFound):
        build_runtime(LaunchClaims("absent", "instance-1", "course-1", "learner-7", Permission.play))


def test_the_state_file_is_the_activity_types_own(tmp_path: Path) -> None:
    build_runtime(CLAIMS)

    assert (tmp_path / "mcq.sqlite3").exists()


@pytest.mark.wasm
def test_state_reads_the_seeded_configuration() -> None:
    runtime = build_runtime(CLAIMS)
    # "question" is scoped "activity" in the manifest, which blanks the learner segment.
    runtime.field_store.set("course-1", "mcq", "instance-1", "", "question", "What is 2 + 2?")

    assert read_state(runtime)["question"] == "What is 2 + 2?"


@pytest.mark.wasm
def test_an_undeclared_action_is_rejected() -> None:
    with pytest.raises(PxcActionRejected):
        run_action(build_runtime(CLAIMS), "no.such.action", [])


@pytest.mark.wasm
def test_submitting_an_answer_returns_the_activitys_events() -> None:
    runtime = build_runtime(CLAIMS)
    # All three fields are scoped "activity" in the manifest, which blanks the learner segment.
    scope = ("course-1", "mcq", "instance-1", "")
    runtime.field_store.set(*scope, "question", "What is 2 + 2?")
    runtime.field_store.set(*scope, "answers", ["3", "4"])
    runtime.field_store.set(*scope, "correct_answers", [1])

    events = run_action(runtime, "answer.submit", [1])

    assert any(event["name"] == "answer.result" for event in events)


@pytest.mark.wasm
def test_configuration_saves_with_edit_and_is_ignored_with_play() -> None:
    # The sandbox is the enforcement point: pxc-lib's on_action refuses actions only in view
    # mode and passes the permission through, and activity/sandbox.js returns early from
    # handleConfigSave unless it is "edit". A play-mode config.save is therefore silently
    # ignored rather than raising, which is what this asserts.
    scope = ("course-1", "mcq", "instance-1", "")
    seeded = build_runtime(EDIT_CLAIMS)
    seeded.field_store.set(*scope, "question", "Original?")
    seeded.field_store.set(*scope, "answers", ["a", "b"])
    seeded.field_store.set(*scope, "correct_answers", [0])

    run_action(
        build_runtime(EDIT_CLAIMS),
        "config.save",
        {"question": "Edited?", "answers": ["x", "y"], "correct_answers": [1]},
    )
    assert read_state(build_runtime(CLAIMS))["question"] == "Edited?"

    run_action(
        build_runtime(CLAIMS),
        "config.save",
        {"question": "Sneaky?", "answers": ["p", "q"], "correct_answers": [0]},
    )
    assert read_state(build_runtime(CLAIMS))["question"] == "Edited?"


def test_a_generated_activity_launches_from_its_own_directory() -> None:
    # The learner path resolves a generated activity from disk alone, with no database read.
    activity_id = str(uuid7())
    directory = generated_activity_dir(activity_id)
    directory.mkdir(parents=True)
    manifest = json.loads((activity_dir("mcq") / "manifest.json").read_text())
    (directory / "manifest.json").write_text(json.dumps({**manifest, "name": activity_id}))

    runtime = build_runtime(LaunchClaims(activity_id, "instance-1", "course-1", "learner-7", Permission.play))

    assert runtime.name == activity_id
