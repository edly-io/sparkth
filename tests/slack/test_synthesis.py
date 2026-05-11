"""Unit tests for Slack RAG LLM synthesis."""

from unittest.mock import AsyncMock

import pytest

from app.core_plugins.slack.synthesis import _MAX_QUESTION_LEN, SYNTHESIS_SYSTEM_PROMPT, synthesize_answer


@pytest.mark.asyncio
async def test_synthesize_returns_llm_content() -> None:
    provider = AsyncMock()
    provider.send_message = AsyncMock(return_value={"content": "Recursion is when a function calls itself."})

    result = await synthesize_answer(
        question="What is recursion?",
        context="[DOCUMENT CONTEXT: python.pdf]\nRecursion is a function that calls itself.",
        provider=provider,
    )

    assert result == "Recursion is when a function calls itself."


@pytest.mark.asyncio
async def test_synthesize_passes_question_and_context_in_user_message() -> None:
    provider = AsyncMock()
    provider.send_message = AsyncMock(return_value={"content": "Answer."})

    await synthesize_answer(
        question="What is OOP?",
        context="[DOCUMENT CONTEXT: java.pdf]\nOOP uses classes and objects.",
        provider=provider,
    )

    call_args = provider.send_message.call_args
    messages = call_args.kwargs.get("messages") or call_args[0][0]

    assert len(messages) == 1
    user_msg = messages[0]
    assert user_msg["role"] == "user"
    assert "What is OOP?" in user_msg["content"]
    assert "OOP uses classes and objects." in user_msg["content"]


@pytest.mark.asyncio
async def test_synthesize_raises_when_content_missing() -> None:
    provider = AsyncMock()
    provider.send_message = AsyncMock(return_value={"content": ""})

    with pytest.raises(ValueError, match="empty or missing content"):
        await synthesize_answer(
            question="test",
            context="test context",
            provider=provider,
        )


@pytest.mark.asyncio
async def test_question_wrapped_in_xml_delimiters() -> None:
    provider = AsyncMock()
    provider.send_message = AsyncMock(return_value={"content": "Answer."})

    await synthesize_answer(
        question="What is OOP?",
        context="context",
        provider=provider,
    )

    user_content = provider.send_message.call_args.kwargs["messages"][0]["content"]
    assert "<student_question>What is OOP?</student_question>" in user_content


@pytest.mark.asyncio
async def test_question_truncated_to_max_length() -> None:
    provider = AsyncMock()
    provider.send_message = AsyncMock(return_value={"content": "Answer."})
    long_question = "x" * (_MAX_QUESTION_LEN + 500)

    await synthesize_answer(
        question=long_question,
        context="context",
        provider=provider,
    )

    user_content = provider.send_message.call_args.kwargs["messages"][0]["content"]
    assert "x" * (_MAX_QUESTION_LEN + 500) not in user_content
    assert "x" * _MAX_QUESTION_LEN in user_content


def test_system_prompt_contains_injection_guardrail() -> None:
    assert "override" in SYNTHESIS_SYSTEM_PROMPT.lower() or "instruction" in SYNTHESIS_SYSTEM_PROMPT.lower()
    assert "reveal" in SYNTHESIS_SYSTEM_PROMPT.lower() or "sensitive" in SYNTHESIS_SYSTEM_PROMPT.lower()
