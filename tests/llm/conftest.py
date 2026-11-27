"""Give the test caller the default role, so key routes are reachable at their own user scope."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def client(client: AsyncClient, default_user_roles: object) -> AsyncClient:
    """The shared test client, with user 1 holding the default roles the routes' permission gates check."""
    return client
