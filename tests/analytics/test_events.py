from collections.abc import Generator

import pytest
from pydantic import ValidationError

from sparkth.core.analytics import ANALYTICS_EVENTS, get_event_schema
from sparkth.core.analytics.schemas import AssessmentSubmitted
from sparkth.lib.analytics import AnalyticsEventSchema, UnknownEventTypeError


class _SampleEvent(AnalyticsEventSchema):
    event_type = "sample.event"
    version = 7

    value: int


class _SampleEventConflict(AnalyticsEventSchema):
    # Same (event_type, version) as _SampleEvent, different class.
    event_type = "sample.event"
    version = 7

    other: str


@pytest.fixture(autouse=True)
def _cleanup_sample_registrations() -> Generator[None, None, None]:
    yield
    ANALYTICS_EVENTS.remove(("sample.event", 7))


def test_get_event_schema_returns_registered_schema() -> None:
    assert get_event_schema("assessment.submitted", 1) is AssessmentSubmitted


def test_get_event_schema_unknown_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        get_event_schema("does.not.exist", 1)


def test_get_event_schema_unknown_version_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        get_event_schema("assessment.submitted", 999)


def test_add_item_registers_by_identity() -> None:
    ANALYTICS_EVENTS.add_item(_SampleEvent)
    assert get_event_schema("sample.event", 7) is _SampleEvent


def test_add_item_same_class_twice_raises() -> None:
    # Re-adding the same object under an already-registered key raises
    ANALYTICS_EVENTS.add_item(_SampleEvent)
    with pytest.raises(ValueError):
        ANALYTICS_EVENTS.add_item(_SampleEvent)
    assert get_event_schema("sample.event", 7) is _SampleEvent


def test_add_item_conflicting_class_raises() -> None:
    # The generic hook raises a plain ValueError on a colliding key; the
    # domain-specific DuplicateEventTypeError is raised one layer up by
    # register_event_schema (see test_plugin_registration.py).
    ANALYTICS_EVENTS.add_item(_SampleEvent)
    with pytest.raises(ValueError):
        ANALYTICS_EVENTS.add_item(_SampleEventConflict)
    assert get_event_schema("sample.event", 7) is _SampleEvent


def test_core_events_are_registered() -> None:
    from sparkth.core.analytics.schemas.v1.user_logged_in import UserLoggedIn

    assert get_event_schema("assessment.submitted", 1) is AssessmentSubmitted
    assert get_event_schema("user.logged_in", 1) is UserLoggedIn


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
    from sparkth.core.analytics.schemas.v1 import UserLoggedIn

    with pytest.raises(ValidationError):
        UserLoggedIn.model_validate({"username": "alice", "extra": "bad"})
