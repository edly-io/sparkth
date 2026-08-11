"""The chat plugin's analytics event schemas and their registration.

Registration happens in ChatPlugin.__init__, which the plugin loader runs once when
the app is imported — so these tests read the process-wide hook rather than
constructing a second ChatPlugin (which would raise DuplicateEventTypeError).
"""

import logging
from dataclasses import FrozenInstanceError
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from sparkth.lib.analytics import AnalyticsEventSchema, get_event_schema
from sparkth.plugins.chat.analytics import (
    ChatCompletionServed,
    ChatConversationStarted,
    ChatMessageSent,
    ChatToolInvoked,
    CompletionAnalyticsContext,
    emit_completion_served,
    emit_conversation_started,
    emit_message_sent,
    emit_tool_invoked,
    tool_names,
)

ALL_SCHEMAS = [
    ChatConversationStarted,
    ChatMessageSent,
    ChatCompletionServed,
    ChatToolInvoked,
]

# One fully valid payload per schema, so the extra="forbid" test can fail on the
# unexpected key alone rather than on missing required fields.
VALID_PAYLOADS: list[tuple[type[AnalyticsEventSchema], dict[str, Any]]] = [
    (ChatConversationStarted, {"conversation_id": "abc", "provider": "openai", "model": "gpt-4o"}),
    (
        ChatMessageSent,
        {
            "conversation_id": "abc",
            "provider": "openai",
            "model": "gpt-4o",
            "message_length": 42,
            "has_attachment": False,
        },
    ),
    (
        ChatCompletionServed,
        {
            "conversation_id": "abc",
            "provider": "openai",
            "model": "gpt-4o",
            "streamed": True,
            "rag_used": False,
            "tool_call_count": 2,
        },
    ),
    (
        ChatToolInvoked,
        {"conversation_id": "abc", "tool_name": "openedx_create_xblock", "tool_category": "openedx-course"},
    ),
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


@pytest.mark.parametrize(("schema", "payload"), VALID_PAYLOADS, ids=[schema.event_type for schema, _ in VALID_PAYLOADS])
def test_schemas_forbid_extra_fields(schema: type[AnalyticsEventSchema], payload: dict[str, Any]) -> None:
    """extra="forbid" on the base class stops a producer smuggling content into a payload.

    Everything but the extra key is valid, so ``extra_forbidden`` must be the *only*
    error raised — a missing-field error would make this pass even without the guard.
    """
    with pytest.raises(ValidationError) as exc_info:
        schema.model_validate({**payload, "unexpected_field": "leak"})

    assert [error["type"] for error in exc_info.value.errors()] == ["extra_forbidden"]


def test_message_length_rejects_a_negative_count() -> None:
    """A producer bug must fail validation rather than silently skew aggregates."""
    with pytest.raises(ValidationError) as exc_info:
        ChatMessageSent(
            conversation_id="abc",
            provider="openai",
            model="gpt-4o",
            message_length=-1,
            has_attachment=False,
        )

    assert [error["type"] for error in exc_info.value.errors()] == ["greater_than_equal"]


def test_tool_call_count_rejects_a_negative_count() -> None:
    """A producer bug must fail validation rather than silently skew aggregates."""
    with pytest.raises(ValidationError) as exc_info:
        ChatCompletionServed(
            conversation_id="abc",
            provider="openai",
            model="gpt-4o",
            streamed=True,
            rag_used=False,
            tool_call_count=-1,
        )

    assert [error["type"] for error in exc_info.value.errors()] == ["greater_than_equal"]


def test_completion_context_is_frozen() -> None:
    context = CompletionAnalyticsContext(provider="openai", model="gpt-4o", rag_used=True, actor_id="7")
    with pytest.raises(FrozenInstanceError):
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

    def test_a_dropped_record_is_logged_with_keys_only(self, caplog: pytest.LogCaptureFixture) -> None:
        """A silent drop would zero tool analytics with no trace if a path renamed its key.

        Only the record's keys may be logged — its values can hold course content.
        """
        record = {"tool_input": {"secret": "pii"}, "output": "learner data"}
        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.analytics"):
            assert tool_names([record]) == []

        assert "tool_input" in caplog.text
        assert "pii" not in caplog.text
        assert "learner data" not in caplog.text

    def test_preserves_order_and_duplicates(self) -> None:
        """Two executions of the same tool are two authoring actions, not one."""
        records = [{"name": "canvas_create_question"}, {"name": "canvas_create_question"}]
        assert tool_names(records) == ["canvas_create_question", "canvas_create_question"]


class TestEmitHelpers:
    """Each helper builds one payload and hands it to the emission primitive."""

    async def test_emit_conversation_started(self) -> None:
        with patch("sparkth.plugins.chat.analytics.emit_event", new_callable=AsyncMock) as emit:
            await emit_conversation_started(conversation_id="conv-1", provider="openai", model="gpt-4o", actor_id="7")

        emit.assert_awaited_once_with(
            "chat.conversation_started",
            1,
            {"conversation_id": "conv-1", "provider": "openai", "model": "gpt-4o"},
            actor_id="7",
        )

    async def test_emit_message_sent(self) -> None:
        with patch("sparkth.plugins.chat.analytics.emit_event", new_callable=AsyncMock) as emit:
            await emit_message_sent(
                conversation_id="conv-1",
                provider="openai",
                model="gpt-4o",
                message_length=12,
                has_attachment=True,
                actor_id="7",
            )

        emit.assert_awaited_once_with(
            "chat.message_sent",
            1,
            {
                "conversation_id": "conv-1",
                "provider": "openai",
                "model": "gpt-4o",
                "message_length": 12,
                "has_attachment": True,
            },
            actor_id="7",
        )

    async def test_emit_completion_served_reads_the_context(self) -> None:
        context = CompletionAnalyticsContext(provider="anthropic", model="claude-sonnet-5", rag_used=True, actor_id="9")
        with patch("sparkth.plugins.chat.analytics.emit_event", new_callable=AsyncMock) as emit:
            await emit_completion_served(conversation_id="conv-2", context=context, tool_call_count=3, streamed=True)

        emit.assert_awaited_once_with(
            "chat.completion_served",
            1,
            {
                "conversation_id": "conv-2",
                "provider": "anthropic",
                "model": "claude-sonnet-5",
                "streamed": True,
                "rag_used": True,
                "tool_call_count": 3,
            },
            actor_id="9",
        )

    async def test_a_negative_count_is_rejected_before_anything_is_emitted(self) -> None:
        """The non-negative guard fires at the producer, so no skewed row can be written.

        Every call site queues these helpers through ``background_tasks.add_task``, so the
        raise lands in the background task after the response has been sent — the same place
        a ``ValidationError`` raised inside ``emit_event`` would have surfaced.
        """
        with patch("sparkth.plugins.chat.analytics.emit_event", new_callable=AsyncMock) as emit:
            with pytest.raises(ValidationError):
                await emit_message_sent(
                    conversation_id="conv-1",
                    provider="openai",
                    model="gpt-4o",
                    message_length=-1,
                    has_attachment=False,
                    actor_id="7",
                )

        emit.assert_not_awaited()

    async def test_emit_tool_invoked_resolves_the_category(self) -> None:
        with (
            patch("sparkth.plugins.chat.analytics.emit_event", new_callable=AsyncMock) as emit,
            patch("sparkth.plugins.chat.analytics.get_tool_registry") as get_registry,
        ):
            get_registry.return_value.category_for.return_value = "openedx-course"
            await emit_tool_invoked(conversation_id="conv-3", tool_name="openedx_create_xblock", actor_id="7")

        emit.assert_awaited_once_with(
            "chat.tool_invoked",
            1,
            {
                "conversation_id": "conv-3",
                "tool_name": "openedx_create_xblock",
                "tool_category": "openedx-course",
            },
            actor_id="7",
        )
