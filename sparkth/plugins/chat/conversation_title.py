from fastapi import BackgroundTasks

from sparkth.lib.db import session_scope
from sparkth.lib.llm import BaseChatProvider, get_provider
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.config import ChatSettings, get_chat_settings
from sparkth.plugins.chat.messages import get_first_user_text
from sparkth.plugins.chat.schemas import ChatMessage
from sparkth.plugins.chat.service import ChatService

logger = get_logger(__name__)


def extract_title_from_messages(messages: list[ChatMessage], max_length: int) -> str | None:
    """Derive a provisional conversation title from the first user message."""
    text = get_first_user_text(messages)
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0] + "..."


async def generate_conversation_title(
    conversation_id: int,
    user_id: int,
    first_user_message: str,
    service: ChatService,
    provider: BaseChatProvider,
) -> None:
    """Background task: ask the LLM for a short title and persist it.

    The title follows the language of the message it is derived from, which the model
    reads off the message itself — titles are user-visible in the conversation sidebar,
    so a Spanish conversation must not be labelled in English.
    """
    config = get_chat_settings()
    try:
        prompt = (
            "Generate a concise 3-6 word title for a conversation that starts with the "
            "following message. Write the title in the same language as the message. "
            "Reply with only the title, no quotes or punctuation:\n\n"
            f"{first_user_message[: config.title_prompt_max_chars]}"
        )
        response = await provider.send_message(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=config.title_llm_max_tokens,
        )
        title = response["content"].strip().strip("\"'").strip()
        if title:
            async with session_scope() as session:
                await service.update_conversation_title(
                    session=session,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    title=title[: config.title_db_max_length],
                )
            logger.info("Generated title for conversation %d: %r", conversation_id, title)
    except (KeyError, ValueError, RuntimeError, OSError) as e:
        logger.warning("Title generation failed for conversation %d: %s", conversation_id, e)


def schedule_title_generation(
    background_tasks: BackgroundTasks,
    service: ChatService,
    *,
    conversation_id: int,
    user_id: int,
    messages: list[ChatMessage],
    provider_name: str,
    api_key: str,
    model: str,
    config: ChatSettings,
) -> None:
    """Queue LLM title generation for a conversation that has just been created.

    Skipped when the request carries no user text: there would be nothing to title from, and the
    provisional title already covers that case.
    """
    first_user_text = get_first_user_text(messages)
    if not first_user_text:
        return
    background_tasks.add_task(
        generate_conversation_title,
        conversation_id=conversation_id,
        user_id=user_id,
        first_user_message=first_user_text,
        service=service,
        provider=get_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            temperature=config.title_llm_temperature,
            max_tool_executions=0,
        ),
    )
