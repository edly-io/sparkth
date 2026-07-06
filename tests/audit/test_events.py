"""Audit event types are self-describing classes: each carries its own
identity (event_type, fail_open) and the grouped envelope fields, and is
registered on the module-level AUDIT_EVENTS hook so a duplicate event type
collides loudly at registration time, never silently overwrites."""

from dataclasses import dataclass
from typing import ClassVar

import pytest

from app.lib.audit import (
    AUDIT_EVENTS,
    AuditOutcome,
    BaseAuditEvent,
    DuplicateAuditEventTypeError,
    LoginAuditEvent,
    UnknownAuditEventTypeError,
)


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
