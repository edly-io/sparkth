"""A throwaway run of an activity's actions: each step's outcome, the state after, the stored fields."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pxc.lib.field_store import MemoryKVStore
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.scratch.__main__ import main
from sparkth.plugins.pxc.scratch.schemas import ScratchStep
from sparkth.plugins.pxc.scratch.steps import read_scratch_state, run_scratch, run_step
from sparkth.plugins.pxc.tests.conftest import AUTHORED_MANIFEST, THROWN_TEXT, compiled_activity, unrunnable_activity

MCQ = activity_dir("mcq")
SAVE = ScratchStep(
    action="config.save",
    value={"question": "Capital of France?", "answers": ["Paris", "Lyon"], "correct_answers": [0]},
    permission="edit",
)
SUBMIT = ScratchStep(action="answer.submit", value=[0], permission="play")
LOGGING_SANDBOX_JS = """\
export function onAction(name, data, context, permission) {
  console.log("from the sandbox");
  return "";
}
export function getState(context, permission) {
  console.log("from the sandbox");
  return "{}";
}
"""


def test_a_step_whose_sandbox_fails_reports_its_error_text(throwing_sandbox: None) -> None:
    outcome = run_step(MCQ, MemoryKVStore(), SUBMIT, io.StringIO())

    assert outcome["error"] == THROWN_TEXT
    assert outcome["events"] == []


def test_a_step_the_manifest_refuses_reports_the_refusal() -> None:
    step = ScratchStep(action="no.such.action", value=[], permission="play")

    outcome = run_step(MCQ, MemoryKVStore(), step, io.StringIO())

    assert outcome["error"] is not None
    assert "no.such.action" in outcome["error"]


def test_state_that_is_not_json_text_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActivityRuntime, "get_state", _not_json)

    outcome = read_scratch_state(MCQ, MemoryKVStore(), Permission.play, io.StringIO())

    assert outcome["state"] is None
    assert outcome["error"] is not None
    assert outcome["error"].startswith("getState must return JSON text")


def test_state_that_is_not_an_object_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ActivityRuntime, "get_state", _a_list)

    outcome = read_scratch_state(MCQ, MemoryKVStore(), Permission.edit, io.StringIO())

    assert outcome["error"] == "getState must return a JSON object, not list"


def _not_json(runtime: ActivityRuntime) -> dict[str, object]:
    """Stand in for ``ActivityRuntime.get_state`` with a getState that returned text which is not JSON."""
    raise json.JSONDecodeError("Expecting value", "not json", 0)


def _a_list(runtime: ActivityRuntime) -> object:
    """Stand in for ``ActivityRuntime.get_state`` with a getState that returned a JSON array."""
    return ["not", "an", "object"]


@pytest.mark.wasm
def test_steps_share_one_store_and_the_report_holds_events_state_and_fields() -> None:
    report = run_scratch(MCQ, [SAVE, SUBMIT], io.StringIO())

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

    assert main([str(MCQ)], io.StringIO()) == 0
    report = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert report["steps"][0]["action"] == "answer.submit"


def test_each_step_and_state_read_is_named_on_the_progress_stream_in_the_order_it_runs(tmp_path: Path) -> None:
    progress = io.StringIO()

    run_scratch(unrunnable_activity(tmp_path), [SAVE, SUBMIT], progress)

    assert progress.getvalue().splitlines() == [
        "config.save as edit",
        "answer.submit as play",
        "getState as play",
        "getState as edit",
    ]


@pytest.mark.wasm
async def test_the_child_entry_names_each_step_on_stdout_and_drops_the_sandboxs_own_output(tmp_path: Path) -> None:
    activity_id = await compiled_activity(
        LOGGING_SANDBOX_JS, {**AUTHORED_MANIFEST, "actions": {"poke": {"type": "string"}}}
    )
    (tmp_path / "steps.json").write_text(json.dumps([ScratchStep(action="poke", value="", permission="play")]))

    child = subprocess.run(
        [sys.executable, "-m", "sparkth.plugins.pxc.scratch", str(activity_dir(activity_id))],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert child.stdout.splitlines() == ["poke as play", "getState as play", "getState as edit"]
