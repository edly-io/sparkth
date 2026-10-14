"""Tests for the pxc MCP tools: the contract, building, listing and reading back activities."""

import json
from datetime import datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from pxc.lib.manifest_types import PxcActivityManifest
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.core.models.user import User
from sparkth.lib.auth import bind_current_user_id
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.models import utc_now
from sparkth.plugins.pxc.activities import generated_activity_dir, preview_url
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_ASSET_DIR, PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID
from sparkth.plugins.pxc.enums import PxcFailureKind
from sparkth.plugins.pxc.exceptions import (
    PxcActivityNotFound,
    PxcBuildFailed,
    PxcCompileFailed,
    PxcFieldsFrozen,
    PxcManifestInvalid,
)
from sparkth.plugins.pxc.models import PxcActionFailure, PxcActivity
from sparkth.plugins.pxc.revisions import publish_revision
from sparkth.plugins.pxc.schemas import ActivitySource, TrialStep
from sparkth.plugins.pxc.scratch.schemas import ScratchReport
from sparkth.plugins.pxc.store import insert_action_failure, insert_activity
from sparkth.plugins.pxc.tests.conftest import (
    AUTHORED_MANIFEST,
    AUTHORED_SANDBOX_JS,
    AUTHORED_UI_JS,
    THROWN_TEXT,
    act_as,
    staged_activity,
)
from sparkth.plugins.pxc.tokens import mint_launch_token, pin_launch_token
from sparkth.plugins.pxc.tools import (
    pxc_about,
    pxc_build_activity,
    pxc_get_activity_failures,
    pxc_get_activity_source,
    pxc_list_activities,
    pxc_run_activity,
    pxc_update_activity,
)


async def test_about_carries_the_contract_rules() -> None:
    about = (await pxc_about())["about"]

    rules = (PXC_ASSET_DIR / "about.txt").read_text(encoding="utf-8")
    assert rules.format(max_source_chars=get_pxc_settings().max_source_chars) in about


async def test_about_states_the_configured_source_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PXC_MAX_SOURCE_CHARS", "12345")
    get_pxc_settings.cache_clear()

    assert "12345" in (await pxc_about())["about"]


async def test_about_carries_the_manifest_schema() -> None:
    about = (await pxc_about())["about"]

    assert json.dumps(PxcActivityManifest.model_json_schema(), indent=2) in about


MANIFEST: dict[str, object] = {"name": "poll", "ui": "ui.js", "sandbox": "sandbox.wasm"}


async def test_build_returns_the_new_activitys_id_and_preview_url() -> None:
    bind_current_user_id(7)
    built = PxcActivity(id=uuid7(), owner_user_id=7, title="Poll", description="A one-question poll")
    with patch("sparkth.plugins.pxc.tools.build_activity", new=AsyncMock(return_value=built)) as build:
        result = await pxc_build_activity("Poll", "A one-question poll", MANIFEST, "ui", "sandbox")

    build.assert_awaited_once_with(
        ActivitySource(
            title="Poll", description="A one-question poll", manifest=MANIFEST, ui_js="ui", sandbox_js="sandbox"
        ),
        7,
    )
    assert result == {"activity_id": str(built.id), "preview_url": preview_url(built.id)}


async def test_a_failed_build_reaches_the_agent_with_its_message() -> None:
    # Raised, not caught: both tool paths render str(exc) as the tool result the agent reads.
    bind_current_user_id(7)
    failure = PxcCompileFailed("sandbox.js:3:7 Unexpected token")
    with (
        patch("sparkth.plugins.pxc.tools.build_activity", new=AsyncMock(side_effect=failure)),
        pytest.raises(PxcBuildFailed) as caught,
    ):
        await pxc_build_activity("Poll", "A one-question poll", MANIFEST, "ui", "sandbox")

    assert str(caught.value) == "sandbox.js:3:7 Unexpected token"


async def test_a_manifest_sent_as_json_text_is_read_as_the_object() -> None:
    bind_current_user_id(7)
    built = PxcActivity(id=uuid7(), owner_user_id=7, title="Poll", description="A one-question poll")
    with patch("sparkth.plugins.pxc.tools.build_activity", new=AsyncMock(return_value=built)) as build:
        await pxc_build_activity("Poll", "A one-question poll", json.dumps(MANIFEST), "ui", "sandbox")

    assert build.await_args is not None
    assert build.await_args.args[0].manifest == MANIFEST


async def test_manifest_text_that_is_not_json_is_refused_with_a_fixable_message() -> None:
    bind_current_user_id(7)
    with pytest.raises(PxcManifestInvalid) as refused:
        await pxc_build_activity("Poll", "A one-question poll", "{not json", "ui", "sandbox")

    assert "not valid JSON" in str(refused.value)


async def test_an_unauthenticated_build_is_refused_before_its_manifest_is_read() -> None:
    with pytest.raises(NoAuthenticatedUser):
        await pxc_build_activity("Poll", "A one-question poll", "{not json", "ui", "sandbox")


async def test_manifest_json_that_is_not_an_object_is_refused_as_the_wrong_type() -> None:
    bind_current_user_id(7)
    with pytest.raises(PxcManifestInvalid) as refused:
        await pxc_build_activity("Poll", "A one-question poll", "[1, 2]", "ui", "sandbox")

    assert str(refused.value) == "manifest must be a JSON object, got list"


async def test_list_returns_the_authors_activities_with_preview_links(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])

    result = await pxc_list_activities()
    stored = datetime.fromisoformat(str(result["activities"][0]["created_at"]))
    assert stored.replace(tzinfo=None) == authored_activity.created_at.replace(tzinfo=None)

    assert result == {
        "activities": [
            {
                "activity_id": str(authored_activity.id),
                "title": "Capital cities",
                "created_at": result["activities"][0]["created_at"],
                "preview_url": preview_url(authored_activity.id),
                "placed": False,
            }
        ]
    }


async def test_list_keeps_only_the_newest_activities_up_to_the_limit(
    session: AsyncSession, authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    older = PxcActivity(
        owner_user_id=authored_activity.owner_user_id,
        title="Older",
        description="Built a day earlier",
        created_at=utc_now() - timedelta(days=1),
    )
    await insert_activity(session, older)
    await session.commit()
    act_as(authors[0])

    result = await pxc_list_activities(1)

    assert [listed["activity_id"] for listed in result["activities"]] == [str(authored_activity.id)]


async def test_list_defaults_to_the_configured_limit(
    session: AsyncSession, authored_activity: PxcActivity, authors: tuple[User, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PXC_LIST_ACTIVITIES_LIMIT", "1")
    get_pxc_settings.cache_clear()
    older = PxcActivity(
        owner_user_id=authored_activity.owner_user_id,
        title="Older",
        description="Built a day earlier",
        created_at=utc_now() - timedelta(days=1),
    )
    await insert_activity(session, older)
    await session.commit()
    act_as(authors[0])

    result = await pxc_list_activities()

    assert [listed["activity_id"] for listed in result["activities"]] == [str(authored_activity.id)]


async def test_list_leaves_out_another_authors_activities(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[1])

    assert await pxc_list_activities() == {"activities": []}


async def test_source_returns_the_owners_files(authored_activity: PxcActivity, authors: tuple[User, User]) -> None:
    act_as(authors[0])

    source = await pxc_get_activity_source(str(authored_activity.id))

    assert source == {
        "activity_id": str(authored_activity.id),
        "title": "Capital cities",
        "description": "Match countries to capitals",
        "manifest": AUTHORED_MANIFEST,
        "ui_js": AUTHORED_UI_JS,
        "sandbox_js": AUTHORED_SANDBOX_JS,
        "placed": False,
    }


async def test_list_and_source_report_a_placed_activity_as_placed(
    session: AsyncSession, authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    authored_activity.placed_at = utc_now()
    session.add(authored_activity)
    await session.commit()
    act_as(authors[0])

    listed = (await pxc_list_activities())["activities"][0]
    source = await pxc_get_activity_source(str(authored_activity.id))

    assert listed["placed"] is True
    assert source["placed"] is True


async def test_source_refuses_another_authors_activity(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[1])

    with pytest.raises(PxcActivityNotFound):
        await pxc_get_activity_source(str(authored_activity.id))


async def test_source_with_missing_files_is_not_found_without_a_server_path(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])
    directory = generated_activity_dir(str(authored_activity.id))
    (directory / "ui.js").unlink()

    with pytest.raises(PxcActivityNotFound) as refused:
        await pxc_get_activity_source(str(authored_activity.id))

    assert str(refused.value) == f"Unknown activity: {authored_activity.id}"


async def test_source_with_an_unreadable_manifest_is_not_found(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])
    directory = generated_activity_dir(str(authored_activity.id))
    (directory / "manifest.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(PxcActivityNotFound):
        await pxc_get_activity_source(str(authored_activity.id))


async def test_an_unauthenticated_source_read_is_refused_before_its_id_is_read() -> None:
    with pytest.raises(NoAuthenticatedUser):
        await pxc_get_activity_source("../../mcq")


async def test_source_refuses_an_id_that_is_not_a_uuid(authors: tuple[User, User]) -> None:
    # Refused before any path is built from it, so it can never walk out of the data directory.
    act_as(authors[0])

    with pytest.raises(PxcActivityNotFound):
        await pxc_get_activity_source("../../mcq")


async def test_update_hands_the_activity_its_edited_files() -> None:
    bind_current_user_id(7)
    activity_id = uuid7()
    with patch("sparkth.plugins.pxc.tools.update_activity", new=AsyncMock()) as update:
        result = await pxc_update_activity(str(activity_id), "Poll", "A one-question poll", MANIFEST, "ui", "sandbox")

    update.assert_awaited_once_with(
        activity_id,
        ActivitySource(
            title="Poll", description="A one-question poll", manifest=MANIFEST, ui_js="ui", sandbox_js="sandbox"
        ),
        7,
    )
    assert result == {"activity_id": str(activity_id), "preview_url": preview_url(activity_id)}


async def test_update_reads_a_manifest_sent_as_json_text() -> None:
    bind_current_user_id(7)
    with patch("sparkth.plugins.pxc.tools.update_activity", new=AsyncMock()) as update:
        await pxc_update_activity(str(uuid7()), "Poll", "A one-question poll", json.dumps(MANIFEST), "ui", "sandbox")

    assert update.await_args is not None
    assert update.await_args.args[1].manifest == MANIFEST


@pytest.mark.parametrize("name", ["mcq", "../../mcq", str(uuid7()).upper()])
async def test_update_refuses_a_name_that_is_not_a_generated_activity(name: str) -> None:
    bind_current_user_id(7)
    with (
        patch("sparkth.plugins.pxc.tools.update_activity", new=AsyncMock()) as update,
        pytest.raises(PxcActivityNotFound),
    ):
        await pxc_update_activity(name, "Poll", "A one-question poll", MANIFEST, "ui", "sandbox")

    update.assert_not_awaited()


async def test_an_unauthenticated_update_is_refused_before_its_id_is_read() -> None:
    with pytest.raises(NoAuthenticatedUser):
        await pxc_update_activity("../../mcq", "Poll", "A one-question poll", MANIFEST, "ui", "sandbox")


async def test_a_refused_update_reaches_the_agent_with_its_message() -> None:
    bind_current_user_id(7)
    refusal = PxcFieldsFrozen("Nothing was updated. field 'question' was removed")
    with (
        patch("sparkth.plugins.pxc.tools.update_activity", new=AsyncMock(side_effect=refusal)),
        pytest.raises(PxcBuildFailed) as caught,
    ):
        await pxc_update_activity(str(uuid7()), "Poll", "A one-question poll", MANIFEST, "ui", "sandbox")

    assert str(caught.value) == "Nothing was updated. field 'question' was removed"


def _recorded(activity: PxcActivity, revision: str | None, action: str, kind: PxcFailureKind) -> PxcActionFailure:
    return PxcActionFailure(
        activity_id=activity.id,
        revision=revision,
        kind=kind,
        action=action,
        permission="play",
        value="[0]",
        error="boom",
    )


async def test_failures_come_back_newest_first_with_their_kind(
    session: AsyncSession, authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    await insert_action_failure(session, _recorded(authored_activity, None, "place", PxcFailureKind.REJECTED), 20)
    await insert_action_failure(session, _recorded(authored_activity, None, "check", PxcFailureKind.FAILED), 20)
    act_as(authors[0])

    failures = (await pxc_get_activity_failures(str(authored_activity.id)))["failures"]

    assert [(failure["action"], failure["kind"]) for failure in failures] == [
        ("check", "failed"),
        ("place", "rejected"),
    ]
    assert failures[0]["error"] == "boom"


async def test_only_the_live_revisions_failures_come_back(
    session: AsyncSession, authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    activity_id = str(authored_activity.id)
    older = publish_revision(staged_activity("first"), activity_id).name
    live = publish_revision(staged_activity("second"), activity_id).name
    await insert_action_failure(session, _recorded(authored_activity, older, "before", PxcFailureKind.FAILED), 20)
    await insert_action_failure(session, _recorded(authored_activity, live, "after", PxcFailureKind.FAILED), 20)
    act_as(authors[0])

    assert [failure["action"] for failure in (await pxc_get_activity_failures(activity_id))["failures"]] == ["after"]


async def test_a_failure_in_the_authors_pinned_preview_reaches_the_tool(
    client: AsyncClient,
    authored_activity: PxcActivity,
    authors: tuple[User, User],
    configured_secret: str,
    throwing_sandbox: None,
) -> None:
    activity_id = str(authored_activity.id)
    revision = publish_revision(staged_activity("q"), activity_id).name
    token = mint_launch_token(
        activity_id, PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID, "sparkth-1", "play", configured_secret, 300
    )

    response = await client.post(
        "/api/v1/pxc/actions/answer.submit", params={"token": pin_launch_token(token, revision)}, json=[0]
    )
    act_as(authors[0])
    failures = (await pxc_get_activity_failures(activity_id))["failures"]

    assert response.status_code == 422
    assert [(failure["action"], failure["error"]) for failure in failures] == [("answer.submit", THROWN_TEXT)]


async def test_failures_of_another_authors_activity_are_refused(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[1])

    with pytest.raises(PxcActivityNotFound):
        await pxc_get_activity_failures(str(authored_activity.id))


async def test_run_hands_the_live_files_and_validated_steps_to_the_trial(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])
    report: ScratchReport = {"steps": [], "state": [], "fields": {}}
    steps = cast(list[TrialStep], [{"action": "check", "permission": "play"}])

    with patch("sparkth.plugins.pxc.tools.run_trial", AsyncMock(return_value=report)) as trial:
        assert await pxc_run_activity(str(authored_activity.id), steps) == report

    assert trial.await_args is not None
    directory, validated = trial.await_args.args
    assert directory == generated_activity_dir(str(authored_activity.id)).resolve()
    assert [(step.action, step.permission.value, step.value) for step in validated] == [("check", "play", "")]


async def test_a_view_step_is_refused_before_anything_runs(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[0])
    steps = cast(list[TrialStep], [{"action": "check", "permission": "view"}])

    with patch("sparkth.plugins.pxc.tools.run_trial", AsyncMock()) as trial:
        with pytest.raises(ValidationError):
            await pxc_run_activity(str(authored_activity.id), steps)

    trial.assert_not_awaited()


async def test_more_steps_than_the_limit_are_refused_before_anything_runs(
    authored_activity: PxcActivity, authors: tuple[User, User], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PXC_TRIAL_STEP_LIMIT", "2")
    get_pxc_settings.cache_clear()
    act_as(authors[0])
    steps = cast(list[TrialStep], [{"action": "check", "permission": "play"}] * 3)

    with patch("sparkth.plugins.pxc.tools.run_trial", AsyncMock()) as trial:
        with pytest.raises(ValidationError):
            await pxc_run_activity(str(authored_activity.id), steps)

    trial.assert_not_awaited()


async def test_running_another_authors_activity_is_refused(
    authored_activity: PxcActivity, authors: tuple[User, User]
) -> None:
    act_as(authors[1])
    steps = cast(list[TrialStep], [{"action": "check", "permission": "play"}])

    with pytest.raises(PxcActivityNotFound):
        await pxc_run_activity(str(authored_activity.id), steps)
