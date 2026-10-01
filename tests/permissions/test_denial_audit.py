"""A refusal from the ``Permission.require*`` dependencies lands a
``permission.denied`` audit row that survives the request's rollback, and the
write is fail-closed. Granted requests and the ``/permissions/can`` probe
record nothing."""

from httpx import AsyncClient
from pytest import MonkeyPatch, raises
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.permissions.models import Role, RoleAssignment, RolePermission
from sparkth.core.security import create_access_token
from sparkth.lib.testing import AuditEventsFetcher

ROLES_URL = "/api/v1/permissions/roles"


async def _user(session: AsyncSession, username: str, permission: str | None = None) -> User:
    user = User(name="T", username=username, email=f"{username}@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    if permission is not None:
        assert user.id is not None
        role = Role(name=f"{username}-role")
        session.add(role)
        await session.flush()
        assert role.id is not None
        session.add(RolePermission(role_id=role.id, permission=permission))
        session.add(RoleAssignment(user_id=user.id, role_id=role.id, scope="global", scope_object_id=None))
    await session.commit()
    await session.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}


async def test_denied_request_records_permission_denied_event(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "denied-alice")

    response = await client.get(ROLES_URL, headers=_auth(user))
    assert response.status_code == 403

    (event,) = await audit_events()
    assert event.category == "permission"
    assert event.action == "denied"
    assert event.outcome == "denied"
    assert event.actor_type == "user"
    assert event.actor_id == str(user.id)
    assert event.target_type == "permission"
    assert event.target_id == "role.read"
    assert event.error_detail == "scope=global"


async def test_denied_scoped_request_names_the_scope_object(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "denied-bob")

    response = await client.get(f"{ROLES_URL}/7", headers=_auth(user))
    assert response.status_code == 403

    (event,) = await audit_events()
    assert event.target_id == "role.read"
    assert event.error_detail == "scope=role:7"


async def test_granted_request_records_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "granted-carol", "role.read")

    response = await client.get(ROLES_URL, headers=_auth(user))
    assert response.status_code == 200

    assert await audit_events() == []


async def test_permission_probe_records_nothing(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "probe-dave")

    response = await client.get("/api/v1/permissions/can", params={"permission": "analytics.read"}, headers=_auth(user))
    assert response.status_code == 200
    assert response.json() == {"allowed": False}

    assert await audit_events() == []


async def test_denial_is_fail_closed_when_audit_write_fails(
    client: AsyncClient, session: AsyncSession, monkeypatch: MonkeyPatch
) -> None:
    user = await _user(session, "broken-erin")

    async def broken_record(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("audit unavailable")

    monkeypatch.setattr("sparkth.core.permissions.record_event_now", broken_record)

    with raises(SQLAlchemyError):
        await client.get(ROLES_URL, headers=_auth(user))
