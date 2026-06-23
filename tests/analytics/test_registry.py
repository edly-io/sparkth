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
