"""A stand-in for a plugin's ``analytics`` module, for register_event_schemas.

Mirrors the real shape: event schemas alongside the seam classes and the imported
base, so a test can prove the sweep picks out only the schemas this module defines.
"""

from sparkth.lib.analytics import AnalyticsEventSchema  # noqa: F401 — imported, must not be registered

SWEEP_PLUGIN_NAME = "fake-sweep-plugin"


class SweptFirst(AnalyticsEventSchema):
    event_type = f"{SWEEP_PLUGIN_NAME}.first_happened"
    version = 1

    detail: str


class SweptSecond(AnalyticsEventSchema):
    event_type = f"{SWEEP_PLUGIN_NAME}.second_happened"
    version = 1

    detail: str


class SweptAnalytics:
    """A seam class, not an event — shares the module and the naming, is not a schema."""
