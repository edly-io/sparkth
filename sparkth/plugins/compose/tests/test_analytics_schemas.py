"""The Compose plugin's analytics event schemas and their registration.

Registration happens in ComposePlugin.__init__, which the plugin loader runs once when
the app is imported — so these tests read the process-wide hook rather than
constructing a second ComposePlugin (which would raise DuplicateEventTypeError).
"""

import logging
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks
from pydantic import ValidationError

from sparkth.lib.analytics import AnalyticsEventSchema, get_event_schema
from sparkth.lib.audit import ToolFailureKind
from sparkth.plugins.compose.analytics import (
    AnalyticsAttribution,
    ComposeCompletionServed,
    ComposeConversationStarted,
    ComposeMessageSent,
    ComposeToolInvoked,
    ComposeTurnAnalytics,
    ExecutedTool,
    StopPoint,
    ToolOutcome,
    emit_completion,
    executed_tools_from,
)
from sparkth.plugins.compose.detached import join_live_tasks, live_tasks

ALL_SCHEMAS = [
    ComposeConversationStarted,
    ComposeMessageSent,
    ComposeCompletionServed,
    ComposeToolInvoked,
]

# One fully valid payload per schema, so the extra="forbid" test can fail on the
# unexpected key alone rather than on missing required fields.
VALID_PAYLOADS: list[tuple[type[AnalyticsEventSchema], dict[str, Any]]] = [
    (ComposeConversationStarted, {"conversation_id": "abc", "provider": "openai", "model": "gpt-4o"}),
    (
        ComposeMessageSent,
        {
            "conversation_id": "abc",
            "provider": "openai",
            "model": "gpt-4o",
            "message_length": 42,
            "has_attachment": False,
        },
    ),
    (
        ComposeCompletionServed,
        {
            "conversation_id": "abc",
            "provider": "openai",
            "model": "gpt-4o",
            "streamed": True,
            "rag_used": False,
            "tool_call_count": 2,
            "stopped_at": None,
        },
    ),
    (
        ComposeToolInvoked,
        {
            "conversation_id": "abc",
            "tool_name": "openedx_create_xblock",
            "tool_category": "openedx-course",
            "outcome": "succeeded",
            "failure_kind": None,
        },
    ),
]


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s.event_type)
def test_schema_is_registered_under_its_own_identity(schema: type[AnalyticsEventSchema]) -> None:
    assert get_event_schema(schema.event_type, schema.version) is schema


@pytest.mark.parametrize("schema", ALL_SCHEMAS, ids=lambda s: s.event_type)
def test_event_types_are_namespaced_compose(schema: type[AnalyticsEventSchema]) -> None:
    assert schema.event_type.startswith("compose.")


def test_conversation_started_payload() -> None:
    event = ComposeConversationStarted(conversation_id="abc", provider="openai", model="gpt-4o")
    assert event.model_dump(mode="json") == {
        "conversation_id": "abc",
        "provider": "openai",
        "model": "gpt-4o",
    }


def test_message_sent_payload() -> None:
    event = ComposeMessageSent(
        conversation_id="abc",
        provider="openai",
        model="gpt-4o",
        message_length=42,
        has_attachment=False,
    )
    assert event.message_length == 42
    assert event.has_attachment is False


def test_completion_served_payload() -> None:
    event = ComposeCompletionServed(
        conversation_id="abc",
        provider="openai",
        model="gpt-4o",
        streamed=True,
        rag_used=False,
        tool_call_count=2,
        stopped_at=None,
    )
    assert event.streamed is True
    assert event.tool_call_count == 2


def test_tool_invoked_payload() -> None:
    event = ComposeToolInvoked(
        conversation_id="abc",
        tool_name="openedx_create_xblock",
        tool_category="openedx-course",
        outcome=ToolOutcome.FAILED,
        failure_kind=ToolFailureKind.AUTH,
    )
    assert event.tool_name == "openedx_create_xblock"
    assert event.tool_category == "openedx-course"
    assert event.model_dump(mode="json")["failure_kind"] == "auth"


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
        ComposeMessageSent(
            conversation_id="abc",
            provider="openai",
            model="gpt-4o",
            message_length=-1,
            has_attachment=False,
        )

    assert [error["type"] for error in exc_info.value.errors()] == ["greater_than_equal"]


def _completion_payload(**overrides: Any) -> dict[str, Any]:
    return {
        "conversation_id": "abc",
        "provider": "openai",
        "model": "gpt-4o",
        "streamed": True,
        "rag_used": False,
        "tool_call_count": 0,
        "stopped_at": None,
        **overrides,
    }


@pytest.mark.parametrize("field", ["outcome", "failure_kind"])
def test_tool_invoked_requires_its_outcome_fields(field: str) -> None:
    """New writes must carry the keys, so a missing one is a producer bug."""
    payload: dict[str, Any] = {
        "conversation_id": "abc",
        "tool_name": "openedx_create_xblock",
        "tool_category": "openedx-course",
        "outcome": "succeeded",
        "failure_kind": None,
    }
    del payload[field]

    with pytest.raises(ValidationError) as exc_info:
        ComposeToolInvoked(**payload)

    assert [error["type"] for error in exc_info.value.errors()] == ["missing"]


def test_completion_served_requires_stopped_at() -> None:
    """New writes must carry the key, so a missing one is a producer bug."""
    payload = _completion_payload()
    del payload["stopped_at"]

    with pytest.raises(ValidationError) as exc_info:
        ComposeCompletionServed(**payload)

    assert [error["type"] for error in exc_info.value.errors()] == ["missing"]


def test_completion_served_accepts_each_stop_point() -> None:
    for stop_point in StopPoint:
        assert ComposeCompletionServed(**_completion_payload(stopped_at=stop_point)).stopped_at == stop_point


def test_completion_served_rejects_an_unknown_stop_point() -> None:
    with pytest.raises(ValidationError):
        ComposeCompletionServed(**_completion_payload(stopped_at="later"))


def test_tool_call_count_rejects_a_negative_count() -> None:
    """A producer bug must fail validation rather than silently skew aggregates."""
    with pytest.raises(ValidationError) as exc_info:
        ComposeCompletionServed(
            conversation_id="abc",
            provider="openai",
            model="gpt-4o",
            streamed=True,
            rag_used=False,
            tool_call_count=-1,
            stopped_at=None,
        )

    assert [error["type"] for error in exc_info.value.errors()] == ["greater_than_equal"]


def test_attribution_is_frozen() -> None:
    attribution = AnalyticsAttribution(provider="openai", actor_id="7")
    with pytest.raises(FrozenInstanceError):
        attribution.provider = "changed"  # type: ignore[misc]


class TestExecutedToolsFrom:
    """One normaliser for both completion paths' differently-shaped records."""

    def test_reads_streaming_shape(self) -> None:
        records: list[dict[str, Any]] = [
            {"name": "openedx_create_xblock", "failure": None},
            {"name": "canvas_create_quiz", "failure": ToolFailureKind.AUTH},
        ]
        assert executed_tools_from(records) == [
            ExecutedTool("openedx_create_xblock", None),
            ExecutedTool("canvas_create_quiz", ToolFailureKind.AUTH),
        ]

    def test_reads_non_streaming_shape(self) -> None:
        records = [
            {"tool": "openedx_create_xblock", "tool_input": {"a": 1}, "output": "created"},
            {"tool": "canvas_create_quiz", "tool_input": {}, "output": "ok", "failure": ToolFailureKind.NOT_FOUND},
        ]
        assert executed_tools_from(records) == [
            ExecutedTool("openedx_create_xblock", None),
            ExecutedTool("canvas_create_quiz", ToolFailureKind.NOT_FOUND),
        ]

    def test_returns_only_names_never_inputs_or_outputs(self) -> None:
        """tool_input and output can hold course content — they must never be read."""
        records = [{"tool": "openedx_create_xblock", "tool_input": {"secret": "pii"}, "output": "learner data"}]
        assert executed_tools_from(records) == [ExecutedTool("openedx_create_xblock", None)]

    def test_empty_list_yields_no_names(self) -> None:
        assert executed_tools_from([]) == []

    def test_records_without_a_usable_name_are_dropped(self) -> None:
        assert executed_tools_from([{"tool_input": {}}, {"name": ""}, {"name": None}]) == []

    def test_a_dropped_record_is_logged_with_keys_only(self, caplog: pytest.LogCaptureFixture) -> None:
        """A silent drop would zero tool analytics with no trace if a path renamed its key.

        Only the record's keys may be logged — its values can hold course content.
        """
        record = {"tool_input": {"secret": "pii"}, "output": "learner data"}
        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.compose.analytics.utils"):
            assert executed_tools_from([record]) == []

        assert "tool_input" in caplog.text
        assert "pii" not in caplog.text
        assert "learner data" not in caplog.text

    def test_preserves_order_and_duplicates(self) -> None:
        """Two executions of the same tool are two authoring actions, not one."""
        records = [{"name": "canvas_create_question"}, {"name": "canvas_create_question"}]
        assert executed_tools_from(records) == [ExecutedTool("canvas_create_question", None)] * 2


MOMENT = datetime(2026, 9, 18, 12, 30, tzinfo=timezone.utc)


def _turn_seam(background_tasks: BackgroundTasks) -> ComposeTurnAnalytics:
    return ComposeTurnAnalytics(
        background_tasks=background_tasks,
        conversation_id="conv-1",
        provider="openai",
        model="gpt-4o",
        actor_id="7",
    )


class TestSchedulingATurnEvent:
    """A seam sends one event and builds its payload when the task runs, not at the seam.

    ``schedule_message_sent`` detaches its task; every other seam queues it on
    ``background_tasks``.

    Driven through the seam rather than a per-event emit helper: the seam is the only
    surface a call site touches, and building inside the task is the property that keeps
    a bad payload from reaching the request. Both are only visible from here.

    Every event carries ``occurred_at`` rather than letting the write path default it:
    these all run from tasks that fire after the turn they describe, so a defaulted time
    would stamp a whole turn at the end of it.
    """

    async def test_conversation_started_is_emitted_when_the_queue_runs(self) -> None:
        background_tasks = BackgroundTasks()
        with patch("sparkth.plugins.compose.analytics.utils.emit_event", new_callable=AsyncMock) as emit:
            _turn_seam(background_tasks).schedule_conversation_started(occurred_at=MOMENT)
            emit.assert_not_awaited()  # queued, not awaited: nothing happens until the response is flushed
            await background_tasks()

        emit.assert_awaited_once_with(
            "compose.conversation_started",
            1,
            {"conversation_id": "conv-1", "provider": "openai", "model": "gpt-4o"},
            actor_id="7",
            occurred_at=MOMENT,
        )

    async def test_message_sent_lands_without_the_response(self) -> None:
        """Detached rather than queued, so it lands even when the turn's route raises and
        the response that would run the queue never goes out."""
        background_tasks = BackgroundTasks()
        with patch("sparkth.plugins.compose.analytics.utils.emit_event", new_callable=AsyncMock) as emit:
            _turn_seam(background_tasks).schedule_message_sent(
                message_length=12, has_attachment=True, occurred_at=MOMENT
            )
            assert background_tasks.tasks == []
            await join_live_tasks()

        emit.assert_awaited_once_with(
            "compose.message_sent",
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
            patch("sparkth.plugins.compose.analytics.utils.emit_events", new_callable=AsyncMock) as emit,
            patch("sparkth.plugins.compose.analytics.utils.get_tool_registry") as get_registry,
        ):
            get_registry.return_value.category_for.return_value = "openedx-course"
            await emit_completion(
                conversation_id="conv-2",
                attribution=attribution,
                model="claude-sonnet-5",
                rag_used=True,
                streamed=True,
                executed_tools=[
                    ExecutedTool("openedx_create_xblock", None),
                    ExecutedTool("canvas_create_quiz", ToolFailureKind.UPSTREAM),
                ],
                occurred_at=MOMENT,
            )

        emit.assert_awaited_once()
        assert emit.await_args is not None
        landed = emit.await_args.args[0]
        assert [event.event_type for event in landed] == [
            "compose.completion_served",
            "compose.tool_invoked",
            "compose.tool_invoked",
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
            "stopped_at": None,
        }
        assert [event.payload["tool_name"] for event in landed[1:]] == [
            "openedx_create_xblock",
            "canvas_create_quiz",
        ]
        assert landed[1].payload["tool_category"] == "openedx-course"
        assert [(event.payload["outcome"], event.payload["failure_kind"]) for event in landed[1:]] == [
            ("succeeded", None),
            ("failed", "upstream"),
        ]
        # The tools ran during the completion and neither path times them individually,
        # so the whole group shares the moment the reply was delivered.
        assert {event.occurred_at for event in landed} == {MOMENT}

    async def test_emit_completion_without_tools_emits_only_the_completion(self) -> None:
        attribution = AnalyticsAttribution(provider="openai", actor_id="7")
        with patch("sparkth.plugins.compose.analytics.utils.emit_events", new_callable=AsyncMock) as emit:
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
        assert [event.event_type for event in landed] == ["compose.completion_served"]
        assert landed[0].payload["tool_call_count"] == 0
        assert landed[0].occurred_at == MOMENT

    async def test_a_negative_count_raises_in_the_task_and_not_at_the_seam(self) -> None:
        """The non-negative guard fires at the producer, so no skewed row can be written —
        but it must fire in the detached task, not while the request is still running.

        The schema is built by the task rather than by ``schedule_*``, so scheduling a bad
        count is silent and the ``ValidationError`` surfaces in the task, where asyncio logs
        it as an unretrieved task exception, as for ``record_turn_failed``. Were the event
        built at the seam, a skewed count would destroy the turn it only measures.
        """
        background_tasks = BackgroundTasks()
        with patch("sparkth.plugins.compose.analytics.utils.emit_event", new_callable=AsyncMock) as emit:
            _turn_seam(background_tasks).schedule_message_sent(
                message_length=-1, has_attachment=False, occurred_at=MOMENT
            )
            # join_live_tasks swallows task errors, so await the task itself to see this one.
            (task,) = live_tasks
            with pytest.raises(ValidationError):
                await task

        emit.assert_not_awaited()
