"""The smoke test the builder runs in a child process: which steps it runs, and what it reports."""

import json
from pathlib import Path

import pytest
from pxc.lib.manifest_types import PxcActivityManifest, TypeSchema

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.constants import PXC_SMOKE_VALUE_LIMIT
from sparkth.plugins.pxc.scratch import StepOutcome
from sparkth.plugins.pxc.smoke import config_save_value, main, sample_value, smoke_steps, step_failures

MCQ_MANIFEST: dict[str, object] = json.loads((activity_dir("mcq") / "manifest.json").read_text())


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"type": "integer"}, 0),
        ({"type": "number"}, 0),
        ({"type": "string"}, ""),
        ({"type": "boolean"}, False),
        ({"type": "array", "items": {"type": "string"}}, []),
        (
            {
                "type": "object",
                "properties": {"animal": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
            },
            {"animal": "", "tags": []},
        ),
    ],
)
def test_a_sample_value_is_the_simplest_one_its_schema_accepts(schema: dict[str, object], expected: object) -> None:
    assert sample_value(TypeSchema.model_validate(schema).root) == expected


def test_the_configuration_is_saved_first_then_every_action_runs_as_play_and_edit() -> None:
    steps = smoke_steps(PxcActivityManifest.model_validate(MCQ_MANIFEST))

    assert [(step["action"], step["permission"]) for step in steps] == [
        ("config.save", "edit"),
        ("answer.submit", "play"),
        ("answer.submit", "edit"),
    ]
    assert steps[0]["value"] == {"question": "What is 2 + 2?", "answers": ["3", "4", "5"], "correct_answers": [1]}


def test_config_save_falls_back_to_a_plain_sample_when_a_default_does_not_fit() -> None:
    actions = {"config.save": {"type": "object", "properties": {"question": {"type": "integer"}}}}
    manifest = PxcActivityManifest.model_validate({**MCQ_MANIFEST, "actions": actions})

    assert config_save_value(manifest) == {"question": 0}


def test_a_config_save_that_is_not_an_object_gets_its_plain_sample() -> None:
    manifest = PxcActivityManifest.model_validate({**MCQ_MANIFEST, "actions": {"config.save": {"type": "string"}}})

    assert config_save_value(manifest) == ""


def test_a_log_field_without_a_default_does_not_break_config_save() -> None:
    fields = {"trace": {"type": "log", "items": {"type": "string"}, "scope": "activity"}}
    actions = {
        "config.save": {"type": "object", "properties": {"trace": {"type": "array", "items": {"type": "string"}}}}
    }
    manifest = PxcActivityManifest.model_validate({**MCQ_MANIFEST, "fields": fields, "actions": actions})

    assert config_save_value(manifest) == {"trace": []}


def test_a_failure_line_gives_the_error_in_full_before_a_capped_value() -> None:
    error = "Error: boom\nStack:\n  at action (index.js:1)"
    outcome: StepOutcome = {
        "action": "config.save",
        "permission": "edit",
        "value": {"question": "q" * 5000},
        "events": [],
        "error": error,
    }

    (line,) = step_failures([outcome])

    assert line.startswith("config.save as edit")
    assert error in line
    assert line.index(error) < line.index("qqq")
    assert len(line) < len(error) + PXC_SMOKE_VALUE_LIMIT + 100
    assert "..." in line


def test_an_activity_with_no_actions_runs_no_action_steps() -> None:
    manifest = PxcActivityManifest.model_validate({**MCQ_MANIFEST, "actions": None})

    assert smoke_steps(manifest) == []


@pytest.mark.wasm
def test_the_bundled_sample_passes_the_smoke_test() -> None:
    assert main([str(activity_dir("mcq"))]) == 0


def test_a_sandbox_that_cannot_run_fails_the_smoke_test(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = tmp_path / "activity"
    directory.mkdir()
    (directory / "manifest.json").write_text((activity_dir("mcq") / "manifest.json").read_text())
    (directory / "sandbox.wasm").write_bytes(b"not a component")

    assert main([str(directory)]) == 1
    assert "getState as play before any action" in capsys.readouterr().err
