"""Audit event types are self-describing classes: each carries its own
identity (event_type, fail_open) and the grouped envelope fields, and is
registered on the module-level AUDIT_EVENTS hook so a duplicate event type
collides loudly at registration time, never silently overwrites."""

from dataclasses import dataclass
from typing import ClassVar

import pytest

from sparkth.lib.audit.events import (
    AIActionAuditEvent,
    AuditChange,
    AuditModelInfo,
    AuditOutcome,
    AuditToolCall,
    BaseAuditEvent,
    LoginAuditEvent,
    MutationAuditEvent,
)
from sparkth.lib.audit.exceptions import DuplicateAuditEventTypeError, UnknownAuditEventTypeError
from sparkth.lib.audit.hooks import AUDIT_EVENTS


def test_core_login_event_is_registered() -> None:
    assert AUDIT_EVENTS.resolve("auth.login") is LoginAuditEvent


def test_category_and_action_derive_from_event_type() -> None:
    event = LoginAuditEvent(outcome=AuditOutcome.SUCCESS)
    assert event.category == "auth"
    assert event.action == "login"


def test_unknown_event_type_raises() -> None:
    with pytest.raises(UnknownAuditEventTypeError):
        AUDIT_EVENTS.resolve("nope.never")


def test_reregistering_the_same_class_is_a_noop() -> None:
    AUDIT_EVENTS.register(LoginAuditEvent)
    assert AUDIT_EVENTS.resolve("auth.login") is LoginAuditEvent


def test_conflicting_class_for_same_event_type_raises() -> None:
    @dataclass(frozen=True, slots=True, kw_only=True)
    class ImposterLogin(BaseAuditEvent):
        event_type: ClassVar[str] = "auth.login"

    with pytest.raises(DuplicateAuditEventTypeError):
        AUDIT_EVENTS.register(ImposterLogin)


def test_event_type_must_be_category_dot_action() -> None:
    @dataclass(frozen=True, slots=True, kw_only=True)
    class Dotless(BaseAuditEvent):
        event_type: ClassVar[str] = "loginwithoutdot"

    with pytest.raises(ValueError):
        AUDIT_EVENTS.register(Dotless)


def test_fail_open_defaults_to_false() -> None:
    assert LoginAuditEvent.fail_open is False


def test_base_events_carry_no_mutation_or_ai_fields() -> None:
    with pytest.raises(TypeError):
        LoginAuditEvent(outcome=AuditOutcome.SUCCESS, change=AuditChange(new={"a": 1}))  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        LoginAuditEvent(outcome=AuditOutcome.SUCCESS, tool=AuditToolCall(name="t"))  # type: ignore[call-arg]


def test_mutation_events_carry_a_change() -> None:
    @dataclass(frozen=True, slots=True, kw_only=True)
    class CourseUpdate(MutationAuditEvent):
        event_type: ClassVar[str] = "course.update"

    event = CourseUpdate(outcome=AuditOutcome.SUCCESS, change=AuditChange(new={"name": "b"}))
    assert event.change is not None
    with pytest.raises(TypeError):
        CourseUpdate(outcome=AuditOutcome.SUCCESS, tool=AuditToolCall(name="t"))  # type: ignore[call-arg]


def test_ai_action_events_carry_provenance_and_change() -> None:
    @dataclass(frozen=True, slots=True, kw_only=True)
    class ToolCall(AIActionAuditEvent):
        event_type: ClassVar[str] = "ai.tool_call"

    event = ToolCall(
        outcome=AuditOutcome.SUCCESS,
        tool=AuditToolCall(name="canvas_create_course"),
        model=AuditModelInfo(provider="anthropic"),
        purpose="course generation",
        change=AuditChange(new={"id": 1}),
    )
    assert event.tool is not None
    assert event.model is not None
    assert event.change is not None


def test_audit_change_accepts_create_update_and_delete_shapes() -> None:
    assert AuditChange(new={"name": "a"}).old is None
    assert AuditChange(old={"name": "a"}).new is None
    change = AuditChange(old={"name": "a"}, new={"name": "b"})
    assert (change.old, change.new) == ({"name": "a"}, {"name": "b"})


def test_audit_change_with_neither_side_raises() -> None:
    with pytest.raises(ValueError, match="old.*new|new.*old"):
        AuditChange()
