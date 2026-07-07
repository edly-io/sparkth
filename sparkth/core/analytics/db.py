"""Analytics database engine and session providers.

Mirrors the structure of :mod:`sparkth.core.db` but points at the separate analytics
database (``ANALYTICS_DATABASE_URL`` / TimescaleDB). All analytics database access
goes through these providers so the test suite can inject a throwaway engine via
``monkeypatch.setattr(sparkth.core.analytics.db, "open_analytics_session", ...)``.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.config import get_settings


def _get_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    return url


def _build_engine(url: str) -> AsyncEngine:
    async_url = _get_async_url(url)
    pool_kwargs = dict(pool_size=3, max_overflow=2, pool_recycle=1800) if not async_url.startswith("sqlite") else {}
    return create_async_engine(async_url, echo=False, pool_pre_ping=True, **pool_kwargs)


_engine: AsyncEngine | None = None


def get_analytics_engine() -> AsyncEngine:
    """Return the process-wide analytics async engine, building it on first use.

    Resolved lazily so importing this module has no side effects and tests can
    inject a throwaway engine before the real one is ever created.
    """
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().ANALYTICS_DATABASE_URL)
    return _engine


@asynccontextmanager
async def open_analytics_session(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Open an :class:`AsyncSession` bound to the analytics engine.

    This is the single low-level session provider that
    :func:`sparkth.lib.db.analytics_session_scope` delegates to. Keep as a dedicated
    seam so the test suite can override it on this module and reach every caller.
    """
    async with AsyncSession(get_analytics_engine(), expire_on_commit=expire_on_commit) as session:
        yield session


async def dispose_analytics_engine() -> None:
    """Dispose the singleton analytics engine and reset it.

    Used at test-session teardown so the aiosqlite worker thread exits and the
    interpreter doesn't hang joining it at shutdown.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
