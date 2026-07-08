from sparkth.core.analytics.schemas import AssessmentSubmitted, UserLoggedIn
from sparkth.lib.analytics import AnalyticsEventSchema


def test_core_schemas_subclass_base() -> None:
    assert issubclass(AssessmentSubmitted, AnalyticsEventSchema)
    assert issubclass(UserLoggedIn, AnalyticsEventSchema)


def test_schemas_declare_identity_and_policy() -> None:
    assert AssessmentSubmitted.event_type == "assessment.submitted"
    assert AssessmentSubmitted.version == 1
    assert AssessmentSubmitted.server_only is True
    assert UserLoggedIn.event_type == "user.logged_in"
    assert UserLoggedIn.version == 1
    assert UserLoggedIn.server_only is True


def test_server_only_defaults_to_true_on_base() -> None:
    # Default-deny: an event that says nothing is server-only.
    class _DefaultEvent(AnalyticsEventSchema):
        event_type = "sample.default_event"
        version = 1

        detail: str

    assert _DefaultEvent.server_only is True


def test_server_only_is_an_explicit_opt_in_to_client_emission() -> None:
    class _ClientEvent(AnalyticsEventSchema):
        event_type = "sample.client_event"
        version = 1
        server_only = False

        detail: str

    assert _ClientEvent.server_only is False


def test_identity_attrs_are_not_pydantic_fields() -> None:
    # event_type / version / server_only are ClassVar metadata, not validated payload.
    assert "event_type" not in UserLoggedIn.model_fields
    assert "version" not in UserLoggedIn.model_fields
    assert "server_only" not in UserLoggedIn.model_fields
    # The actual payload field is still present.
    assert "username" in UserLoggedIn.model_fields


def test_payload_round_trips_without_identity_attrs() -> None:
    model = UserLoggedIn.model_validate({"username": "alice"})
    assert model.model_dump(mode="json") == {"username": "alice"}
