from collections.abc import Generator

import pytest
from pydantic import ValidationError

from sparkth.core.analytics.registry import EventRegistry
from sparkth.core.analytics.schemas import AssessmentSubmitted
from sparkth.lib.analytics import AnalyticsEventSchema, DuplicateEventTypeError, UnknownEventTypeError


class _SampleEvent(AnalyticsEventSchema):
    event_type = "sample.event"
    version = 7

    value: int


class _SampleEventConflict(AnalyticsEventSchema):
    # Same (event_type, version) as _SampleEvent, different class.
    event_type = "sample.event"
    version = 7

    other: str


class _SampleServerOnly(AnalyticsEventSchema):
    event_type = "sample.server_only"
    version = 1
    server_only = True

    value: int


class _SampleClientEmittable(AnalyticsEventSchema):
    event_type = "sample.client_emittable"
    version = 1
    server_only = False

    value: int


_SAMPLE_KEYS = [
    ("sample.event", 7),
    ("sample.server_only", 1),
    ("sample.client_emittable", 1),
]


@pytest.fixture(autouse=True)
def _cleanup_sample_registrations() -> Generator[None, None, None]:
    """Remove sample.* keys from the singleton after each test.

    Mirrors the conftest cleanup for test.client_event — without this, a later
    test registering a different class under the same key would hit a spurious
    DuplicateEventTypeError from leftover state.
    """
    yield
    for key in _SAMPLE_KEYS:
        EventRegistry()._schemas.pop(key, None)
        EventRegistry()._server_only.pop(key, None)


def test_registry_is_singleton() -> None:
    assert EventRegistry() is EventRegistry()


def test_resolve_returns_registered_schema() -> None:
    assert EventRegistry().resolve("assessment.submitted", 1) is AssessmentSubmitted


def test_resolve_unknown_event_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        EventRegistry().resolve("does.not.exist", 1)


def test_resolve_unknown_version_of_known_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        EventRegistry().resolve("assessment.submitted", 999)


def test_register_derives_key_from_class() -> None:
    EventRegistry().register(_SampleEvent)
    assert EventRegistry().resolve("sample.event", 7) is _SampleEvent


def test_register_same_class_twice_is_idempotent() -> None:
    EventRegistry().register(_SampleEvent)
    EventRegistry().register(_SampleEvent)  # no error, no warning
    assert EventRegistry().resolve("sample.event", 7) is _SampleEvent


def test_register_conflicting_class_raises() -> None:
    EventRegistry().register(_SampleEvent)
    # A different class claiming the same (event_type, version) is a programming
    # error — analytics raises rather than silently keeping one schema, because a
    # producer's payload would otherwise validate against the wrong schema.
    with pytest.raises(DuplicateEventTypeError):
        EventRegistry().register(_SampleEventConflict)
    # The first registration is unaffected.
    assert EventRegistry().resolve("sample.event", 7) is _SampleEvent


def test_server_only_defaults_to_true() -> None:
    # Default-deny: _SampleEvent declares no server_only, so it is server-only.
    EventRegistry().register(_SampleEvent)
    assert EventRegistry().is_server_only("sample.event", 7) is True


def test_server_only_derived_from_class() -> None:
    EventRegistry().register(_SampleServerOnly)
    assert EventRegistry().is_server_only("sample.server_only", 1) is True


def test_server_only_false_is_an_explicit_opt_in() -> None:
    EventRegistry().register(_SampleClientEmittable)
    assert EventRegistry().is_server_only("sample.client_emittable", 1) is False


def test_core_events_are_server_only() -> None:
    assert EventRegistry().is_server_only("assessment.submitted", 1) is True
    assert EventRegistry().is_server_only("user.logged_in", 1) is True


def test_is_server_only_raises_for_unregistered_event() -> None:
    with pytest.raises(UnknownEventTypeError):
        EventRegistry().is_server_only("does.not.exist", 1)


def test_register_missing_identity_raises_descriptive_error() -> None:
    class _Incomplete(AnalyticsEventSchema):
        value: int  # forgot event_type and version

    with pytest.raises(TypeError, match="_Incomplete"):
        EventRegistry().register(_Incomplete)


def test_sample_schema_validates_good_payload() -> None:
    model = AssessmentSubmitted.model_validate(
        {"learner_id": "u1", "competency_id": "c1", "score": 0.9, "passed": True}
    )
    assert model.passed is True


def test_sample_schema_rejects_bad_payload() -> None:
    with pytest.raises(ValidationError):
        AssessmentSubmitted.model_validate({"learner_id": "u1"})


def test_assessment_submitted_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AssessmentSubmitted.model_validate(
            {"learner_id": "u1", "competency_id": "c1", "score": 0.9, "passed": True, "extra": "bad"}
        )


def test_user_logged_in_rejects_extra_fields() -> None:
    from sparkth.core.analytics.schemas.v1.user_logged_in import UserLoggedIn

    with pytest.raises(ValidationError):
        UserLoggedIn.model_validate({"username": "alice", "extra": "bad"})
