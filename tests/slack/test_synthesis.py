"""Unit tests for Slack RAG LLM synthesis."""

from unittest.mock import AsyncMock

import pytest

from app.core_plugins.slack.synthesis import synthesize_answer


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
