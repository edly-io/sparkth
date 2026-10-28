"""Look up users for callers outside user management."""

from collections.abc import Collection

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User


async def get_usernames(session: AsyncSession, user_ids: Collection[int]) -> dict[int, str]:
    """Map each id in ``user_ids`` that belongs to a user to that user's username."""
    if not user_ids:
        return {}
    rows = await session.exec(select(User.id, User.username).where(col(User.id).in_(user_ids)))
    return {user_id: username for user_id, username in rows if user_id is not None}
