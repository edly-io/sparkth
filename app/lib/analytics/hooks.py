"""Analytics contribution hook.

Plugins register their event payload schemas here from their ``__init__`` (one or
more per plugin). This hook carries plugin contributions only —
core default events are seeded directly into ``EventRegistry``. The
``initialize_event_registry`` drain in this package's ``__init__`` copies these
into the gateway's event registry at app assembly.
"""

from app.core.analytics.schemas.base import AnalyticsEventSchema
from app.lib.hooks import PluginCollectionHook

ANALYTICS_SCHEMAS: PluginCollectionHook[type[AnalyticsEventSchema]] = PluginCollectionHook()
