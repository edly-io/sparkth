"""The chat plugin's analytics event schemas and their registration.

Registration happens in ChatPlugin.__init__, which the plugin loader runs once when
the app is imported — so these tests read the process-wide hook rather than
constructing a second ChatPlugin (which would raise DuplicateEventTypeError).
"""

import logging
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from sparkth.lib.analytics import AnalyticsEventSchema, get_event_schema
from sparkth.plugins.chat.analytics import (
    AnalyticsAttribution,
    ChatCompletionServed,
    ChatConversationStarted,
    ChatMessageSent,
    ChatToolInvoked,
    emit_completion,
    emit_conversation_started,
    emit_message_sent,
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


def test_attribution_is_frozen() -> None:
    attribution = AnalyticsAttribution(provider="openai", actor_id="7")
    with pytest.raises(FrozenInstanceError):
        attribution.provider = "changed"  # type: ignore[misc]


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


MOMENT = datetime(2026, 9, 18, 12, 30, tzinfo=timezone.utc)


class TestEmitHelpers:
    """Each helper builds one payload and hands it to the emission primitive.

    Every helper forwards ``occurred_at`` rather than letting the write path default it:
    these all run from tasks that fire after the turn they describe, so a defaulted time
    would stamp a whole turn at the end of it.
    """

    async def test_emit_conversation_started(self) -> None:
        with patch("sparkth.plugins.chat.analytics.emit_event", new_callable=AsyncMock) as emit:
            await emit_conversation_started(
                conversation_id="conv-1", provider="openai", model="gpt-4o", actor_id="7", occurred_at=MOMENT
            )

        emit.assert_awaited_once_with(
            "chat.conversation_started",
            1,
            {"conversation_id": "conv-1", "provider": "openai", "model": "gpt-4o"},
            actor_id="7",
            occurred_at=MOMENT,
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
                occurred_at=MOMENT,
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
            occurred_at=MOMENT,
        )

    async def test_emit_completion_lands_the_completion_and_every_tool_in_one_call(self) -> None:
        """One emit_events call, so the group shares a session and cannot half-queue."""
        attribution = AnalyticsAttribution(provider="anthropic", actor_id="9")
        with (
            patch("sparkth.plugins.chat.analytics.emit_events", new_callable=AsyncMock) as emit,
            patch("sparkth.plugins.chat.analytics.get_tool_registry") as get_registry,
        ):
            get_registry.return_value.category_for.return_value = "openedx-course"
            await emit_completion(
                conversation_id="conv-2",
                attribution=attribution,
                model="claude-sonnet-5",
                rag_used=True,
                streamed=True,
                executed_tools=["openedx_create_xblock", "canvas_create_quiz"],
                occurred_at=MOMENT,
            )

        emit.assert_awaited_once()
        assert emit.await_args is not None
        landed = emit.await_args.args[0]
        assert [event.event_type for event in landed] == [
            "chat.completion_served",
            "chat.tool_invoked",
            "chat.tool_invoked",
        ]
        assert {event.actor_id for event in landed} == {"9"}
        assert landed[0].payload == {
            "conversation_id": "conv-2",
            "provider": "anthropic",
            "model": "claude-sonnet-5",
            "streamed": True,
            "rag_used": True,
            # Derived from the tool list, so it cannot disagree with the events beside it.
            "tool_call_count": 2,
        }
        assert [event.payload["tool_name"] for event in landed[1:]] == [
            "openedx_create_xblock",
            "canvas_create_quiz",
        ]
        assert landed[1].payload["tool_category"] == "openedx-course"
        # The tools ran during the completion and neither path times them individually,
        # so the whole group shares the moment the reply was delivered.
        assert {event.occurred_at for event in landed} == {MOMENT}

    async def test_emit_completion_without_tools_emits_only_the_completion(self) -> None:
        attribution = AnalyticsAttribution(provider="openai", actor_id="7")
        with patch("sparkth.plugins.chat.analytics.emit_events", new_callable=AsyncMock) as emit:
            await emit_completion(
                conversation_id="conv-4",
                attribution=attribution,
                model="gpt-4o",
                rag_used=False,
                streamed=False,
                executed_tools=[],
                occurred_at=MOMENT,
            )

        emit.assert_awaited_once()
        assert emit.await_args is not None
        landed = emit.await_args.args[0]
        assert [event.event_type for event in landed] == ["chat.completion_served"]
        assert landed[0].payload["tool_call_count"] == 0
        assert landed[0].occurred_at == MOMENT

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
                    occurred_at=MOMENT,
                )

        emit.assert_not_awaited()
