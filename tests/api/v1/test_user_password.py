"""Tests for ``POST /user/me/password``: a signed-in user changing their own password.

The change needs the current password, the new one must meet the registration
complexity rules, and a Google-only account (no password) is refused. Every attempt
lands an ``auth.password_changed`` audit row: a success commits with the new hash,
while a wrong current password or a refused account is recorded in its own
transaction so the evidence survives the error response. The write is fail-closed.

These tests sign in with a real token rather than overriding ``get_current_user``,
so the audit actor is bound the way it is in production.
"""

from httpx import AsyncClient
from pytest import MonkeyPatch, raises
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.core.security import create_access_token, get_password_hash, verify_password
from sparkth.lib.testing import AuditEventsFetcher

URL = "/api/v1/user/me/password"
CURRENT = "Old-Passw0rd!"
NEW = "New-Passw0rd!"


async def _user(session: AsyncSession, username: str, *, with_password: bool = True) -> User:
    user = User(
        name="T",
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash(CURRENT) if with_password else None,
        google_id=None if with_password else f"g-{username}",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.username})}"}


async def _stored_hash(session: AsyncSession, user: User) -> str | None:
    await session.refresh(user)
    return user.hashed_password


async def test_change_password_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(URL, json={"current_password": CURRENT, "new_password": NEW})

    assert response.status_code == 401


async def test_change_password_replaces_the_hash(client: AsyncClient, session: AsyncSession) -> None:
    user = await _user(session, "changer")

    response = await client.post(URL, json={"current_password": CURRENT, "new_password": NEW}, headers=_auth(user))

    assert response.status_code == 204
    stored = await _stored_hash(session, user)
    assert stored is not None
    assert verify_password(NEW, stored)
    assert not verify_password(CURRENT, stored)


async def test_change_password_rejects_a_wrong_current_password(client: AsyncClient, session: AsyncSession) -> None:
    user = await _user(session, "wrongcurrent")
    before = user.hashed_password

    response = await client.post(URL, json={"current_password": "Nope-123!", "new_password": NEW}, headers=_auth(user))

    assert response.status_code == 400
    assert await _stored_hash(session, user) == before


async def test_change_password_rejects_a_weak_new_password(client: AsyncClient, session: AsyncSession) -> None:
    user = await _user(session, "weak")
    before = user.hashed_password

    response = await client.post(URL, json={"current_password": CURRENT, "new_password": "short"}, headers=_auth(user))

    assert response.status_code == 422
    assert await _stored_hash(session, user) == before


async def test_change_password_refuses_an_account_without_a_password(
    client: AsyncClient, session: AsyncSession
) -> None:
    user = await _user(session, "googleonly", with_password=False)

    response = await client.post(URL, json={"current_password": CURRENT, "new_password": NEW}, headers=_auth(user))

    assert response.status_code == 409
    assert await _stored_hash(session, user) is None


async def test_success_records_a_password_changed_event(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "auditok")

    await client.post(URL, json={"current_password": CURRENT, "new_password": NEW}, headers=_auth(user))

    (event,) = await audit_events()
    assert (event.category, event.action) == ("auth", "password_changed")
    assert event.outcome == "success"
    assert event.actor_type == "user"
    assert event.actor_id == str(user.id)
    assert (event.target_type, event.target_id) == ("user", str(user.id))
    assert event.new_values == {"method": "self_service"}
    assert event.error_detail is None


async def test_wrong_current_password_records_a_failure_that_survives_the_error(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "auditfail")

    await client.post(URL, json={"current_password": "Nope-123!", "new_password": NEW}, headers=_auth(user))

    (event,) = await audit_events()
    assert (event.category, event.action) == ("auth", "password_changed")
    assert event.outcome == "failure"
    assert event.actor_id == str(user.id)
    assert (event.target_type, event.target_id) == ("user", str(user.id))
    assert event.error_detail == "incorrect current password"


async def test_account_without_password_records_a_denial(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "auditdenied", with_password=False)

    await client.post(URL, json={"current_password": CURRENT, "new_password": NEW}, headers=_auth(user))

    (event,) = await audit_events()
    assert (event.category, event.action) == ("auth", "password_changed")
    assert event.outcome == "denied"
    assert event.actor_id == str(user.id)
    assert event.error_detail == "account has no password"


async def test_audit_rows_never_carry_a_password_or_hash(
    client: AsyncClient, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    user = await _user(session, "nosecrets")
    old_hash = user.hashed_password
    assert old_hash is not None

    await client.post(URL, json={"current_password": "Nope-123!", "new_password": NEW}, headers=_auth(user))
    await client.post(URL, json={"current_password": CURRENT, "new_password": NEW}, headers=_auth(user))
    new_hash = await _stored_hash(session, user)
    assert new_hash is not None

    events = await audit_events()
    assert len(events) == 2
    for event in events:
        for secret in [CURRENT, NEW, "Nope-123!", old_hash, new_hash, user.username]:
            assert secret.encode() not in event.canonical_bytes


async def test_success_is_fail_closed_when_audit_write_fails(
    client: AsyncClient, session: AsyncSession, monkeypatch: MonkeyPatch
) -> None:
    user = await _user(session, "failclosed")
    before = user.hashed_password

    async def broken_record(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("audit unavailable")

    monkeypatch.setattr("sparkth.services.account.service.record_event", broken_record)

    with raises(SQLAlchemyError):
        await client.post(URL, json={"current_password": CURRENT, "new_password": NEW}, headers=_auth(user))

    assert await _stored_hash(session, user) == before
