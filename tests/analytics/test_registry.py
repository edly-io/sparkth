import pytest
from pydantic import ValidationError

import app.analytics.schemas  # noqa: F401 -- registers schemas on import
from app.analytics.exceptions import UnknownEventTypeError
from app.analytics.registry import EventRegistry, event_registry
from app.analytics.schemas.v1.assessment_submitted import AssessmentSubmitted


def test_resolve_returns_registered_schema() -> None:
    assert event_registry.resolve("assessment.submitted", 1) is AssessmentSubmitted


def test_resolve_unknown_event_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        event_registry.resolve("does.not.exist", 1)


def test_resolve_unknown_version_of_known_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        event_registry.resolve("assessment.submitted", 999)


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
