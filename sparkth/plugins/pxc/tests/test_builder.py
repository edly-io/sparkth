"""The activity build: manifest rules, bounded child processes, compile, smoke test, storage."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.builder import agent_error, compile_sandbox, run_bounded, validate_manifest
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_BUILD_ERROR_LIMIT, PXC_MAX_SOURCE_CHARS
from sparkth.plugins.pxc.exceptions import PxcBuildTimedOut, PxcCompileFailed, PxcManifestInvalid
from sparkth.plugins.pxc.schemas import ActivitySource

OWNER = 1
MCQ = activity_dir("mcq")
MCQ_MANIFEST: dict[str, object] = json.loads((MCQ / "manifest.json").read_text())


def test_the_manifest_is_named_after_the_activity_id() -> None:
    assert validate_manifest({**MCQ_MANIFEST, "name": "anything"}, "the-id")["name"] == "the-id"


def test_a_manifest_outside_the_pxc_schema_names_the_field_at_fault() -> None:
    without_ui = {key: value for key, value in MCQ_MANIFEST.items() if key != "ui"}

    with pytest.raises(PxcManifestInvalid) as refused:
        validate_manifest(without_ui, "the-id")

    assert "ui: Field required" in str(refused.value)


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"assets": ["picture.png"]}, "assets"),
        ({"capabilities": {"grading": {}}}, "capabilities"),
        ({"ui": "main.js"}, "ui"),
        ({"sandbox": "other.wasm"}, "sandbox"),
    ],
)
def test_a_manifest_breaking_a_build_rule_is_refused(change: dict[str, object], field: str) -> None:
    with pytest.raises(PxcManifestInvalid) as refused:
        validate_manifest({**MCQ_MANIFEST, **change}, "the-id")

    assert f'"{field}"' in str(refused.value)


@pytest.mark.parametrize("field", ["ui_js", "sandbox_js"])
def test_source_over_the_size_limit_is_refused_before_any_build(field: str) -> None:
    sources = {"ui_js": "", "sandbox_js": "", field: "x" * (PXC_MAX_SOURCE_CHARS + 1)}

    with pytest.raises(ValidationError):
        ActivitySource.model_validate({"title": "t", "description": "d", "manifest": {}, **sources})


# Starts a grandchild that sleeps, records its pid in argv[1], then sleeps itself.
SPAWNS_A_GRANDCHILD = (
    "import subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "open(sys.argv[1], 'w').write(str(child.pid))\n"
    "time.sleep(60)\n"
)


def _process_gone(pid: int) -> bool:
    """Whether ``pid`` has exited, polling for up to five seconds while the OS reaps it."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


@pytest.fixture
def short_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PXC_BUILD_TIMEOUT_SECONDS", "2")
    get_pxc_settings.cache_clear()


async def test_a_step_returns_its_exit_code_and_stderr(tmp_path: Path) -> None:
    script = "import sys; sys.stderr.write('boom'); sys.exit(3)"

    assert await run_bounded([sys.executable, "-c", script], tmp_path, "A step", None) == (3, "boom")


async def test_a_step_that_outlives_the_timeout_is_stopped(tmp_path: Path, short_timeout: None) -> None:
    started = time.monotonic()

    with pytest.raises(PxcBuildTimedOut) as timed_out:
        await run_bounded([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, "A step", None)

    assert time.monotonic() - started < 10
    assert "A step did not finish within 2 seconds" in str(timed_out.value)


async def test_a_timeout_kills_the_steps_grandchildren_too(tmp_path: Path, short_timeout: None) -> None:
    # node runs wizer as a child of its own; killing node alone leaves wizer spinning.
    pid_file = tmp_path / "grandchild.pid"

    with pytest.raises(PxcBuildTimedOut):
        await run_bounded([sys.executable, "-c", SPAWNS_A_GRANDCHILD, str(pid_file)], tmp_path, "A step", None)

    assert _process_gone(int(pid_file.read_text()))


async def test_cancelling_a_step_kills_its_process_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    step = asyncio.create_task(
        run_bounded([sys.executable, "-c", SPAWNS_A_GRANDCHILD, str(pid_file)], tmp_path, "A step", None)
    )
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text():
            break
        await asyncio.sleep(0.1)
    step.cancel()

    with pytest.raises(asyncio.CancelledError):
        await step

    assert _process_gone(int(pid_file.read_text()))


def test_agent_errors_drop_toolchain_frames_and_the_build_path(tmp_path: Path) -> None:
    stderr = (
        "file:///opt/x/node_modules/@bytecodealliance/componentize-js/src/componentize.js:302\n"
        "Error: Failed to initialize component:\n"
        "    at componentize (file:///opt/x/node_modules/a.js:1:1)\n"
        f"ReferenceError: {tmp_path}/sandbox.js:3:1 boom\n"
    )

    assert (
        agent_error(stderr, tmp_path) == "Error: Failed to initialize component:\nReferenceError: sandbox.js:3:1 boom"
    )


def test_agent_errors_keep_the_end_of_a_long_output(tmp_path: Path) -> None:
    trimmed = agent_error("early noise\n" + "x" * PXC_BUILD_ERROR_LIMIT + "\nthe cause", tmp_path)

    assert trimmed.endswith("the cause")
    assert len(trimmed) == PXC_BUILD_ERROR_LIMIT


def _compile_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "compile"
    directory.mkdir()
    return directory


@pytest.mark.wasm
async def test_the_sample_sandbox_compiles_from_its_single_file(tmp_path: Path) -> None:
    output = tmp_path / "sandbox.wasm"

    await compile_sandbox((MCQ / "sandbox.js").read_text(), _compile_dir(tmp_path), output)

    assert output.stat().st_size > 0


@pytest.mark.wasm
async def test_an_import_outside_pxc_sandbox_fails_to_compile(tmp_path: Path) -> None:
    sandbox_js = (
        'import { readFileSync } from "node:fs";\n'
        'export function onAction() { return ""; }\n'
        'export function getState() { return readFileSync("x"); }\n'
    )

    with pytest.raises(PxcCompileFailed) as refused:
        await compile_sandbox(sandbox_js, _compile_dir(tmp_path), tmp_path / "sandbox.wasm")

    assert "node:fs" in str(refused.value)


@pytest.mark.wasm
async def test_a_sandbox_cannot_reach_a_file_outside_its_compile_directory(tmp_path: Path) -> None:
    # The compile runs top-level code; with a parent as cwd this import would embed the secret.
    (tmp_path / "secret.js").write_text('export const secret = "TOPSECRET";\n')
    sandbox_js = (
        'import { secret } from "../secret.js";\n'
        'export function onAction() { return ""; }\n'
        "export function getState() { return JSON.stringify({ secret }); }\n"
    )

    with pytest.raises(PxcCompileFailed) as refused:
        await compile_sandbox(sandbox_js, _compile_dir(tmp_path), tmp_path / "sandbox.wasm")

    assert "TOPSECRET" not in str(refused.value)


@pytest.mark.wasm
async def test_a_compile_that_never_ends_is_stopped(tmp_path: Path, short_timeout: None) -> None:
    sandbox_js = (
        'while (true) {}\nexport function onAction() { return ""; }\nexport function getState() { return "{}"; }\n'
    )

    with pytest.raises(PxcBuildTimedOut):
        await compile_sandbox(sandbox_js, _compile_dir(tmp_path), tmp_path / "sandbox.wasm")
