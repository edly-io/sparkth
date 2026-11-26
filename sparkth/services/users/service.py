"""Search, read and look up users for callers outside user management."""

from collections.abc import Collection

from sqlmodel import col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.services.users.exceptions import UserNotFound


async def get_usernames(session: AsyncSession, user_ids: Collection[int]) -> dict[int, str]:
    """Map each id in ``user_ids`` that belongs to a user to that user's username."""
    if not user_ids:
        return {}
    rows = await session.exec(select(User.id, User.username).where(col(User.id).in_(user_ids)))
    return {user_id: username for user_id, username in rows if user_id is not None}


async def list_users(search: str | None, limit: int, offset: int, session: AsyncSession) -> list[User]:
    """Return a page of active users ordered by username.

    ``search`` keeps the users whose name, username or email contains it, ignoring case and
    treating ``%`` and ``_`` as plain characters.
    """
    query = select(User).where(col(User.is_deleted).is_(False))
    if search:
        query = query.where(
            or_(
                col(User.name).icontains(search, autoescape=True),
                col(User.username).icontains(search, autoescape=True),
                col(User.email).icontains(search, autoescape=True),
            )
        )
    rows = await session.exec(query.order_by(col(User.username), col(User.id)).limit(limit).offset(offset))
    return list(rows)


async def get_user(user_id: int, session: AsyncSession) -> User:
    """Return the active user with ``user_id``, raising when there is none."""
    user = await session.get(User, user_id)
    if user is None or user.is_deleted:
        raise UserNotFound(user_id)
    return user
