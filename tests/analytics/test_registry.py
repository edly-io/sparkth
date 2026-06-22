import pytest
from pydantic import ValidationError

from app.analytics.exceptions import UnknownEventTypeError
from app.analytics.registry import EventRegistry
from app.analytics.schemas.v1.assessment_submitted import AssessmentSubmitted


def test_registry_is_singleton() -> None:
    assert EventRegistry() is EventRegistry()


def test_reconstruction_preserves_registered_schemas() -> None:
    EventRegistry().register("sample.persisted", 1, AssessmentSubmitted)
    # Re-constructing returns the same instance, so prior registrations survive
    # an accidental EventRegistry() call elsewhere.
    assert EventRegistry().resolve("sample.persisted", 1) is AssessmentSubmitted


def test_resolve_returns_registered_schema() -> None:
    assert EventRegistry().resolve("assessment.submitted", 1) is AssessmentSubmitted


def test_resolve_unknown_event_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        EventRegistry().resolve("does.not.exist", 1)


def test_resolve_unknown_version_of_known_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        EventRegistry().resolve("assessment.submitted", 999)


def test_register_and_resolve_roundtrip() -> None:
    registry = EventRegistry()
    registry.register("sample.event", 2, AssessmentSubmitted)
    assert registry.resolve("sample.event", 2) is AssessmentSubmitted


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
    from app.analytics.schemas.v1.user_logged_in import UserLoggedIn

    with pytest.raises(ValidationError):
        UserLoggedIn.model_validate({"username": "alice", "extra": "bad"})


def test_server_only_defaults_to_false() -> None:
    registry = EventRegistry()
    registry.register("sample.event", 1, AssessmentSubmitted)
    assert registry.is_server_only("sample.event", 1) is False


def test_server_only_can_be_set_true() -> None:
    registry = EventRegistry()
    registry.register("secure.event", 1, AssessmentSubmitted, server_only=True)
    assert registry.is_server_only("secure.event", 1) is True


def test_is_server_only_raises_for_unregistered_event() -> None:
    registry = EventRegistry()
    with pytest.raises(UnknownEventTypeError):
        registry.is_server_only("does.not.exist", 1)
