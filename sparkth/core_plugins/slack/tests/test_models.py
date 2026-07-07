"""Unit tests for Slack plugin models."""

from sparkth.core_plugins.slack.enums import ConnectionEventType, ResponseType
from sparkth.core_plugins.slack.models import (
    BotResponseLog,
    SlackConnectionLog,
)


class TestResponseType:
    def test_has_all_expected_values(self) -> None:
        assert set(ResponseType) == {
            ResponseType.RAG_MATCH,
            ResponseType.FALLBACK,
            ResponseType.GREETING,
            ResponseType.CONFIG_INCOMPLETE,
            ResponseType.PLUGIN_DISABLED,
            ResponseType.LEGACY,
            ResponseType.NO_FILES_RESOLVED,
            ResponseType.RAG_NOT_READY,
            ResponseType.DRIVE_FILE_NOT_FOUND,
            ResponseType.RETRIEVAL_ERROR,
        }

    def test_is_str_enum(self) -> None:
        assert isinstance(ResponseType.RAG_MATCH, str)
        assert ResponseType.RAG_MATCH.value == "rag_match"


class TestConnectionEventType:
    def test_has_connected_and_disconnected(self) -> None:
        assert set(ConnectionEventType) == {
            ConnectionEventType.CONNECTED,
            ConnectionEventType.DISCONNECTED,
        }

    def test_is_str_enum(self) -> None:
        assert isinstance(ConnectionEventType.CONNECTED, str)


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
            response_type=ResponseType.FALLBACK,
        )
        assert log.slack_user_name is None
        assert log.slack_channel_name is None


class TestSlackConnectionLog:
    def test_can_instantiate(self) -> None:
        log = SlackConnectionLog(
            workspace_id=1,
            event_type=ConnectionEventType.CONNECTED,
            team_name="Acme Inc",
        )
        assert log.event_type == ConnectionEventType.CONNECTED
        assert log.team_name == "Acme Inc"

    def test_team_name_is_optional(self) -> None:
        log = SlackConnectionLog(workspace_id=1, event_type=ConnectionEventType.DISCONNECTED)
        assert log.team_name is None
