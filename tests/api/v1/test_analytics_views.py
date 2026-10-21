"""Tests for ``/api/v1/analytics/views``."""

import uuid

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.testing import grant_global_permission

URL = "/api/v1/analytics/views"
CONFIG = {"event": "auth.login", "filters": [], "measure": "count", "chart": "line"}


async def _users(session: AsyncSession, *, analytics_read: bool = True) -> None:
    session.add(User(id=1, name="Me", username="me", email="me@example.com", hashed_password="x"))
    session.add(User(id=2, name="Other", username="other", email="o@example.com", hashed_password="x"))
    await session.flush()
    if analytics_read:
        await grant_global_permission(session, 1, "analytics.read")
    await session.commit()


async def test_views_crud_round_trip(client: AsyncClient, session: AsyncSession, current_user: User) -> None:
    await _users(session)

    created = await client.post(URL, json={"name": "Logins", "config": CONFIG})
    assert created.status_code == 201
    view = created.json()
    assert (view["name"], view["config"]) == ("Logins", CONFIG)
    view_url = f"{URL}/{view['id']}"

    listed = await client.get(URL)
    assert listed.status_code == 200
    assert [v["id"] for v in listed.json()] == [view["id"]]

    assert (await client.get(view_url)).json()["name"] == "Logins"

    patched = await client.patch(view_url, json={"name": "Renamed"})
    assert patched.status_code == 200
    assert (patched.json()["name"], patched.json()["config"]) == ("Renamed", CONFIG)

    assert (await client.delete(view_url)).status_code == 204
    assert (await client.get(view_url)).status_code == 404


async def test_other_users_view_is_404_on_every_route(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await _users(session)
    from sparkth.services.analytics_views import create_view

    theirs = await create_view(session, 2, "Theirs", CONFIG)
    view_url = f"{URL}/{theirs.id}"

    assert (await client.get(view_url)).status_code == 404
    assert (await client.patch(view_url, json={"name": "x"})).status_code == 404
    assert (await client.delete(view_url)).status_code == 404
    assert (await client.get(f"{URL}/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(URL)).json() == []


async def test_duplicate_name_is_409(client: AsyncClient, session: AsyncSession, current_user: User) -> None:
    await _users(session)
    await client.post(URL, json={"name": "Logins", "config": CONFIG})

    response = await client.post(URL, json={"name": "Logins", "config": CONFIG})

    assert response.status_code == 409


async def test_name_must_be_non_empty_and_at_most_100_chars(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await _users(session)

    assert (await client.post(URL, json={"name": "", "config": CONFIG})).status_code == 422
    assert (await client.post(URL, json={"name": "x" * 101, "config": CONFIG})).status_code == 422


async def test_views_forbidden_without_analytics_read(
    client: AsyncClient, session: AsyncSession, current_user: User
) -> None:
    await _users(session, analytics_read=False)

    assert (await client.get(URL)).status_code == 403
    assert (await client.post(URL, json={"name": "Logins", "config": CONFIG})).status_code == 403
