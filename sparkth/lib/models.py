"""Public API for the SQLModel data models that plugins consume.

Plugins import model classes and the shared mixins from here instead of reaching
into ``sparkth.core.models.*`` directly — every internal symbol a plugin imports
becomes an implicit public API and blocks refactoring (see issue #379).

Implementation lives in ``sparkth/core/models/``.
"""

from sparkth.core.models.base import SoftDeleteModel, TimestampedModel, utc_now
from sparkth.core.models.llm import LLMConfig
from sparkth.core.models.user import User

__all__ = [
    "User",
    "LLMConfig",
    "TimestampedModel",
    "SoftDeleteModel",
    "utc_now",
]
