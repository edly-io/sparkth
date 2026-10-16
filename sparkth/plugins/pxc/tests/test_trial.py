"""Running an author's steps against an activity in a child process."""

import pytest

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.enums import PreviewPermission
from sparkth.plugins.pxc.exceptions import PxcTrialFailed, PxcTrialReportTooLarge, PxcTrialTimedOut
from sparkth.plugins.pxc.schemas import TrialStep
from sparkth.plugins.pxc.tests.conftest import CASE_STUDY_MANIFEST, CASE_STUDY_SANDBOX_JS, compiled_activity
from sparkth.plugins.pxc.trial import run_trial

SUBMIT = TrialStep(action="answer.submit", value=[1], permission=PreviewPermission.PLAY)


@pytest.mark.wasm
async def test_a_run_reports_each_steps_events_then_the_state_and_fields() -> None:
    report = await run_trial(activity_dir("mcq"), [SUBMIT])

    assert report["steps"][0]["error"] is None
    assert [event["name"] for event in report["steps"][0]["events"]] == ["answer.result"]
    assert [state["permission"] for state in report["state"]] == ["play", "edit"]
    assert report["fields"]["question"] == "What is 2 + 2?"


@pytest.mark.wasm
async def test_a_throwing_step_reports_what_it_threw() -> None:
    activity_id = await compiled_activity(CASE_STUDY_SANDBOX_JS, CASE_STUDY_MANIFEST)

    report = await run_trial(activity_dir(activity_id), [TrialStep(action="boom", permission=PreviewPermission.PLAY)])

    assert report["steps"][0]["error"] is not None
    assert report["steps"][0]["error"].startswith("boom from onAction")


@pytest.mark.wasm
async def test_a_step_the_manifest_refuses_is_that_steps_error() -> None:
    report = await run_trial(
        activity_dir("mcq"), [TrialStep(action="no.such.action", permission=PreviewPermission.PLAY), SUBMIT]
    )

    assert "no.such.action" in (report["steps"][0]["error"] or "")
    assert report["steps"][1]["error"] is None


@pytest.mark.wasm
async def test_a_step_that_never_ends_is_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    looping = CASE_STUDY_SANDBOX_JS.replace('throw new Error("boom from onAction")', "while (true) {}")
    assert looping != CASE_STUDY_SANDBOX_JS
    # Compiled first, under the normal timeout: the compile runs through run_bounded too.
    activity_id = await compiled_activity(looping, CASE_STUDY_MANIFEST)
    monkeypatch.setenv("PXC_BUILD_TIMEOUT_SECONDS", "2")
    get_pxc_settings.cache_clear()

    with pytest.raises(PxcTrialTimedOut) as timed_out:
        await run_trial(activity_dir(activity_id), [TrialStep(action="boom", permission=PreviewPermission.PLAY)])

    assert "while running boom as play." in str(timed_out.value)


@pytest.mark.wasm
async def test_a_report_over_the_limit_is_refused_with_its_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PXC_TRIAL_REPORT_LIMIT", "100")
    get_pxc_settings.cache_clear()

    with pytest.raises(PxcTrialReportTooLarge) as refused:
        await run_trial(activity_dir("mcq"), [SUBMIT])

    assert "over the 100 limit" in str(refused.value)


async def test_a_child_that_crashes_gives_a_message_with_no_server_path(caplog: pytest.LogCaptureFixture) -> None:
    missing = activity_dir("mcq").parent / "no-such-activity"

    with pytest.raises(PxcTrialFailed) as failed:
        await run_trial(missing, [SUBMIT])

    assert str(missing) not in str(failed.value)
    assert "Traceback" in caplog.text
