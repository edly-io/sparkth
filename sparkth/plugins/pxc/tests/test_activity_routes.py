"""The author's own activities, behind their Sparkth session."""

import json
import logging
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from pxc.lib.permission import Permission
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.lib.models import User, utc_now
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir, state_file
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.store import insert_activity
from sparkth.plugins.pxc.tokens import read_launch_token

OTHER_USER = 2


def _rmtree_busy(path: Path) -> None:
    raise OSError("busy")


async def _failing_record_event(session: AsyncSession, event: object) -> None:
    raise SQLAlchemyError("audit unavailable")


def _write_state_and_storage(activity: PxcActivity) -> list[Path]:
    """Write the activity's learner state file and a storage file; return both paths."""
    activity_id = str(activity.id)
    stored = get_pxc_settings().data_dir / "storage" / activity_id / "answer.txt"
    stored.parent.mkdir(parents=True)
    paths = [state_file(activity_id), stored]
    for path in paths:
        path.write_text("x")
    return paths


async def _row_exists(session: AsyncSession, activity_id: object) -> bool:
    return (await session.exec(select(PxcActivity).where(PxcActivity.id == activity_id))).first() is not None


async def _insert_owned(session: AsyncSession, owner_user_id: int) -> PxcActivity:
    activity = PxcActivity(owner_user_id=owner_user_id, title="Fractions", description="Order three fractions")
    await insert_activity(session, activity)
    return activity


def _write_built_files(activity: PxcActivity) -> None:
    """Lay down the manifest a launch resolves the activity by, as a finished build leaves it.

    The autouse ``pxc_settings`` fixture points ``PXC_DATA_DIR`` at this test's ``tmp_path``.
    """
    directory = generated_activity_dir(str(activity.id))
    directory.mkdir(parents=True)
    manifest = json.loads((activity_dir("mcq") / "manifest.json").read_text(encoding="utf-8"))
    (directory / "manifest.json").write_text(json.dumps({**manifest, "name": str(activity.id)}), encoding="utf-8")


async def test_listing_activities_needs_a_session(client: AsyncClient) -> None:
    response = await client.get("/api/v1/pxc/activities")

    assert response.status_code == 401


async def test_an_author_lists_only_their_own_activities(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    mine = await _insert_owned(session, cast(int, current_user.id))
    await _insert_owned(session, OTHER_USER)

    response = await client.get("/api/v1/pxc/activities")

    assert response.status_code == 200
    assert [(item["id"], item["title"], item["preview_url"]) for item in response.json()] == [
        (str(mine.id), "Fractions", f"/dashboard/pxc?activity={mine.id}")
    ]


async def test_the_list_says_whether_each_activity_was_placed(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    owner = cast(int, current_user.id)
    draft = await _insert_owned(session, owner)
    placed = PxcActivity(owner_user_id=owner, title="Placed", description="In a course", placed_at=utc_now())
    await insert_activity(session, placed)

    response = await client.get("/api/v1/pxc/activities")

    assert {item["id"]: item["placed"] for item in response.json()} == {str(placed.id): True, str(draft.id): False}


async def test_an_author_gets_an_embed_url_for_their_own_activity(
    client: AsyncClient, session: AsyncSession, current_user: User, configured_secret: str
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))
    _write_built_files(activity)

    response = await client.get(f"/api/v1/pxc/activities/{activity.id}/launch", params={"permission": "edit"})

    assert response.status_code == 200
    embed_url = urlsplit(response.json()["embed_url"])
    claims = read_launch_token(parse_qs(embed_url.query)["token"][0])
    assert embed_url.path == "/api/v1/pxc/embed"
    assert (claims.activity, claims.permission) == (str(activity.id), Permission.edit)


async def test_another_users_activity_cannot_be_launched(
    client: AsyncClient, session: AsyncSession, current_user: User, configured_secret: str
) -> None:
    activity = await _insert_owned(session, OTHER_USER)

    response = await client.get(f"/api/v1/pxc/activities/{activity.id}/launch", params={"permission": "play"})

    assert response.status_code == 404


async def test_an_unknown_activity_cannot_be_launched(
    client: AsyncClient, current_user: User, configured_secret: str
) -> None:
    response = await client.get(f"/api/v1/pxc/activities/{uuid7()}/launch", params={"permission": "play"})

    assert response.status_code == 404


async def test_a_launch_asks_for_play_or_edit_only(
    client: AsyncClient, session: AsyncSession, current_user: User, configured_secret: str
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))

    response = await client.get(f"/api/v1/pxc/activities/{activity.id}/launch", params={"permission": "view"})

    assert response.status_code == 422


async def test_a_launch_without_a_configured_secret_is_unavailable(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))
    _write_built_files(activity)

    response = await client.get(f"/api/v1/pxc/activities/{activity.id}/launch", params={"permission": "play"})

    assert response.status_code == 503


async def test_an_owned_activity_with_no_files_on_disk_cannot_be_launched(
    client: AsyncClient, session: AsyncSession, current_user: User, configured_secret: str
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))

    response = await client.get(f"/api/v1/pxc/activities/{activity.id}/launch", params={"permission": "play"})

    assert response.status_code == 404


async def test_an_author_deletes_their_own_activity(
    client: AsyncClient, session: AsyncSession, current_user: User, audit_events: AuditEventsFetcher
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))
    _write_built_files(activity)
    extra = _write_state_and_storage(activity)
    built = generated_activity_dir(str(activity.id))
    await session.commit()

    response = await client.delete(f"/api/v1/pxc/activities/{activity.id}")

    assert response.status_code == 204
    assert not await _row_exists(session, activity.id)
    assert not any(path.exists() for path in [built, *extra])
    (event,) = await audit_events()
    assert (event.actor_type, event.actor_id) == ("user", str(current_user.id))


async def test_deleting_twice_is_not_found_the_second_time(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))
    await session.commit()

    first = await client.delete(f"/api/v1/pxc/activities/{activity.id}")
    second = await client.delete(f"/api/v1/pxc/activities/{activity.id}")

    assert (first.status_code, second.status_code) == (204, 404)


async def test_another_users_activity_cannot_be_deleted(
    client: AsyncClient, session: AsyncSession, current_user: User, audit_events: AuditEventsFetcher
) -> None:
    activity = await _insert_owned(session, OTHER_USER)
    _write_built_files(activity)
    built = generated_activity_dir(str(activity.id))
    await session.commit()

    response = await client.delete(f"/api/v1/pxc/activities/{activity.id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Unknown activity: {activity.id}"}
    assert await _row_exists(session, activity.id)
    assert built.exists()
    assert await audit_events() == []


async def test_an_unknown_activity_cannot_be_deleted(client: AsyncClient, current_user: User) -> None:
    unknown = uuid7()

    response = await client.delete(f"/api/v1/pxc/activities/{unknown}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Unknown activity: {unknown}"}


async def test_a_bundled_name_cannot_be_deleted(client: AsyncClient, current_user: User) -> None:
    response = await client.delete("/api/v1/pxc/activities/mcq")

    assert response.status_code == 422


async def test_deleting_needs_a_session(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/pxc/activities/{uuid7()}")

    assert response.status_code == 401


async def test_an_activity_with_no_files_on_disk_can_still_be_deleted(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))
    await session.commit()

    response = await client.delete(f"/api/v1/pxc/activities/{activity.id}")

    assert response.status_code == 204
    assert not await _row_exists(session, activity.id)


async def test_a_failed_file_removal_still_deletes_the_activity(
    client: AsyncClient,
    session: AsyncSession,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))
    _write_built_files(activity)
    await session.commit()
    monkeypatch.setattr("sparkth.plugins.pxc.revisions.shutil.rmtree", _rmtree_busy)

    response = await client.delete(f"/api/v1/pxc/activities/{activity.id}")

    assert response.status_code == 204
    assert not await _row_exists(session, activity.id)
    assert any(r.levelno == logging.WARNING and str(activity.id) in r.getMessage() for r in caplog.records)


async def test_a_failed_audit_record_keeps_the_activity_and_its_files(
    client: AsyncClient, session: AsyncSession, current_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    activity = await _insert_owned(session, cast(int, current_user.id))
    _write_built_files(activity)
    built = generated_activity_dir(str(activity.id))
    await session.commit()
    monkeypatch.setattr("sparkth.plugins.pxc.store.record_event", _failing_record_event)

    with pytest.raises(SQLAlchemyError):
        await client.delete(f"/api/v1/pxc/activities/{activity.id}")

    assert await _row_exists(session, activity.id)
    assert built.exists()
