"""Analytics test fixtures."""

from collections.abc import Generator

import pytest
from pydantic import BaseModel

from app.core.analytics.registry import EventRegistry


class _SimpleEvent(BaseModel):
    value: str


@pytest.fixture(autouse=True)
def _register_test_client_event() -> Generator[None, None, None]:
    """Register a client-emittable event for endpoint tests, then remove it."""
    EventRegistry().register("test.client_event", 1, _SimpleEvent, server_only=False)
    yield
    EventRegistry()._schemas.pop(("test.client_event", 1), None)
    EventRegistry()._server_only.pop(("test.client_event", 1), None)
