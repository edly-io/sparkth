from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.lib.auth import get_current_user

URL = "/api/v1/permissions/can"


async def _grant(session: AsyncSession, user_id: int, permission: str) -> None:
    role = Role(name="reader")
    session.add(role)
    await session.flush()
    assert role.id is not None
    session.add(RolePermission(role_id=role.id, permission=permission))
    session.add(RoleAssignment(user_id=user_id, role_id=role.id, scope="global", scope_object_id=None))
    await session.flush()


def _login_as(client: AsyncClient, user: User) -> None:
    from sparkth.main import app

    async def override() -> User:
        return user

    app.dependency_overrides[get_current_user] = override


async def test_can_true_when_user_holds_permission(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=1, name="R", username="r", email="r@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    await _grant(session, 1, "analytics.read")
    await session.commit()
    _login_as(client, user)

    resp = await client.get(URL, params={"permission": "analytics.read"})
    assert resp.status_code == 200
    assert resp.json() == {"allowed": True}


async def test_can_false_without_permission(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=2, name="P", username="p", email="p@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(client, user)

    resp = await client.get(URL, params={"permission": "analytics.read"})
    assert resp.status_code == 200
    assert resp.json() == {"allowed": False}


async def test_can_unknown_permission_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=3, name="U", username="u", email="u@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(client, user)

    resp = await client.get(URL, params={"permission": "does.not.exist"})
    assert resp.status_code == 422


async def test_can_unknown_scope_returns_422(client: AsyncClient, session: AsyncSession) -> None:
    user = User(id=4, name="S", username="s", email="s@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    _login_as(client, user)

    resp = await client.get(URL, params={"permission": "analytics.read", "scope": "nope"})
    assert resp.status_code == 422


async def test_can_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get(URL, params={"permission": "analytics.read"})
    assert resp.status_code == 403
