"""Request and response schemas for reading the audit trail: the filter set, one row
in summary and in full, a page of rows, and the export query."""

from datetime import datetime
from typing import Any, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from sparkth.lib.audit.context import AuditSource
from sparkth.lib.audit.events import AuditOutcome
from sparkth.services.audit.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from sparkth.services.audit.enums import ExportFormat


class AuditEventQuery(BaseModel):
    """Filters over the audit trail; every one is optional and they combine with AND.

    ``from`` and ``to`` bound ``occurred_at`` inclusively and must carry a timezone, so
    a range never silently shifts by the server's offset. ``actor_id`` is a user id, the
    only actor that carries one, so anything but a positive integer of at most 64 digits
    is rejected, matching the column width.
    """

    model_config = ConfigDict(populate_by_name=True)

    from_: AwareDatetime | None = Field(default=None, alias="from")
    to: AwareDatetime | None = None
    actor_id: str | None = Field(default=None, max_length=64, pattern=r"^[1-9][0-9]*$")
    category: str | None = None
    action: str | None = None
    outcome: AuditOutcome | None = None
    source: AuditSource | None = None
    target_type: str | None = None
    target_id: str | None = None
    request_id: str | None = None

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise PydanticCustomError("range_reversed", "'from' must not be after 'to'")
        return self


class AuditEventPageQuery(AuditEventQuery):
    """The filters plus a keyset cursor: up to ``limit`` events older than ``before_id``."""

    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    before_id: int | None = Field(default=None, ge=1)


class AuditEventExportQuery(AuditEventQuery):
    """The filters plus the shape the export streams as."""

    export_format: ExportFormat = Field(default=ExportFormat.CSV, alias="format")


class AuditEventSummary(BaseModel):
    """One audit row as the listing shows it: when, what, who, outcome and target.

    The rest of the row (request metadata, changed values, tool and model details) is
    read on demand as an :class:`AuditEventRecord`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    occurred_at: datetime
    category: str
    action: str
    source: str
    actor_type: str
    actor_id: str | None
    actor_label: str | None
    outcome: str
    target_type: str | None
    target_id: str | None


class AuditEventRecord(BaseModel):
    """One audit row in full: every column but the sealed canonical bytes."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    occurred_at: datetime
    category: str
    action: str
    source: str
    actor_type: str
    actor_id: str | None
    actor_label: str | None
    request_ip: str | None
    user_agent: str | None
    request_id: str | None
    outcome: str
    error_detail: str | None
    target_type: str | None
    target_id: str | None
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    tool_name: str | None
    tool_args: dict[str, Any] | None
    model_provider: str | None
    model_name: str | None
    model_version: str | None
    purpose: str | None


class AuditEventPage(BaseModel):
    """A page of events, most recently recorded first.

    Pass ``next_before_id`` back as ``before_id`` for the next one.
    """

    items: list[AuditEventSummary]
    next_before_id: int | None
