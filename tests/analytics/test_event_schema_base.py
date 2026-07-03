from sparkth.core.analytics.schemas import AssessmentSubmitted, UserLoggedIn
from sparkth.lib.analytics import AnalyticsEventSchema


def test_core_schemas_subclass_base() -> None:
    assert issubclass(AssessmentSubmitted, AnalyticsEventSchema)
    assert issubclass(UserLoggedIn, AnalyticsEventSchema)


def test_schemas_declare_identity() -> None:
    assert AssessmentSubmitted.event_type == "assessment.submitted"
    assert AssessmentSubmitted.version == 1
    assert UserLoggedIn.event_type == "user.logged_in"
    assert UserLoggedIn.version == 1


def test_identity_attrs_are_not_pydantic_fields() -> None:
    # event_type / version are ClassVar metadata, not validated payload.
    assert "event_type" not in UserLoggedIn.model_fields
    assert "version" not in UserLoggedIn.model_fields
    # The actual payload field is still present.
    assert "username" in UserLoggedIn.model_fields


def test_payload_round_trips_without_identity_attrs() -> None:
    model = UserLoggedIn.model_validate({"username": "alice"})
    assert model.model_dump(mode="json") == {"username": "alice"}
