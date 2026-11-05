from collections.abc import Awaitable, Callable
from functools import partial

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.auth import get_current_user
from sparkth.lib.db import get_async_session


async def probe() -> dict[str, bool]:
    return {"ok": True}


def build_gated_client(
    session: AsyncSession, dep: Callable[..., Awaitable[User]], user: User | None = None, path: str = "/probe"
) -> AsyncClient:
    """An async client for a one-route app gated by ``dep`` on ``session``.

    With a ``user`` the request runs as that user; without one the real authentication dependency runs.
    """
    app = FastAPI()
    app.dependency_overrides[get_async_session] = lambda: session
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    app.get(path, dependencies=[Depends(dep)])(probe)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def gated_client(session: AsyncSession) -> Callable[..., AsyncClient]:
    """``build_gated_client`` bound to the test's session: call it with ``dep``, then optionally the user and path."""
    return partial(build_gated_client, session)
