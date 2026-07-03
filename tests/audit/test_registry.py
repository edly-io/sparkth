"""The audit event registry mirrors the analytics EventRegistry: a singleton
mapping event-type strings to definitions, so recording an unknown event type
is a programming error surfaced loudly, never a silently mistyped category."""

import pytest

from app.lib.audit import (
    AuditEventDefinition,
    AuditEventRegistry,
    DuplicateAuditEventTypeError,
    UnknownAuditEventTypeError,
)


def test_registry_is_a_singleton() -> None:
    assert AuditEventRegistry() is AuditEventRegistry()


def test_core_login_event_is_registered() -> None:
    definition = AuditEventRegistry().resolve("auth.login")
    assert definition.category == "auth"
    assert definition.action == "login"


def test_unknown_event_type_raises() -> None:
    with pytest.raises(UnknownAuditEventTypeError):
        AuditEventRegistry().resolve("nope.never")


def test_reregistering_the_same_definition_is_a_noop() -> None:
    registry = AuditEventRegistry()
    definition = registry.resolve("auth.login")
    registry.register(definition)
    assert registry.resolve("auth.login") is definition


def test_conflicting_definition_for_same_type_raises() -> None:
    registry = AuditEventRegistry()
    with pytest.raises(DuplicateAuditEventTypeError):
        registry.register(AuditEventDefinition(event_type="auth.login", fail_open=True))


def test_event_type_must_be_category_dot_action() -> None:
    with pytest.raises(ValueError):
        AuditEventDefinition(event_type="loginwithoutdot")
