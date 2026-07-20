from pydantic import BaseModel as _PydanticBase
from pydantic import EmailStr, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.whitelist import WhitelistedEmail
from sparkth.lib.log import get_logger
from sparkth.services.whitelist.exceptions import (
    InvalidWhitelistValue,
    WhitelistEntryAlreadyExists,
    WhitelistEntryNotFound,
)

logger = get_logger(__name__)


class _EmailValidator(_PydanticBase):
    email: EmailStr


class WhitelistService:
    @staticmethod
    async def add_entry(
        session: AsyncSession,
        *,
        value: str,
        added_by_id: int,
    ) -> WhitelistedEmail:
        normalized = value.strip().lower()

        if normalized.startswith("@"):
            domain_part = normalized[1:]
            if (
                not domain_part
                or "." not in domain_part
                or len(domain_part) < 3
                or domain_part.startswith(".")
                or domain_part.endswith(".")
                or ".." in domain_part
            ):
                raise InvalidWhitelistValue(f"Invalid domain format: {value}")
            entry_type = "domain"
        else:
            try:
                _EmailValidator(email=normalized)
            except ValidationError as exc:
                raise InvalidWhitelistValue(f"Invalid email format: {value}") from exc
            entry_type = "email"

        # No pre-check SELECT: the unique index on ``value`` is the single, atomic guard
        # against duplicates. A check-then-insert would both cost an extra round trip and
        # leave a race window where two concurrent adds pass the check and both insert.
        entry = WhitelistedEmail(
            value=normalized,
            entry_type=entry_type,
            added_by_id=added_by_id,
        )
        session.add(entry)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            # An IntegrityError here is not necessarily a duplicate value: the insert also
            # carries the added_by_id foreign key, which fails if the referencing user was
            # deleted mid-request. Re-query to tell the two apart (portably, without parsing
            # DB-specific error text) rather than assuming a unique-value conflict.
            existing = await session.exec(select(WhitelistedEmail).where(WhitelistedEmail.value == normalized))
            if existing.one_or_none() is not None:
                logger.warning("Whitelist insert conflict for value %s: %s", normalized, exc)
                raise WhitelistEntryAlreadyExists(f"Entry already exists: {normalized}") from exc
            logger.exception("Unexpected integrity error inserting whitelist value %s", normalized)
            raise
        await session.refresh(entry)
        return entry

    @staticmethod
    async def remove_entry(session: AsyncSession, *, entry_id: int) -> None:
        entry = await session.get(WhitelistedEmail, entry_id)
        if entry is None:
            raise WhitelistEntryNotFound(f"Whitelist entry not found: {entry_id}")

        await session.delete(entry)
        await session.commit()

    @staticmethod
    async def list_entries(session: AsyncSession) -> list[WhitelistedEmail]:
        result = await session.exec(select(WhitelistedEmail).order_by(col(WhitelistedEmail.created_at).desc()))
        return list(result.all())

    @staticmethod
    async def is_email_allowed(session: AsyncSession, email: str) -> bool:
        normalized = email.strip().lower()
        if "@" not in normalized:
            return False
        domain = "@" + normalized.split("@")[1]

        result = await session.exec(
            select(WhitelistedEmail.id).where(
                ((WhitelistedEmail.value == normalized) & (WhitelistedEmail.entry_type == "email"))
                | ((WhitelistedEmail.value == domain) & (WhitelistedEmail.entry_type == "domain"))
            )
        )
        return result.first() is not None
