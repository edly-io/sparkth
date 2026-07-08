"""AuditEvent.from_event is the single assembly point: it flattens a domain
event plus its origin context into the append-only row, resolving the actor
and timestamp, redacting payloads, and pinning the canonical bytes in one
place so a row can never be built with mutually inconsistent columns."""

from dataclasses import dataclass
from typing import ClassVar

from sparkth.core.audit.constants import REDACTED
from sparkth.core.audit.models import AuditEvent
from sparkth.lib.audit.context import AuditRequestContext, AuditSystemContext, UserActor
from sparkth.lib.audit.events import (
    AIActionAuditEvent,
    AuditChange,
    AuditOutcome,
    AuditToolCall,
    LoginAuditEvent,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallEvent(AIActionAuditEvent):
    """AI-category event; from_event is pure assembly, so no registration needed."""

    event_type: ClassVar[str] = "test.model_tool_call"


def test_from_event_flattens_event_actor_and_context() -> None:
    context = AuditRequestContext(
        request_id="req-1",
        request_ip="9.9.9.9",
        user_agent="pytest-agent",
        actor=UserActor(id="7", label="alice"),
    )
    row = AuditEvent.from_event(LoginAuditEvent(outcome=AuditOutcome.SUCCESS), context)

    assert (row.category, row.action) == ("auth", "login")
    assert row.outcome == "success"
    assert (row.actor_type, row.actor_id, row.actor_label) == ("user", "7", "alice")
    assert (row.request_id, row.request_ip, row.user_agent) == ("req-1", "9.9.9.9", "pytest-agent")
    assert row.source == "rest"
    assert row.occurred_at is not None
    assert row.canonical_bytes


def test_from_event_falls_back_to_anonymous_actor() -> None:
    row = AuditEvent.from_event(LoginAuditEvent(outcome=AuditOutcome.FAILURE), AuditSystemContext())
    assert row.actor_type == "anonymous"
    assert row.actor_id is None


def test_from_event_redacts_payloads() -> None:
    event = ToolCallEvent(
        outcome=AuditOutcome.SUCCESS,
        tool=AuditToolCall(name="canvas_create_course", args={"auth": {"api_token": "s3cret"}, "course_id": 5}),
        change=AuditChange(new={"password": "hunter2", "name": "n"}),
    )
    row = AuditEvent.from_event(event, AuditSystemContext())
    assert row.tool_args == {"auth": REDACTED, "course_id": 5}
    assert row.new_values == {"password": REDACTED, "name": "n"}


def test_from_event_leaves_ai_columns_empty_for_base_events() -> None:
    row = AuditEvent.from_event(LoginAuditEvent(outcome=AuditOutcome.SUCCESS), AuditSystemContext())
    assert (row.tool_name, row.tool_args) == (None, None)
    assert (row.model_provider, row.model_name, row.model_version) == (None, None, None)
    assert (row.old_values, row.new_values, row.purpose) == (None, None, None)
