"""Tests for the pxc MCP tools: the contract, building, listing and reading back activities."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pxc.lib.manifest_types import PxcActivityManifest
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.core.models.user import User
from sparkth.lib.auth import bind_current_user_id
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.models import utc_now
from sparkth.plugins.pxc import tools
from sparkth.plugins.pxc.activities import generated_activity_dir, preview_url
from sparkth.plugins.pxc.constants import PXC_ASSET_DIR, PXC_MAX_SOURCE_CHARS
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcBuildFailed, PxcCompileFailed, PxcManifestInvalid
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.schemas import ActivitySource
from sparkth.plugins.pxc.store import insert_activity
from sparkth.plugins.pxc.tests.conftest import AUTHORED_MANIFEST, AUTHORED_SANDBOX_JS, AUTHORED_UI_JS, act_as
from sparkth.plugins.pxc.tools import pxc_about, pxc_build_activity, pxc_get_activity_source, pxc_list_activities


async def test_about_carries_the_contract_rules() -> None:
    about = (await pxc_about())["about"]

    rules = (PXC_ASSET_DIR / "about.txt").read_text(encoding="utf-8")
    assert rules.format(max_source_chars=PXC_MAX_SOURCE_CHARS) in about


async def test_about_states_the_current_source_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "PXC_MAX_SOURCE_CHARS", 12345)

    assert "12345" in (await tools.pxc_about())["about"]


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
    stored = datetime.fromisoformat(result["activities"][0]["created_at"])
    assert stored.replace(tzinfo=None) == authored_activity.created_at.replace(tzinfo=None)

    assert result == {
        "activities": [
            {
                "activity_id": str(authored_activity.id),
                "title": "Capital cities",
                "created_at": result["activities"][0]["created_at"],
                "preview_url": preview_url(authored_activity.id),
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
    }


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
