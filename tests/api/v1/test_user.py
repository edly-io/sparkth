"""Tests for the /user/me endpoint: the computed is_admin flag and the
preferred-language column exposed via GET and PATCH.

is_admin is not a stored column — it is derived from whether the user holds the
global ``admin`` role, so those tests seed role assignments and assert the
endpoint reflects them. The language tests cover reading the raw stored
preference and writing it through PATCH, including the allowlist validation that
keeps unsupported tags out of the database, the auth gate on the write endpoint,
and that a PATCH only ever touches the caller's own row.
"""

from typing import cast

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session
from sparkth.lib.permissions import assign_role
from sparkth.lib.permissions.scopes import GLOBAL, PermissionScope


async def _create_user(session: AsyncSession, username: str) -> User:
    user = User(
        name="Test",
        username=username,
        email=f"{username}@example.com",
        hashed_password="fakehash",
    )
    session.add(user)
    await session.flush()
    return user


def _override_current_user(client: AsyncClient, user: User) -> None:
    """Stand in for ``get_current_user``, resolved on the request's own session.

    Production ``get_current_user`` takes ``session: AsyncSession =
    Depends(get_async_session)`` and looks the row up by JWT subject; FastAPI
    caches that dependency per request, so the returned user is attached to the
    very same session the route body uses. This override takes the same
    dependency for the same reason: a value one request writes (e.g. a PATCHed
    ``language``) must be visible to a later GET on the same client, and a
    detached snapshot frozen at override time would not be.
    """
    transport = cast(ASGITransport, client._transport)
    app_instance = cast(FastAPI, transport.app)
    user_id = user.id

    async def override(session: AsyncSession = Depends(get_async_session)) -> User:
        result = await session.exec(select(User).where(User.id == user_id))
        return result.one()

    app_instance.dependency_overrides[get_current_user] = override


async def test_me_reports_admin_when_user_holds_global_admin_role(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "root")
    assert user.id is not None
    session.add(Role(name="admin"))
    await session.flush()
    await assign_role(user.id, "admin", GLOBAL, None, session)
    _override_current_user(client, user)

    response = await client.get("/api/v1/user/me")

    assert response.status_code == 200
    assert response.json()["is_admin"] is True


async def test_me_reports_non_admin_for_regular_user(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "regular")
    _override_current_user(client, user)

    response = await client.get("/api/v1/user/me")

    assert response.status_code == 200
    assert response.json()["is_admin"] is False


async def test_me_admin_role_at_other_scope_does_not_grant_global_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _create_user(session, "scoped")
    assert user.id is not None
    session.add(Role(name="admin"))
    await session.flush()
    await assign_role(user.id, "admin", PermissionScope("course"), "1", session)
    _override_current_user(client, user)

    response = await client.get("/api/v1/user/me")

    assert response.status_code == 200
    assert response.json()["is_admin"] is False


async def test_me_reports_no_language_for_a_user_who_never_chose(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "nolang")
    await session.commit()
    _override_current_user(client, user)

    response = await client.get("/api/v1/user/me")

    assert response.status_code == 200
    assert response.json()["language"] is None


async def test_patch_me_requires_authentication(client: AsyncClient) -> None:
    """PATCH is a write endpoint; it must be gated the same as GET."""
    transport = cast(ASGITransport, client._transport)
    cast(FastAPI, transport.app).dependency_overrides.pop(get_current_user, None)

    response = await client.patch("/api/v1/user/me", json={"language": "es"})

    assert response.status_code == 401


async def test_patch_me_stores_the_chosen_language(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "picker")
    await session.commit()
    _override_current_user(client, user)

    response = await client.patch("/api/v1/user/me", json={"language": "es"})

    assert response.status_code == 200
    assert response.json()["language"] == "es"

    # Read it back through the API — the choice must have been persisted, not just echoed.
    assert (await client.get("/api/v1/user/me")).json()["language"] == "es"


async def test_patch_me_only_updates_the_authenticated_users_row(client: AsyncClient, session: AsyncSession) -> None:
    """A PATCH must never write to a row other than the caller's own."""
    caller = await _create_user(session, "caller")
    bystander = await _create_user(session, "bystander")
    await session.commit()
    _override_current_user(client, caller)

    response = await client.patch("/api/v1/user/me", json={"language": "fr"})

    assert response.status_code == 200
    assert response.json()["language"] == "fr"

    _override_current_user(client, bystander)
    bystander_response = await client.get("/api/v1/user/me")

    assert bystander_response.json()["language"] is None


async def test_patch_me_rejects_an_unsupported_language(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "german")
    await session.commit()
    _override_current_user(client, user)

    response = await client.patch("/api/v1/user/me", json={"language": "de"})

    assert response.status_code == 422
    assert (await client.get("/api/v1/user/me")).json()["language"] is None


async def test_patch_me_rejects_a_wellformed_but_unsupported_tag(client: AsyncClient, session: AsyncSession) -> None:
    """A syntactically valid BCP 47 tag outside the allowlist must still be a 422.

    ``is_supported_language`` is an exact, case-sensitive match against the
    allowlist keys — it has no subtag or case handling, so a value like
    "en-US" or "EN" is not recognised as "en". This guards the write path: a bad
    tag must be rejected here rather than silently normalised and stored.
    """
    user = await _create_user(session, "regiontag")
    await session.commit()
    _override_current_user(client, user)

    response = await client.patch("/api/v1/user/me", json={"language": "en-US"})

    assert response.status_code == 422
    assert (await client.get("/api/v1/user/me")).json()["language"] is None

    response = await client.patch("/api/v1/user/me", json={"language": "EN"})

    assert response.status_code == 422
    assert (await client.get("/api/v1/user/me")).json()["language"] is None


async def test_patch_me_replaces_a_previous_choice(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "switcher")
    await session.commit()
    _override_current_user(client, user)

    await client.patch("/api/v1/user/me", json={"language": "es"})
    response = await client.patch("/api/v1/user/me", json={"language": "fr"})

    assert response.status_code == 200
    assert (await client.get("/api/v1/user/me")).json()["language"] == "fr"


async def test_patch_me_clears_the_language_with_null(client: AsyncClient, session: AsyncSession) -> None:
    """Clearing it hands the user back to the platform default at runtime."""
    user = await _create_user(session, "clearer")
    await session.commit()
    _override_current_user(client, user)

    await client.patch("/api/v1/user/me", json={"language": "fr"})
    response = await client.patch("/api/v1/user/me", json={"language": None})

    assert response.status_code == 200
    assert response.json()["language"] is None
    assert (await client.get("/api/v1/user/me")).json()["language"] is None


async def test_patch_me_preserves_the_computed_admin_flag(client: AsyncClient, session: AsyncSession) -> None:
    user = await _create_user(session, "adminpicker")
    assert user.id is not None
    session.add(Role(name="admin"))
    await session.flush()
    await assign_role(user.id, "admin", GLOBAL, None, session)
    await session.commit()
    _override_current_user(client, user)

    response = await client.patch("/api/v1/user/me", json={"language": "fr"})

    assert response.status_code == 200
    assert response.json()["is_admin"] is True
    assert response.json()["language"] == "fr"
