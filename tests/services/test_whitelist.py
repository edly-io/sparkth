import uuid

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.services.whitelist import (
    InvalidWhitelistValue,
    WhitelistEntryAlreadyExists,
    WhitelistEntryNotFound,
    WhitelistService,
)


def _uniq(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class TestAddEntry:
    async def test_add_email_entry(self, session: AsyncSession) -> None:
        email = f"{_uniq('user')}@example.com"
        entry = await WhitelistService.add_entry(session, value=email, added_by_id=1)

        assert entry.value == email
        assert entry.entry_type == "email"
        assert entry.added_by_id == 1
        assert entry.id is not None

    async def test_add_domain_entry(self, session: AsyncSession) -> None:
        domain = f"@{_uniq('org')}.com"
        entry = await WhitelistService.add_entry(session, value=domain, added_by_id=1)

        assert entry.value == domain
        assert entry.entry_type == "domain"

    async def test_add_duplicate_raises(self, session: AsyncSession) -> None:
        email = f"{_uniq('user')}@example.com"
        await WhitelistService.add_entry(session, value=email, added_by_id=1)

        with pytest.raises(WhitelistEntryAlreadyExists, match="already exists"):
            await WhitelistService.add_entry(session, value=email, added_by_id=1)

    async def test_add_invalid_email_raises(self, session: AsyncSession) -> None:
        with pytest.raises(InvalidWhitelistValue, match="Invalid email"):
            await WhitelistService.add_entry(session, value="not-an-email", added_by_id=1)

    async def test_add_invalid_domain_raises(self, session: AsyncSession) -> None:
        with pytest.raises(InvalidWhitelistValue, match="Invalid domain"):
            await WhitelistService.add_entry(session, value="@", added_by_id=1)

    async def test_add_domain_without_dot_raises(self, session: AsyncSession) -> None:
        with pytest.raises(InvalidWhitelistValue, match="Invalid domain"):
            await WhitelistService.add_entry(session, value="@localhost", added_by_id=1)

    async def test_add_domain_with_leading_dot_raises(self, session: AsyncSession) -> None:
        with pytest.raises(InvalidWhitelistValue, match="Invalid domain"):
            await WhitelistService.add_entry(session, value="@.example.com", added_by_id=1)

    async def test_add_domain_with_trailing_dot_raises(self, session: AsyncSession) -> None:
        with pytest.raises(InvalidWhitelistValue, match="Invalid domain"):
            await WhitelistService.add_entry(session, value="@example.com.", added_by_id=1)

    async def test_add_domain_with_consecutive_dots_raises(self, session: AsyncSession) -> None:
        with pytest.raises(InvalidWhitelistValue, match="Invalid domain"):
            await WhitelistService.add_entry(session, value="@example..com", added_by_id=1)

    async def test_integrity_error_race_raises_already_exists(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A unique-index race (commit raises IntegrityError) is translated, with rollback."""
        from sqlalchemy.exc import IntegrityError

        real_rollback = session.rollback
        rollback_called = False

        async def failing_commit() -> None:
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))

        async def tracking_rollback() -> None:
            nonlocal rollback_called
            rollback_called = True
            await real_rollback()

        monkeypatch.setattr(session, "commit", failing_commit)
        monkeypatch.setattr(session, "rollback", tracking_rollback)

        # A unique value is essential: the pre-check must return None so flow reaches the
        # monkeypatched commit (the IntegrityError path), not the pre-check duplicate path.
        email = f"{_uniq('race')}@example.com"
        with pytest.raises(WhitelistEntryAlreadyExists, match="already exists"):
            await WhitelistService.add_entry(session, value=email, added_by_id=1)

        assert rollback_called is True


class TestRemoveEntry:
    async def test_remove_existing(self, session: AsyncSession) -> None:
        email = f"{_uniq('user')}@example.com"
        entry = await WhitelistService.add_entry(session, value=email, added_by_id=1)

        await WhitelistService.remove_entry(session, entry_id=entry.id)  # type: ignore[arg-type]

        entries = await WhitelistService.list_entries(session)
        assert all(e.value != email for e in entries)

    async def test_remove_nonexistent_raises(self, session: AsyncSession) -> None:
        with pytest.raises(WhitelistEntryNotFound, match="not found"):
            await WhitelistService.remove_entry(session, entry_id=999999)


class TestListEntries:
    async def test_list_returns_all(self, session: AsyncSession) -> None:
        email1 = f"{_uniq('user')}@example.com"
        email2 = f"{_uniq('user')}@example.com"
        await WhitelistService.add_entry(session, value=email1, added_by_id=1)
        await WhitelistService.add_entry(session, value=email2, added_by_id=1)

        entries = await WhitelistService.list_entries(session)
        values = [e.value for e in entries]

        assert email1 in values
        assert email2 in values

    async def test_list_empty(self, session: AsyncSession) -> None:
        entries = await WhitelistService.list_entries(session)
        assert isinstance(entries, list)


class TestIsEmailAllowed:
    async def test_exact_email_match(self, session: AsyncSession) -> None:
        email = f"{_uniq('user')}@example.com"
        await WhitelistService.add_entry(session, value=email, added_by_id=1)

        assert await WhitelistService.is_email_allowed(session, email) is True

    async def test_domain_match(self, session: AsyncSession) -> None:
        domain = f"@{_uniq('org')}.com"
        await WhitelistService.add_entry(session, value=domain, added_by_id=1)

        assert await WhitelistService.is_email_allowed(session, f"anyone{domain}") is True

    async def test_no_match_returns_false(self, session: AsyncSession) -> None:
        assert await WhitelistService.is_email_allowed(session, f"{_uniq('nobody')}@nowhere.com") is False

    async def test_case_insensitive_email(self, session: AsyncSession) -> None:
        email = f"{_uniq('user')}@example.com"
        await WhitelistService.add_entry(session, value=email, added_by_id=1)

        assert await WhitelistService.is_email_allowed(session, email.upper()) is True

    async def test_case_insensitive_domain(self, session: AsyncSession) -> None:
        domain = f"@{_uniq('org')}.com"
        await WhitelistService.add_entry(session, value=domain, added_by_id=1)

        assert await WhitelistService.is_email_allowed(session, f"USER{domain.upper()}") is True
