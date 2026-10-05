"""Account creation and password resets through the user CLI leave an audit
row attributed to the CLI, in the same transaction as the change, and never
carry the password or its hash."""

import pytest
import typer
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.cli import users
from sparkth.core.audit.models import AuditEvent
from sparkth.core.models.user import User
from sparkth.lib.testing import AuditEventsFetcher

PASSWORD = "s3cret-Passw0rd"
NEW_PASSWORD = "n3w-Passw0rd"


async def _broken_record(*_args: object, **_kwargs: object) -> None:
    raise SQLAlchemyError("audit store down")


async def _create(username: str = "alice") -> None:
    await users._create_user(
        username=username,
        email=f"{username}@example.com",
        password=PASSWORD,
        name=None,
        superuser=False,
        email_verified=True,
    )


async def _user(session: AsyncSession, username: str) -> User:
    return (await session.exec(select(User).where(User.username == username))).one()


def _hash(user: User) -> str:
    assert user.hashed_password is not None
    return user.hashed_password


def _assert_cli_actor(event: AuditEvent) -> None:
    assert event.actor_type == "system"
    assert event.actor_id is None
    assert event.actor_label == "cli"
    assert event.source == "cli"


async def test_create_user_records_registered_by_the_cli(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await _create()
    user = await _user(session, "alice")

    (event,) = await audit_events()
    assert (event.category, event.action) == ("auth", "registered")
    assert event.outcome == "success"
    _assert_cli_actor(event)
    assert event.target_type == "user"
    assert event.target_id == str(user.id)
    assert event.new_values == {"method": "cli"}
    text = event.canonical_bytes.decode()
    assert PASSWORD not in text
    assert _hash(user) not in text
    assert "alice" not in text


async def test_duplicate_create_user_records_nothing_more(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await _create()

    with pytest.raises(typer.Exit):
        await _create()

    assert len(await audit_events()) == 1


async def test_create_user_is_fail_closed_when_audit_write_fails(
    session: AsyncSession, audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sparkth.cli.users.record_event", _broken_record)

    with pytest.raises(SQLAlchemyError):
        await _create()

    assert (await session.exec(select(User).where(User.username == "alice"))).all() == []
    assert await audit_events() == []


async def test_reset_password_records_password_reset_by_the_cli(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await _create("carol")
    old_hash = _hash(await _user(session, "carol"))

    await users._reset_password(identifier="carol", new_password=NEW_PASSWORD)

    session.expire_all()
    user = await _user(session, "carol")
    _, event = await audit_events()
    assert (event.category, event.action) == ("auth", "password_reset")
    assert event.outcome == "success"
    _assert_cli_actor(event)
    assert event.target_type == "user"
    assert event.target_id == str(user.id)
    assert event.old_values is None
    assert event.new_values == {"method": "cli"}
    text = event.canonical_bytes.decode()
    assert _hash(user) != old_hash
    for secret in (PASSWORD, NEW_PASSWORD, old_hash, _hash(user)):
        assert secret not in text


async def test_reset_password_for_unknown_user_records_nothing(
    session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    with pytest.raises(typer.Exit):
        await users._reset_password(identifier="ghost", new_password=NEW_PASSWORD)

    assert await audit_events() == []


async def test_reset_password_is_fail_closed_when_audit_write_fails(
    session: AsyncSession, audit_events: AuditEventsFetcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _create("dave")
    old_hash = _hash(await _user(session, "dave"))
    monkeypatch.setattr("sparkth.cli.users.record_event", _broken_record)

    with pytest.raises(SQLAlchemyError):
        await users._reset_password(identifier="dave", new_password=NEW_PASSWORD)

    session.expire_all()
    assert _hash(await _user(session, "dave")) == old_hash
    (event,) = await audit_events()
    assert event.action == "registered"
