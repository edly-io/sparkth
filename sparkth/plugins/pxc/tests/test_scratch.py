"""A throwaway run of an activity's actions: each step's outcome, the state after, the stored fields."""

import json
from pathlib import Path

import pytest
from pxc.lib.field_store import MemoryKVStore
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.scratch import ScratchStep, main, read_scratch_state, run_scratch, run_step
from sparkth.plugins.pxc.tests.conftest import THROWN_TEXT

MCQ = activity_dir("mcq")
SAVE = ScratchStep(
    action="config.save",
    value={"question": "Capital of France?", "answers": ["Paris", "Lyon"], "correct_answers": [0]},
    permission="edit",
)
SUBMIT = ScratchStep(action="answer.submit", value=[0], permission="play")


def test_a_step_whose_sandbox_fails_reports_its_error_text(throwing_sandbox: None) -> None:
    outcome = run_step(MCQ, MemoryKVStore(), SUBMIT)

    assert outcome["error"] == THROWN_TEXT
    assert outcome["events"] == []


def test_a_step_the_manifest_refuses_reports_the_refusal() -> None:
    outcome = run_step(MCQ, MemoryKVStore(), ScratchStep(action="no.such.action", value=[], permission="play"))

    assert outcome["error"] is not None
    assert "no.such.action" in outcome["error"]


def test_state_that_is_not_json_text_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActivityRuntime, "get_state", _not_json)

    outcome = read_scratch_state(MCQ, MemoryKVStore(), Permission.play)

    assert outcome["state"] is None
    assert outcome["error"] is not None
    assert outcome["error"].startswith("getState must return JSON text")


def test_state_that_is_not_an_object_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActivityRuntime, "get_state", _a_list)

    outcome = read_scratch_state(MCQ, MemoryKVStore(), Permission.edit)

    assert outcome["error"] == "getState must return a JSON object, not list"


def _not_json(runtime: ActivityRuntime) -> dict[str, object]:
    """Stand in for ``ActivityRuntime.get_state`` with a getState that returned text which is not JSON."""
    raise json.JSONDecodeError("Expecting value", "not json", 0)


def _a_list(runtime: ActivityRuntime) -> object:
    """Stand in for ``ActivityRuntime.get_state`` with a getState that returned a JSON array."""
    return ["not", "an", "object"]


@pytest.mark.wasm
def test_steps_share_one_store_and_the_report_holds_events_state_and_fields() -> None:
    report = run_scratch(MCQ, [SAVE, SUBMIT])

    assert [step["error"] for step in report["steps"]] == [None, None]
    assert "answer.result" in [event["name"] for event in report["steps"][1]["events"]]
    assert report["fields"]["question"] == "Capital of France?"
    play, edit = report["state"]
    assert play["state"] is not None and "correct_answers" not in play["state"]
    assert edit["state"] is not None and edit["state"]["correct_answers"] == [0]


@pytest.mark.wasm
def test_the_child_entry_reads_its_steps_and_writes_its_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "steps.json").write_text(json.dumps([SUBMIT]), encoding="utf-8")

    assert main([str(MCQ)]) == 0
    report = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert report["steps"][0]["action"] == "answer.submit"
