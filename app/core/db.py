from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings


def _get_async_database_url(url: str) -> str:
    """Convert database URL to use async driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    return url


def _create_engine(url: str) -> AsyncEngine:
    """Build an async engine from a database URL, applying a connection pool for non-SQLite backends."""
    async_url = _get_async_database_url(url)
    pool_kwargs = dict(pool_size=3, max_overflow=2, pool_recycle=1800) if not async_url.startswith("sqlite") else {}
    return create_async_engine(async_url, echo=False, pool_pre_ping=True, **pool_kwargs)


# Lazily-built singleton async engine. Built on first `get_engine()` call rather
# than at import time so that (a) importing `app.core.db` has no side effects and
# (b) tests can swap in their own engine before the real one is ever created.
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, building it on first use.

    All database access goes through this provider (via `app.lib.db.session_scope`
    / `get_async_session`) rather than a module-level constant, so the engine can
    be resolved at call time — which is what lets the test suite inject a
    throwaway per-test engine.
    """
    global _engine
    if _engine is None:
        _engine = _create_engine(get_settings().DATABASE_URL)
    return _engine


@asynccontextmanager
async def open_session(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Open an :class:`AsyncSession` bound to the engine from :func:`get_engine`.

    This is the single low-level session provider that :func:`app.lib.db.session_scope`
    delegates to. Application code should use ``session_scope`` (or the
    ``get_async_session`` dependency), not this directly.

    It is kept as a dedicated seam so the test suite can override this one function —
    ``session_scope`` resolves it via module attribute at call time, so a single
    override reaches every caller, including modules that did
    ``from app.lib.db import session_scope``.
    """
    async with AsyncSession(get_engine(), expire_on_commit=expire_on_commit) as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the singleton engine and reset it, so the next `get_engine()` rebuilds.

    Used at test-session teardown to close the engine's connection pool (and, for
    aiosqlite, let its worker thread exit so the interpreter doesn't hang).
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
