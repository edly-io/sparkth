"""Shared base for all analytics event payload schemas.

An ``AnalyticsEventSchema`` is a Pydantic model that also declares its own
identity — the ``event_type`` string and integer ``version`` — and its emission
policy (``server_only``) as class attributes. This lets registration take the
class alone (``register(MyEvent)``): the type string, the payload shape, and the
policy live in one place and cannot drift apart.

Namespacing convention: plugin events MUST prefix ``event_type`` with the plugin
name (e.g. ``"slack.message_received"``) so they cannot collide with core events
or with another plugin's events. Enforcement is wired via ``initialize_event_registry``
(called from ``assemble_app()``) which rejects unnamespaced events with
``EventNamespaceError``. A *different* class claiming an already-registered
``(event_type, version)`` is a startup-fatal ``DuplicateEventTypeError``.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class AnalyticsEventSchema(BaseModel):
    """Base class for analytics event payload schemas.

    Subclasses set ``event_type`` and ``version`` (and, to allow client emission,
    ``server_only = False``) as class attributes and declare the payload as
    ordinary Pydantic fields. Those three are ``ClassVar`` — identity/policy
    metadata, not part of the validated payload.

    Extra fields are forbidden so a producer sending unexpected keys gets a
    ``422`` rather than having those fields silently dropped from the stored row.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: ClassVar[str]
    version: ClassVar[int]
    # Default-deny: an event is server-only unless it explicitly opts in. When
    # True, the event may only be emitted by trusted server-side callers via
    # ingest_event directly; the HTTP emission endpoint rejects it with 403.
    # A plugin sets server_only = False to allow authenticated clients to emit it.
    server_only: ClassVar[bool] = True
