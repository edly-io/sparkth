"""The append-only audit event table.

Rows are the system of record for who did what, when, and with what effect.
They are never updated or deleted by application code: corrections are new
events, and the model deliberately does not subclass ``SoftDeleteModel``.
Writes go through :func:`sparkth.lib.audit.record_event`, never direct ORM
inserts, so redaction and canonicalization cannot be skipped.
"""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict
from sqlalchemy import JSON, Column, DateTime, LargeBinary, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from sparkth.core.audit.canonical import canonicalize
from sparkth.core.audit.constants import ANONYMOUS_ACTOR
from sparkth.core.audit.events import BaseAuditEvent
from sparkth.core.audit.redaction import redact
from sparkth.core.audit.types import AuditContext
from sparkth.core.models.base import TimestampedModel, utc_now


def _json_column() -> Column[Any]:
    """JSONB on Postgres, plain JSON on the SQLite test database."""
    return Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)


class AuditEvent(TimestampedModel, SQLModel, table=True):
    """One audited action, carrying the NIST AU-3 six fields plus AI provenance.

    ``canonical_bytes`` holds the pinned canonical serialization of the event
    (see :mod:`sparkth.core.audit.canonical`) so the tamper-evidence sealer can
    later hash exactly what was written, byte for byte.
    """

    __tablename__ = "audit_events"

    # Column names starting with "model_" are intentional (AI provenance);
    # disable pydantic's protected namespace check for them.
    model_config = ConfigDict(protected_namespaces=())  # type: ignore[assignment]

    id: int | None = Field(default=None, primary_key=True)

    # What / when / where
    occurred_at: datetime = Field(
        sa_type=DateTime(timezone=True),  # type: ignore
        default_factory=utc_now,
        nullable=False,
        index=True,
    )
    category: str = Field(max_length=100, index=True, nullable=False)
    action: str = Field(max_length=100, nullable=False)
    source: str = Field(max_length=20, nullable=False)

    # Who / origin
    actor_type: str = Field(max_length=20, nullable=False)
    actor_id: str | None = Field(default=None, max_length=64, index=True)
    actor_label: str | None = Field(default=None, max_length=255)
    request_ip: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    request_id: str | None = Field(default=None, max_length=64, index=True)

    # Outcome / target
    outcome: str = Field(max_length=20, nullable=False)
    error_detail: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    target_type: str | None = Field(default=None, max_length=100)
    target_id: str | None = Field(default=None, max_length=255)

    # Before/after snapshots of a mutation (AU-3 "what effect"), redacted
    # before persistence. The pair encodes the mutation kind: a create has no
    # old, a delete has no new, an update has both, and non-mutation events
    # (e.g. a login) have neither.
    old_values: dict[str, Any] | None = Field(default=None, sa_column=_json_column())
    new_values: dict[str, Any] | None = Field(default=None, sa_column=_json_column())

    # AI provenance
    tool_name: str | None = Field(default=None, max_length=255)
    tool_args: dict[str, Any] | None = Field(default=None, sa_column=_json_column())
    model_provider: str | None = Field(default=None, max_length=100)
    model_name: str | None = Field(default=None, max_length=255)
    model_version: str | None = Field(default=None, max_length=100)

    # Reserved for FERPA disclosure logging (34 CFR 99.32), deferred from v1
    purpose: str | None = Field(default=None, max_length=255)

    # Pinned canonical serialization, hashed later by the tamper-evidence sealer
    canonical_bytes: bytes = Field(sa_column=Column(LargeBinary, nullable=False))

    @classmethod
    def from_event(cls, event: BaseAuditEvent, context: AuditContext) -> "AuditEvent":
        """Flatten ``event`` and its origin ``context`` into a row.

        The single assembly point for rows: resolves the actor (event actor,
        else context actor, else anonymous) and the timestamp, redacts every
        payload, pins the canonical bytes, and maps the grouped value objects
        onto the flat, indexable columns, so a row can never be constructed
        with columns inconsistent with one another. All construction goes
        through here (via :func:`sparkth.lib.audit.record_event`), never the
        bare field-by-field constructor.
        """
        actor = event.actor or context.actor or ANONYMOUS_ACTOR
        occurred_at = event.occurred_at or utc_now()
        change, target, tool, model = event.change, event.target, event.tool, event.model
        redacted_old = redact(change.old) if change is not None and change.old is not None else None
        redacted_new = redact(change.new) if change is not None and change.new is not None else None
        redacted_args = redact(tool.args) if tool is not None and tool.args is not None else None

        canonical_bytes = canonicalize(
            {
                "event_type": event.event_type,
                "occurred_at": occurred_at.isoformat(),
                "source": context.source.value,
                "actor": {"type": actor.type.value, "id": actor.id, "label": actor.label},
                "outcome": event.outcome.value,
                "target": {
                    "type": target.type if target is not None else None,
                    "id": target.id if target is not None else None,
                },
                "error_detail": event.error_detail,
                "old_values": redacted_old,
                "new_values": redacted_new,
                "tool": {"name": tool.name if tool is not None else None, "args": redacted_args},
                "model": {
                    "provider": model.provider if model is not None else None,
                    "name": model.name if model is not None else None,
                    "version": model.version if model is not None else None,
                },
                "purpose": event.purpose,
            }
        )

        return cls(
            occurred_at=occurred_at,
            category=event.category,
            action=event.action,
            source=context.source.value,
            actor_type=actor.type.value,
            actor_id=actor.id,
            actor_label=actor.label,
            request_ip=context.request_ip,
            user_agent=context.user_agent,
            request_id=context.request_id,
            outcome=event.outcome.value,
            error_detail=event.error_detail,
            target_type=target.type if target is not None else None,
            target_id=target.id if target is not None else None,
            old_values=redacted_old,
            new_values=redacted_new,
            tool_name=tool.name if tool is not None else None,
            tool_args=redacted_args,
            model_provider=model.provider if model is not None else None,
            model_name=model.name if model is not None else None,
            model_version=model.version if model is not None else None,
            purpose=event.purpose,
            canonical_bytes=canonical_bytes,
        )
