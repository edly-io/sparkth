"""Database session access for Sparkth — the curated public session API.

This is the single public entry point for obtaining a database session. All code,
including plugins, should acquire sessions from here rather than reaching for the
raw SQLAlchemy engines in :mod:`app.core.db`.

The engines themselves stay in :mod:`app.core.db` (they read settings); this
module is only the public face that hands out sessions over them.
"""

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager

from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import async_engine, engine


@asynccontextmanager
async def session_scope(expire_on_commit: bool = False) -> AsyncGenerator[AsyncSession, None]:
    """Open an async database session as a managed context.

    Yields an :class:`AsyncSession` — a unit-of-work that borrows a connection
    from the shared ``async_engine`` pool, tracks the ORM objects you load and
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
    objects to refresh on next access. (Note the synchronous :func:`get_session`
    uses ``True`` — see its docstring.)

    Args:
        expire_on_commit: Whether ORM objects are expired after ``commit()``.
            Defaults to ``False`` (async-safe).

    Yields:
        An :class:`AsyncSession` bound to the shared async engine.
    """
    async with AsyncSession(async_engine, expire_on_commit=expire_on_commit) as session:
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


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a synchronous :class:`Session`.

    For synchronous (``def``) handlers only — FastAPI runs those in a threadpool,
    so the blocking psycopg2 I/O does not stall the event loop. An ``async def``
    handler must use :func:`get_async_session` instead; a sync session inside an
    async handler blocks the loop on every query.

    ``expire_on_commit=True`` is set explicitly (rather than relying on the
    SQLAlchemy default) to document the deliberate asymmetry with the async
    :func:`session_scope`, which uses ``False``. In synchronous code, expiring on
    commit is harmless: the post-commit reload is a plain blocking ``SELECT`` that
    succeeds while the session is open. Like :func:`get_async_session`, this
    dependency is parameterless for the FastAPI query-parameter reason above.
    """
    with Session(engine, expire_on_commit=True) as session:
        yield session
