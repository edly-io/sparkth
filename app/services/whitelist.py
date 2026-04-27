from pydantic import BaseModel as _PydanticBase
from pydantic import EmailStr, ValidationError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.whitelist import WhitelistedEmail


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
            if "." not in domain_part or len(domain_part) < 3:
                raise ValueError(f"Invalid domain format: {value}")
            entry_type = "domain"
        else:
            try:
                _EmailValidator(email=normalized)
            except ValidationError as exc:
                raise ValueError(f"Invalid email format: {value}") from exc
            entry_type = "email"

        result = await session.exec(select(WhitelistedEmail).where(WhitelistedEmail.value == normalized))
        if result.one_or_none() is not None:
            raise ValueError(f"Entry already exists: {normalized}")

        entry = WhitelistedEmail(
            value=normalized,
            entry_type=entry_type,
            added_by_id=added_by_id,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry

    @staticmethod
    async def remove_entry(session: AsyncSession, *, entry_id: int) -> None:
        result = await session.exec(select(WhitelistedEmail).where(WhitelistedEmail.id == entry_id))
        entry = result.one_or_none()
        if entry is None:
            raise ValueError(f"Whitelist entry not found: {entry_id}")

        await session.delete(entry)
        await session.commit()

    @staticmethod
    async def list_entries(session: AsyncSession) -> list[WhitelistedEmail]:
        result = await session.exec(select(WhitelistedEmail).order_by(col(WhitelistedEmail.created_at).desc()))
        return list(result.all())

    @staticmethod
    async def is_email_allowed(session: AsyncSession, email: str) -> bool:
        normalized = email.strip().lower()
        domain = "@" + normalized.split("@")[1] if "@" in normalized else ""

        result = await session.exec(
            select(WhitelistedEmail.id).where(
                ((WhitelistedEmail.value == normalized) & (WhitelistedEmail.entry_type == "email"))
                | ((WhitelistedEmail.value == domain) & (WhitelistedEmail.entry_type == "domain"))
            )
        )
        return result.first() is not None
