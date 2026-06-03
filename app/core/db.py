from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import create_engine

from app.core.config import get_settings

settings = get_settings()

# Synchronous engine for regular operations
engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


# Helper function to convert database URL to async driver
def _get_async_database_url(url: str) -> str:
    """Convert database URL to use async driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    return url


# Async engine for async operations
_async_db_url = _get_async_database_url(settings.DATABASE_URL)
_pool_kwargs = dict(pool_size=3, max_overflow=2, pool_recycle=1800) if not _async_db_url.startswith("sqlite") else {}
async_engine = create_async_engine(_async_db_url, echo=False, pool_pre_ping=True, **_pool_kwargs)


def get_engine() -> Engine:
    return engine
