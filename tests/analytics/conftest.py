"""Analytics test fixtures."""

from collections.abc import Generator

import pytest

from app.core.analytics.registry import EventRegistry
from app.core.analytics.schemas import AnalyticsEventSchema


class _SimpleClientEvent(AnalyticsEventSchema):
    # Client-emittable: explicitly opts out of the default-deny server_only policy
    # so the endpoint tests can POST it over the HTTP emission gateway.
    event_type = "test.client_event"
    version = 1
    server_only = False

    value: str


@pytest.fixture(autouse=True)
def _register_test_client_event() -> Generator[None, None, None]:
    """Register a client-emittable event for endpoint tests, then remove it.

    Registered directly on the singleton (not via the plugin drain), so the
    namespace rule that applies to plugin events does not apply here.
    """
    EventRegistry().register(_SimpleClientEvent)
    yield
    EventRegistry()._schemas.pop(("test.client_event", 1), None)
    EventRegistry()._server_only.pop(("test.client_event", 1), None)
