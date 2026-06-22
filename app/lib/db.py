"""Database session access for Sparkth — the curated public session API.

This is the single public entry point for obtaining a database session. All code,
including plugins, should acquire sessions from here rather than reaching for the
raw SQLAlchemy engine in :mod:`app.core.db`.

The engine itself stays in :mod:`app.core.db` (it reads settings); this module is
only the public face that hands out sessions over it.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlmodel.ext.asyncio.session import AsyncSession

# Imported as a module (not `from app.core.db import open_session`) on purpose:
# `session_scope` resolves `core_db.open_session` at call time, so overriding that one
# function (e.g. in tests) reaches every caller — including code that imported
# `session_scope` by value.
import app.core.db as core_db


@asynccontextmanager
async def session_scope(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Open an async database session as a managed context.

    Yields an :class:`AsyncSession` — a unit-of-work that borrows a connection
    from the shared engine (``app.core.db.get_engine``), tracks the ORM objects you load and
    mutate, and returns the connection to the pool when the ``async with`` block
    exits (whether normally or via an exception). Always use it as a context
    manager so the connection is never leaked::

        from app.lib.db import session_scope

        async with session_scope() as session:
            session.add(obj)
            await session.commit()

    Use this for code that runs **outside** an HTTP request — background tasks,
    plugin bootstrap, CLI jobs, cleanup routines — where FastAPI's dependency
    injection is not available. Inside request handlers, prefer the
    :func:`get_async_session` dependency instead.

    Transaction semantics: the caller is responsible for committing
    (``await session.commit()``); any un-committed work is rolled back when the
    context exits.

    The ``expire_on_commit`` parameter defaults to ``False``, which is the
    async-safe choice. By default SQLAlchemy *expires* every ORM object after
    ``commit()``, so the next attribute access lazily re-issues a ``SELECT`` to
    reload it. In synchronous code that reload is a transparent (if wasteful)
    blocking query, but in async code it is implicit I/O that cannot be awaited
    and fails once the session has closed. Keeping ``expire_on_commit=False``
    leaves already-loaded attributes valid after the commit and after the block.
    Pass ``expire_on_commit=True`` only if you specifically want post-commit
    objects to refresh on next access.

    Args:
        expire_on_commit: Whether ORM objects are expired after ``commit()``.
            Defaults to ``False`` (async-safe).

    Yields:
        An :class:`AsyncSession` bound to the engine from :func:`app.core.db.get_engine`.
    """
    async with core_db.open_session(expire_on_commit=expire_on_commit) as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an :class:`AsyncSession` to ``async def`` handlers.

    Delegates to :func:`session_scope`. It is intentionally parameterless:
    FastAPI turns a dependency's parameters into request (query) parameters, so
    the ``expire_on_commit`` knob must not be exposed here — use
    :func:`session_scope` directly when you need to override it.
    """
    async with session_scope() as session:
        yield session
