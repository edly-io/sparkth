"""Unit tests for Slack plugin models."""

from app.core_plugins.slack.models import (
    BotResponseLog,
    ConnectionEventType,
    ResponseType,
    SlackConnectionLog,
)


class TestResponseType:
    def test_has_all_expected_values(self) -> None:
        assert set(ResponseType) == {
            ResponseType.rag_match,
            ResponseType.fallback,
            ResponseType.greeting,
            ResponseType.config_incomplete,
            ResponseType.plugin_disabled,
            ResponseType.legacy,
        }

    def test_is_str_enum(self) -> None:
        assert isinstance(ResponseType.rag_match, str)
        assert ResponseType.rag_match == "rag_match"


class TestConnectionEventType:
    def test_has_connected_and_disconnected(self) -> None:
        assert set(ConnectionEventType) == {
            ConnectionEventType.connected,
            ConnectionEventType.disconnected,
        }

    def test_is_str_enum(self) -> None:
        assert isinstance(ConnectionEventType.connected, str)


class TestBotResponseLogFields:
    def test_has_response_type_field(self) -> None:
        fields = BotResponseLog.model_fields
        assert "response_type" in fields

    def test_has_name_fields(self) -> None:
        fields = BotResponseLog.model_fields
        assert "slack_user_name" in fields
        assert "slack_channel_name" in fields

    def test_name_fields_are_nullable(self) -> None:
        log = BotResponseLog(
            workspace_id=1,
            slack_channel="C1",
            slack_user="U1",
            slack_ts="123.0",
            question="q",
            rag_matched=False,
            response_type=ResponseType.fallback,
        )
        assert log.slack_user_name is None
        assert log.slack_channel_name is None


class TestSlackConnectionLog:
    def test_can_instantiate(self) -> None:
        log = SlackConnectionLog(
            workspace_id=1,
            event_type=ConnectionEventType.connected,
            team_name="Acme Inc",
        )
        assert log.event_type == ConnectionEventType.connected
        assert log.team_name == "Acme Inc"

    def test_team_name_is_optional(self) -> None:
        log = SlackConnectionLog(workspace_id=1, event_type=ConnectionEventType.disconnected)
        assert log.team_name is None
