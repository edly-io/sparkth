"""Value objects shared across the audit subsystem.

Actors (who), contexts (where from), and the grouped event envelope fields
(what and with what effect). Pure frozen-or-plain dataclasses whose only
behavior is their own invariants; the contextvar plumbing lives in
:mod:`sparkth.core.audit.context` and the event classes in
:mod:`sparkth.core.audit.events`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

from sparkth.core.audit.enums import AuditActorType, AuditSource


@dataclass(frozen=True, slots=True)
class UserActor:
    """An authenticated identity.

    ``id`` is the immutable user ID and is mandatory: attribution must never
    hang off a mutable field. ``label`` is a display-only convenience (e.g.
    the username at the time of the event).
    """

    id: str
    label: str | None = None
    type: ClassVar[AuditActorType] = AuditActorType.USER


@dataclass(frozen=True, slots=True)
class SystemActor:
    """The platform acting on its own: scheduler, CLI, background jobs.

    There is no user behind the action, so there is no per-instance ``id``
    (the ClassVar pins it to ``None`` for the uniform read surface); ``label``
    names the component (e.g. ``"cli"``).
    """

    label: str | None = None
    id: ClassVar[None] = None
    type: ClassVar[AuditActorType] = AuditActorType.SYSTEM


@dataclass(frozen=True, slots=True)
class AnonymousActor:
    """An unauthenticated caller: a pure marker with no identity fields.

    A claimed-but-unverified identity (e.g. the username typed into a failed
    login) is evidence about the *event*, not the actor, and rides on the
    event's :class:`AuditTarget` (see the ``auth.login`` capture). The
    ClassVars pin ``id`` and ``label`` to ``None`` for the uniform read
    surface.
    """

    id: ClassVar[None] = None
    label: ClassVar[None] = None
    type: ClassVar[AuditActorType] = AuditActorType.ANONYMOUS


# Who performed the action. A closed tagged union: each member fixes ``type``
# and enforces its own field invariants at construction, while exposing the
# uniform read surface (type/id/label) the recorder flattens into the event row.
AuditActor = UserActor | SystemActor | AnonymousActor


@dataclass(slots=True, kw_only=True)
class AuditRequestContext:
    """Origin metadata for a unit of work that arrived over the network.

    Seeded by the ASGI middleware for HTTP requests (``source=REST``);
    the MCP and chat capture seams will seed their own with their source.
    ``request_id`` is mandatory (the producer generates one at the edge);
    ``request_ip`` and ``user_agent`` stay optional because a request can
    genuinely lack them.
    """

    request_id: str
    request_ip: str | None = None
    user_agent: str | None = None
    source: AuditSource = AuditSource.REST
    actor: AuditActor | None = None


@dataclass(slots=True, kw_only=True)
class AuditSystemContext:
    """Origin metadata for a unit of work with no network edge.

    CLI commands (``source=CLI``) and platform-initiated jobs carry this
    shape; it is also the empty fallback outside any installed context.
    There is no request, so the ``request_*`` fields are structurally
    absent, not merely unset.
    """

    source: AuditSource = AuditSource.SYSTEM
    actor: AuditActor | None = None
    request_id: ClassVar[None] = None
    request_ip: ClassVar[None] = None
    user_agent: ClassVar[None] = None


# Origin metadata for the current unit of work, merged into every recorded
# event. A closed tagged union, like AuditActor: each member carries only the
# fields its origin can actually have, while exposing the uniform read surface
# (request_id/request_ip/user_agent/source/actor) the recorder flattens into
# the event row.
AuditContext = AuditRequestContext | AuditSystemContext


@dataclass(frozen=True, slots=True)
class AuditTarget:
    """The entity the action acted on (the NIST AU-3 what field)."""

    type: str
    id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditChange:
    """Before/after snapshots of a mutation; redacted before persistence.

    The pair encodes the mutation kind: a create has no ``old``, a delete has
    no ``new``, an update carries both. At least one side is required; events
    without a mutation carry no ``AuditChange`` at all.
    """

    old: Mapping[str, Any] | None = None
    new: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.old is None and self.new is None:
            raise ValueError("AuditChange requires at least one of 'old' or 'new'")


@dataclass(frozen=True, slots=True)
class AuditToolCall:
    """The tool invocation behind an AI action; args are redacted before persistence."""

    name: str
    args: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AuditModelInfo:
    """AI provenance: which model produced or drove the action."""

    provider: str | None = None
    name: str | None = None
    version: str | None = None
