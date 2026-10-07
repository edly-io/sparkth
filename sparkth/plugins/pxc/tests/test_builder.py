"""The activity build: manifest rules, bounded child processes, compile, smoke test, storage."""

import asyncio
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest
from pxc.lib.permission import Permission
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.builder import (
    build_activity,
    compile_sandbox,
    run_bounded,
    validate_manifest,
)
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import (
    PXC_BUILD_ERROR_LIMIT,
    PXC_BUILD_STDERR_LIMIT_BYTES,
    PXC_MAX_DESCRIPTION_CHARS,
    PXC_MAX_SOURCE_CHARS,
)
from sparkth.plugins.pxc.exceptions import PxcBuildTimedOut, PxcCompileFailed, PxcManifestInvalid, PxcSmokeTestFailed
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.runtime import build_runtime, read_state
from sparkth.plugins.pxc.schemas import ActivitySource
from sparkth.plugins.pxc.store import get_owned_activity, list_owned_activities
from sparkth.plugins.pxc.tests.conftest import TOOLCHAIN_DIR
from sparkth.plugins.pxc.tokens import LaunchClaims

OWNER = 1
MCQ = activity_dir("mcq")
MCQ_MANIFEST: dict[str, object] = json.loads((MCQ / "manifest.json").read_text())
MCQ_SANDBOX_JS = (MCQ / "sandbox.js").read_text()


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


def test_a_description_over_the_size_limit_is_refused() -> None:
    with pytest.raises(ValidationError):
        ActivitySource.model_validate(
            {
                "title": "t",
                "description": "x" * (PXC_MAX_DESCRIPTION_CHARS + 1),
                "manifest": {},
                "ui_js": "",
                "sandbox_js": "",
            }
        )


@pytest.mark.parametrize("title", ["", " ", "\t\n"])
def test_a_blank_title_is_refused(title: str) -> None:
    with pytest.raises(ValidationError):
        ActivitySource.model_validate(
            {"title": title, "description": "d", "manifest": {}, "ui_js": "", "sandbox_js": ""}
        )


def test_a_manifest_over_the_size_limit_is_refused_before_any_build() -> None:
    manifest = {"padding": "x" * PXC_MAX_SOURCE_CHARS}

    with pytest.raises(ValidationError):
        ActivitySource.model_validate(
            {"title": "t", "description": "d", "manifest": manifest, "ui_js": "", "sandbox_js": ""}
        )


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

    assert await run_bounded([sys.executable, "-c", script], tmp_path, "A step") == (3, "boom")


async def test_a_step_keeps_only_the_end_of_a_flood_of_stderr(tmp_path: Path) -> None:
    script = f"import sys; sys.stderr.write('x' * {PXC_BUILD_STDERR_LIMIT_BYTES * 4}); sys.stderr.write('END')"

    returncode, stderr = await run_bounded([sys.executable, "-c", script], tmp_path, "A step")

    assert returncode == 0
    assert len(stderr) <= PXC_BUILD_STDERR_LIMIT_BYTES
    assert stderr.endswith("END")


async def test_a_step_gets_a_bare_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPARKTH_TEST_SECRET", "x")
    script = "import os, sys; sys.stderr.write(' '.join(sorted(os.environ)))"

    _, names = await run_bounded([sys.executable, "-c", script], tmp_path, "A step")

    assert "SPARKTH_TEST_SECRET" not in names.split()
    assert {"PATH", "NO_COLOR"} <= set(names.split())


async def test_a_step_that_outlives_the_timeout_is_stopped(tmp_path: Path, short_timeout: None) -> None:
    started = time.monotonic()

    with pytest.raises(PxcBuildTimedOut) as timed_out:
        await run_bounded([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, "A step")

    assert time.monotonic() - started < 10
    assert "A step did not finish within 2 seconds" in str(timed_out.value)


async def test_a_timeout_kills_the_steps_grandchildren_too(tmp_path: Path, short_timeout: None) -> None:
    # node runs wizer as a child of its own; killing node alone leaves wizer spinning.
    pid_file = tmp_path / "grandchild.pid"

    with pytest.raises(PxcBuildTimedOut):
        await run_bounded([sys.executable, "-c", SPAWNS_A_GRANDCHILD, str(pid_file)], tmp_path, "A step")

    assert _process_gone(int(pid_file.read_text()))


async def test_cancelling_a_step_kills_its_process_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    step = asyncio.create_task(
        run_bounded([sys.executable, "-c", SPAWNS_A_GRANDCHILD, str(pid_file)], tmp_path, "A step")
    )
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text():
            break
        await asyncio.sleep(0.1)
    step.cancel()

    with pytest.raises(asyncio.CancelledError):
        await step

    assert _process_gone(int(pid_file.read_text()))


THROWS_AT_TOP_LEVEL = (
    'throw new Error("boom");\nexport function onAction() { return ""; }\nexport function getState() { return "{}"; }\n'
)


def _compile_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "compile"
    directory.mkdir()
    return directory


async def _compile_error(sandbox_js: str, tmp_path: Path) -> str:
    """The message a failed compile of ``sandbox_js`` hands the agent."""
    with pytest.raises(PxcCompileFailed) as refused:
        await compile_sandbox(sandbox_js, _compile_dir(tmp_path), tmp_path / "sandbox.wasm")
    return str(refused.value)


@pytest.mark.wasm
async def test_a_syntax_error_names_the_line_it_is_on(tmp_path: Path) -> None:
    sandbox_js = 'export function getState() { return "{}"\nexport function onAction() { return ""; }}}\n'

    message = await _compile_error(sandbox_js, tmp_path)

    assert "Unexpected token" in message
    assert "[sandbox.js:2:" in message


@pytest.mark.wasm
async def test_a_top_level_throw_names_the_line_it_came_from(tmp_path: Path) -> None:
    assert "sandbox.js:1:7 Error: boom" in await _compile_error(THROWS_AT_TOP_LEVEL, tmp_path)


@pytest.mark.wasm
async def test_a_missing_export_names_the_function_to_define(tmp_path: Path) -> None:
    sandbox_js = 'export function getState() { return "{}"; }\n'

    assert 'does not export a "onAction" function' in await _compile_error(sandbox_js, tmp_path)


@pytest.mark.wasm
async def test_a_compile_error_carries_no_toolchain_stack_or_server_path(tmp_path: Path) -> None:
    message = await _compile_error(THROWS_AT_TOP_LEVEL, tmp_path)

    assert "node_modules" not in message
    assert str(tmp_path) not in message


@pytest.mark.wasm
async def test_a_compile_error_keeps_the_end_of_a_long_message(tmp_path: Path) -> None:
    sandbox_js = (
        f'throw new Error("{"x" * PXC_BUILD_ERROR_LIMIT}");\n'
        'export function onAction() { return ""; }\nexport function getState() { return "{}"; }\n'
    )

    message = await _compile_error(sandbox_js, tmp_path)

    assert len(message) <= len("sandbox.js failed to compile:\n") + PXC_BUILD_ERROR_LIMIT
    assert message.endswith("@sandbox.js:1:7")


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
    assert '"../secret.js"' in str(refused.value)


@pytest.mark.wasm
async def test_a_compile_that_never_ends_is_stopped(tmp_path: Path, short_timeout: None) -> None:
    sandbox_js = (
        'while (true) {}\nexport function onAction() { return ""; }\nexport function getState() { return "{}"; }\n'
    )

    with pytest.raises(PxcBuildTimedOut):
        await compile_sandbox(sandbox_js, _compile_dir(tmp_path), tmp_path / "sandbox.wasm")


def _mcq_source(sandbox_js: str | None = None) -> ActivitySource:
    """The bundled sample's files as an agent would submit them, optionally with another sandbox."""
    return ActivitySource(
        title="Two plus two",
        description="A one-question check",
        manifest=MCQ_MANIFEST,
        ui_js=(MCQ / "ui.js").read_text(),
        sandbox_js=(MCQ / "sandbox.js").read_text() if sandbox_js is None else sandbox_js,
    )


@pytest.mark.wasm
async def test_a_built_activity_is_stored_and_launches(session: AsyncSession) -> None:
    activity = await build_activity(_mcq_source(), OWNER)

    activity_id = str(activity.id)
    assert activity_dir(activity_id) == generated_activity_dir(activity_id)
    assert json.loads((generated_activity_dir(activity_id) / "manifest.json").read_text())["name"] == activity_id
    assert (await get_owned_activity(session, activity.id, OWNER)).title == "Two plus two"
    runtime = build_runtime(LaunchClaims(activity_id, "instance-1", "course-1", "learner-7", Permission.play))
    assert read_state(runtime)["question"] == "What is 2 + 2?"


@pytest.mark.wasm
async def test_a_failing_get_state_leaves_no_activity_behind(session: AsyncSession, tmp_path: Path) -> None:
    throwing = (
        'export function onAction() { return ""; }\n'
        "export function getState() { const x = undefined; return x.boom; }\n"
    )

    with pytest.raises(PxcSmokeTestFailed) as failed:
        await build_activity(_mcq_source(throwing), OWNER)

    assert "boom" in str(failed.value)
    assert str(tmp_path) not in str(failed.value)
    assert await list_owned_activities(session, OWNER) == []
    assert list((tmp_path / "builds").iterdir()) == []
    assert not (tmp_path / "activities").exists()


@pytest.mark.wasm
async def test_a_compile_failure_leaves_no_activity_behind(session: AsyncSession, tmp_path: Path) -> None:
    with pytest.raises(PxcCompileFailed):
        await build_activity(_mcq_source("this is not javascript {"), OWNER)

    assert await list_owned_activities(session, OWNER) == []
    assert list((tmp_path / "builds").iterdir()) == []


@pytest.mark.wasm
async def test_a_timed_out_compile_leaves_no_activity_behind(tmp_path: Path, short_timeout: None) -> None:
    looping = (
        'while (true) {}\nexport function onAction() { return ""; }\nexport function getState() { return "{}"; }\n'
    )

    with pytest.raises(PxcBuildTimedOut):
        await build_activity(_mcq_source(looping), OWNER)

    assert list((tmp_path / "builds").iterdir()) == []


async def test_a_missing_toolchain_fails_without_blaming_the_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PXC_TOOLCHAIN_DIR", str(tmp_path / "no-toolchain"))
    get_pxc_settings.cache_clear()

    with pytest.raises(PxcCompileFailed) as failed:
        await build_activity(_mcq_source(), OWNER)

    assert "toolchain is not installed" in str(failed.value)
    assert list((tmp_path / "builds").iterdir()) == []


@pytest.mark.wasm
async def test_a_toolchain_without_its_packages_fails_without_blaming_the_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    toolchain = tmp_path / "toolchain"
    toolchain.mkdir()
    shutil.copyfile(TOOLCHAIN_DIR / "compile.mjs", toolchain / "compile.mjs")
    monkeypatch.setenv("PXC_TOOLCHAIN_DIR", str(toolchain))
    get_pxc_settings.cache_clear()

    with pytest.raises(PxcCompileFailed) as failed:
        await compile_sandbox(MCQ_SANDBOX_JS, _compile_dir(tmp_path), tmp_path / "sandbox.wasm")

    assert "toolchain is not installed" in str(failed.value)


async def test_an_invalid_manifest_fails_before_anything_is_written(tmp_path: Path) -> None:
    source = _mcq_source().model_copy(update={"manifest": {**MCQ_MANIFEST, "assets": ["a.png"]}})

    with pytest.raises(PxcManifestInvalid):
        await build_activity(source, OWNER)

    assert not (tmp_path / "builds").exists()


@pytest.mark.wasm
async def test_non_ascii_content_survives_the_build(session: AsyncSession) -> None:
    # An activity written in Spanish or French must serve its text unchanged.
    question = "¿Cuál es la capital de Francia? — été"
    manifest = json.loads(json.dumps(MCQ_MANIFEST))
    manifest["fields"]["question"]["default"] = question
    source = _mcq_source().model_copy(update={"manifest": manifest, "title": "Capitales — été"})

    activity = await build_activity(source, OWNER)

    claims = LaunchClaims(str(activity.id), "instance-1", "course-1", "learner-7", Permission.play)
    assert read_state(build_runtime(claims))["question"] == question
    assert (await get_owned_activity(session, activity.id, OWNER)).title == "Capitales — été"


async def _failing_insert(session: AsyncSession, activity: PxcActivity) -> None:
    raise OperationalError("insert", {}, Exception("db down"))


@pytest.mark.wasm
async def test_a_failed_insert_removes_the_moved_activity(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.builder.insert_activity", _failing_insert)

    with pytest.raises(OperationalError):
        await build_activity(_mcq_source(), OWNER)

    assert list((tmp_path / "activities").iterdir()) == []
