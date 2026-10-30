"""The compose plugin's routes mount under its name."""

import pytest
from httpx import AsyncClient

from sparkth.lib.models import User


@pytest.mark.asyncio
async def test_completions_route_is_under_compose(client: AsyncClient, current_user: User) -> None:
    # An empty body fails the handler's request model, so a 422 proves the route was reached.
    assert (await client.post("/api/v1/compose/completions", json={})).status_code == 422
    assert (await client.post("/api/v1/chat/completions", json={})).status_code == 404
