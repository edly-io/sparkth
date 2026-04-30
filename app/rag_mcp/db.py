"""RAG MCP database engine - lightweight async DB for metadata tools."""

import contextlib
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# Read DATABASE_URL at module import time
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required for RAG MCP server")


def _get_async_url(url: str) -> str:
    """Convert database URL to use async driver.

    Args:
        url: Database URL (e.g. "postgresql://..." or "sqlite://...")

    Returns:
        Async-compatible URL (e.g. "postgresql+asyncpg://..." or "sqlite+aiosqlite://...")
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


# Create async engine
_async_engine = create_async_engine(
    _get_async_url(DATABASE_URL),
    echo=False,
    pool_pre_ping=True,
)


@contextlib.asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Open an async session for database operations.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(...))

    Yields:
        AsyncSession ready for queries
    """
    async with AsyncSession(_async_engine, expire_on_commit=False) as session:
        yield session
