"""The author's own activities, behind their Sparkth session."""

import json
from typing import cast
from urllib.parse import parse_qs, urlsplit

from httpx import AsyncClient
from pxc.lib.permission import Permission
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.lib.models import User
from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.store import insert_activity
from sparkth.plugins.pxc.tokens import read_launch_token

OTHER_USER = 2


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
