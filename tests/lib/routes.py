"""Router-registration helper for plugin test conftest files.

Each plugin's conftest calls ``register_router`` once at module level to mount
its APIRouter onto the shared FastAPI app.  The sentinel-path check makes the
call idempotent so repeated imports (e.g. when pytest collects multiple test
files) don't double-register the same routes.
"""

from enum import Enum
from typing import Sequence

from fastapi import FastAPI
from fastapi.routing import APIRouter


def register_router(
    app: FastAPI,
    router: APIRouter,
    *,
    sentinel_path: str,
    prefix: str,
    tags: Sequence[str | Enum] | None = None,
) -> None:
    """Include *router* on *app* unless *sentinel_path* is already registered."""
    existing = {getattr(r, "path", None) for r in app.routes}
    if sentinel_path not in existing:
        app.include_router(router, prefix=prefix, tags=list(tags) if tags else [])
