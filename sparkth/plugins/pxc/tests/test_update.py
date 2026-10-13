"""Updating a generated activity in place: what changes, what a placed activity refuses, what a draft loses."""

import json
from pathlib import Path
from uuid import UUID

import pytest
from pxc.lib.permission import Permission
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.db import session_scope
from sparkth.lib.models import User
from sparkth.plugins.pxc.activities import activity_dir, state_file
from sparkth.plugins.pxc.builder import build_activity, update_activity
from sparkth.plugins.pxc.constants import PXC_PREVIEW_ACTIVITY_INSTANCE, PXC_PREVIEW_COURSE_ID
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcCompileFailed, PxcFieldsFrozen
from sparkth.plugins.pxc.field_store.sqlite import SqliteFieldStore
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.revisions import remove_activity_files, revisions_dir
from sparkth.plugins.pxc.runtime import build_runtime, read_state
from sparkth.plugins.pxc.schemas import ActivitySource
from sparkth.plugins.pxc.store import get_owned_activity, mark_placed
from sparkth.plugins.pxc.tests.conftest import AUTHORED_SANDBOX_JS, stage_without_compiling
from sparkth.plugins.pxc.tokens import LaunchClaims

QUESTION: dict[str, object] = {"type": "string", "scope": "activity", "default": "What is 2 + 2?"}
RETYPED: dict[str, object] = {"question": {**QUESTION, "type": "integer", "default": 4}}
UI_JS = "export function setup(activity) {}\n"

# The activity _stage_while_placing places; a test sets it with monkeypatch.
PLACED_DURING_BUILD: list[UUID] = []


def _source(fields: dict[str, object], ui_js: str = UI_JS, title: str = "Capital cities") -> ActivitySource:
    """An agent's submission for an activity whose manifest declares ``fields``."""
    return ActivitySource(
        title=title,
        description="Match countries to capitals",
        manifest={"name": "placeholder", "ui": "ui.js", "sandbox": "sandbox.wasm", "fields": fields},
        ui_js=ui_js,
        sandbox_js=AUTHORED_SANDBOX_JS,
    )


def _live_manifest(activity: PxcActivity) -> dict[str, object]:
    """The live revision's manifest."""
    manifest: dict[str, object] = json.loads((activity_dir(str(activity.id)) / "manifest.json").read_text())
    return manifest


def _live_ui(activity: PxcActivity) -> str:
    """The live revision's ui.js."""
    return (activity_dir(str(activity.id)) / "ui.js").read_text()


def _preview_store(activity: PxcActivity) -> SqliteFieldStore:
    """The activity's state file, where its preview saves what the author typed."""
    return SqliteFieldStore(state_file(str(activity.id)))


def _save_preview_question(activity: PxcActivity, question: str) -> None:
    """Save a question the way the preview's author view would."""
    _preview_store(activity).set(
        PXC_PREVIEW_COURSE_ID, str(activity.id), PXC_PREVIEW_ACTIVITY_INSTANCE, "", "question", question
    )


def _preview_question(activity: PxcActivity) -> object:
    """The question the preview saved, or None."""
    return _preview_store(activity).get(
        PXC_PREVIEW_COURSE_ID, str(activity.id), PXC_PREVIEW_ACTIVITY_INSTANCE, "", "question"
    )


async def _failing_stage(work: Path, manifest: dict[str, object], source: ActivitySource) -> Path:
    raise PxcCompileFailed("sandbox.js failed to compile")


async def _stage_while_placing(work: Path, manifest: dict[str, object], source: ActivitySource) -> Path:
    """Stage the files, with the activity placed in a course while it compiles."""
    async with session_scope() as session:
        await mark_placed(session, PLACED_DURING_BUILD[0])
    return await stage_without_compiling(work, manifest, source)


@pytest.fixture
def owner_id(authors: tuple[User, User]) -> int:
    """The id of the author who owns the activities built here."""
    assert authors[0].id is not None
    return authors[0].id


@pytest.fixture
def other_id(authors: tuple[User, User]) -> int:
    """The id of an author who owns nothing."""
    assert authors[1].id is not None
    return authors[1].id


@pytest.fixture
async def draft(uncompiled_builds: None, owner_id: int) -> PxcActivity:
    """One activity the owner built and never placed."""
    return await build_activity(_source({"question": QUESTION}), owner_id)


@pytest.fixture
async def placed(draft: PxcActivity) -> PxcActivity:
    """The draft, after it was placed in a course."""
    async with session_scope() as session:
        await mark_placed(session, draft.id)
    return draft


async def test_an_update_replaces_the_live_files_under_the_same_id(draft: PxcActivity, owner_id: int) -> None:
    await update_activity(draft.id, _source({"question": QUESTION}, "// v2\n"), owner_id)

    assert _live_ui(draft) == "// v2\n"


async def test_an_update_saves_the_title_and_description(
    session: AsyncSession, draft: PxcActivity, owner_id: int
) -> None:
    await update_activity(draft.id, _source({"question": QUESTION}, UI_JS, "Capitals of Europe"), owner_id)

    assert (await get_owned_activity(session, draft.id, owner_id)).title == "Capitals of Europe"


async def test_another_author_cannot_update_an_activity(
    draft: PxcActivity, other_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.builder.stage_activity", _failing_stage)

    with pytest.raises(PxcActivityNotFound):
        await update_activity(draft.id, _source({"question": QUESTION}, "// stolen\n"), other_id)

    assert _live_ui(draft) == UI_JS


async def test_an_activity_whose_files_are_gone_cannot_be_updated(
    draft: PxcActivity, owner_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.builder.stage_activity", _failing_stage)
    remove_activity_files(str(draft.id))

    with pytest.raises(PxcActivityNotFound):
        await update_activity(draft.id, _source({"question": QUESTION}), owner_id)


async def test_a_failed_build_leaves_the_live_activity_unchanged(
    draft: PxcActivity, owner_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sparkth.plugins.pxc.builder.stage_activity", _failing_stage)

    with pytest.raises(PxcCompileFailed):
        await update_activity(draft.id, _source({"question": QUESTION}, "// v2\n"), owner_id)

    assert _live_ui(draft) == UI_JS
    assert len(list(revisions_dir(str(draft.id)).iterdir())) == 1


async def test_a_placed_activity_refuses_a_field_change(placed: PxcActivity, owner_id: int) -> None:
    with pytest.raises(PxcFieldsFrozen) as refused:
        await update_activity(placed.id, _source(RETYPED, "// v2\n"), owner_id)

    assert "'question'" in str(refused.value)
    assert _live_manifest(placed)["fields"] == {"question": QUESTION}
    assert _live_ui(placed) == UI_JS


async def test_a_placed_activity_accepts_code_action_default_and_new_field_changes(
    placed: PxcActivity, owner_id: int
) -> None:
    fields: dict[str, object] = {
        "question": {**QUESTION, "default": "What is 3 + 3?"},
        "hints_used": {"type": "integer", "scope": "user,activity"},
    }
    source = _source(fields, "// v2\n")
    source.manifest["actions"] = {"hint": {"type": "boolean"}}

    await update_activity(placed.id, source, owner_id)

    live = _live_manifest(placed)
    assert live["fields"] == fields
    assert live["actions"] == {"hint": {"type": "boolean"}}
    assert _live_ui(placed) == "// v2\n"


async def test_a_draft_accepts_a_field_change_and_loses_its_preview_state(draft: PxcActivity, owner_id: int) -> None:
    _save_preview_question(draft, "What is the capital of France?")

    await update_activity(draft.id, _source(RETYPED), owner_id)

    assert _live_manifest(draft)["fields"] == RETYPED
    assert _preview_question(draft) is None


async def test_a_drafts_default_change_keeps_its_preview_state(draft: PxcActivity, owner_id: int) -> None:
    _save_preview_question(draft, "What is the capital of France?")

    await update_activity(draft.id, _source({"question": {**QUESTION, "default": "What is 3 + 3?"}}), owner_id)

    assert _preview_question(draft) == "What is the capital of France?"


async def test_a_placement_made_during_the_build_is_seen(
    draft: PxcActivity, owner_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(f"{__name__}.PLACED_DURING_BUILD", [draft.id])
    monkeypatch.setattr("sparkth.plugins.pxc.builder.stage_activity", _stage_while_placing)

    with pytest.raises(PxcFieldsFrozen):
        await update_activity(draft.id, _source(RETYPED), owner_id)


@pytest.mark.wasm
async def test_an_updated_activity_launches_with_its_new_content(owner_id: int) -> None:
    mcq = activity_dir("mcq")
    manifest = json.loads((mcq / "manifest.json").read_text())
    source = ActivitySource(
        title="Two plus two",
        description="A one-question check",
        manifest=manifest,
        ui_js=(mcq / "ui.js").read_text(),
        sandbox_js=(mcq / "sandbox.js").read_text(),
    )
    activity = await build_activity(source, owner_id)
    manifest["fields"]["question"]["default"] = "What is 3 + 3?"

    await update_activity(activity.id, source.model_copy(update={"manifest": manifest}), owner_id)

    claims = LaunchClaims(str(activity.id), "instance-1", "course-1", "learner-7", Permission.play)
    assert read_state(build_runtime(claims))["question"] == "What is 3 + 3?"
