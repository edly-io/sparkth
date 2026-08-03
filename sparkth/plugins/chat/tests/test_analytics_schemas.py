"""The chat plugin's analytics event schemas and their registration.

Registration happens in ChatPlugin.__init__, which the plugin loader runs once when
the app is imported — so these tests read the process-wide hook rather than
constructing a second ChatPlugin (which would raise DuplicateEventTypeError).
"""

import pytest
from pydantic import ValidationError

from sparkth.lib.analytics import AnalyticsEventSchema, get_event_schema
from sparkth.plugins.chat.analytics import (
    ChatCompletionServed,
    ChatConversationStarted,
    ChatMessageSent,
    ChatToolInvoked,
    CompletionAnalyticsContext,
    tool_names,
)

ALL_SCHEMAS = [
    ChatConversationStarted,
    ChatMessageSent,
    ChatCompletionServed,
    ChatToolInvoked,
]


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s.event_type)
def test_schema_is_registered_under_its_own_identity(schema: type[AnalyticsEventSchema]) -> None:
    assert get_event_schema(schema.event_type, schema.version) is schema


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s.event_type)
def test_event_type_is_namespaced_under_the_plugin(schema: type[AnalyticsEventSchema]) -> None:
    assert schema.event_type.startswith("chat.")


def test_conversation_started_payload() -> None:
    event = ChatConversationStarted(conversation_id="abc", provider="openai", model="gpt-4o")
    assert event.model_dump(mode="json") == {
        "conversation_id": "abc",
        "provider": "openai",
        "model": "gpt-4o",
    }


def test_message_sent_payload() -> None:
    event = ChatMessageSent(
        conversation_id="abc",
        provider="openai",
        model="gpt-4o",
        message_length=42,
        has_attachment=False,
    )
    assert event.message_length == 42
    assert event.has_attachment is False


def test_completion_served_payload() -> None:
    event = ChatCompletionServed(
        conversation_id="abc",
        provider="openai",
        model="gpt-4o",
        streamed=True,
        rag_used=False,
        tool_call_count=2,
    )
    assert event.streamed is True
    assert event.tool_call_count == 2


def test_tool_invoked_payload() -> None:
    event = ChatToolInvoked(
        conversation_id="abc",
        tool_name="openedx_create_xblock",
        tool_category="openedx-course",
    )
    assert event.tool_name == "openedx_create_xblock"
    assert event.tool_category == "openedx-course"


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s.event_type)
def test_schemas_forbid_extra_fields(schema: type[AnalyticsEventSchema]) -> None:
    """extra="forbid" on the base class stops a producer smuggling content into a payload."""
    with pytest.raises(ValidationError):
        schema(unexpected_field="leak")  # type: ignore[call-arg]


def test_completion_context_is_frozen() -> None:
    context = CompletionAnalyticsContext(provider="openai", model="gpt-4o", rag_used=True, actor_id="7")
    with pytest.raises(Exception):
        context.model = "changed"  # type: ignore[misc]


class TestToolNames:
    """One normaliser for both completion paths' differently-shaped records."""

    def test_reads_streaming_shape(self) -> None:
        records = [{"name": "openedx_create_xblock"}, {"name": "canvas_create_quiz"}]
        assert tool_names(records) == ["openedx_create_xblock", "canvas_create_quiz"]

    def test_reads_non_streaming_shape(self) -> None:
        records = [
            {"tool": "openedx_create_xblock", "tool_input": {"a": 1}, "output": "created"},
            {"tool": "canvas_create_quiz", "tool_input": {}, "output": "ok"},
        ]
        assert tool_names(records) == ["openedx_create_xblock", "canvas_create_quiz"]

    def test_returns_only_names_never_inputs_or_outputs(self) -> None:
        """tool_input and output can hold course content — they must never be read."""
        records = [{"tool": "openedx_create_xblock", "tool_input": {"secret": "pii"}, "output": "learner data"}]
        assert tool_names(records) == ["openedx_create_xblock"]

    def test_empty_list_yields_no_names(self) -> None:
        assert tool_names([]) == []

    def test_records_without_a_usable_name_are_dropped(self) -> None:
        assert tool_names([{"tool_input": {}}, {"name": ""}, {"name": None}]) == []

    def test_preserves_order_and_duplicates(self) -> None:
        """Two executions of the same tool are two authoring actions, not one."""
        records = [{"name": "canvas_create_question"}, {"name": "canvas_create_question"}]
        assert tool_names(records) == ["canvas_create_question", "canvas_create_question"]
