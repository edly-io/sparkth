"""Shared base for all analytics event payload schemas.

An ``AnalyticsEventSchema`` is a Pydantic model that also declares its own
identity — the ``event_type`` string and integer ``version`` — as class
attributes. This lets registration take the class alone (``register(MyEvent)``):
the type string and the payload shape live in one place and cannot drift apart.

Namespacing convention: plugin events MUST prefix ``event_type`` with the plugin
name (e.g. ``"slack.message_received"``) so they cannot collide with core events
or with another plugin's events. Registration enforces this and rejects a
duplicate ``(event_type, version)`` claimed by a different class.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class AnalyticsEventSchema(BaseModel):
    """Base class for analytics event payload schemas.

    Subclasses set ``event_type`` and ``version`` as class attributes and declare
    the payload as ordinary Pydantic fields. Those two are ``ClassVar`` — identity
    metadata, not part of the validated payload.

    Extra fields are forbidden so a producer sending unexpected keys gets a
    ``422`` rather than having those fields silently dropped from the stored row.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: ClassVar[str]
    version: ClassVar[int]
