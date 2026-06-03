from app.core_plugins.chat.config import get_chat_settings
from app.core_plugins.chat.schemas import ChatMessage
from app.core_plugins.chat.service import ChatService
from app.lib.db import session_scope
from app.lib.log import get_logger
from app.llm.providers import BaseChatProvider

logger = get_logger(__name__)


def get_first_user_text(messages: list[ChatMessage]) -> str | None:
    """Return the raw text of the first user message (no truncation)."""
    for msg in messages:
        if msg.role != "user":
            continue
        if isinstance(msg.content, str):
            text = msg.content.strip()
        else:
            text = " ".join(
                block.get("text", "")
                for block in msg.content
                if isinstance(block, dict) and block.get("type") == "text"
            ).strip()
        if text:
            return text
    return None


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
    """Background task: ask the LLM for a short title and persist it."""
    config = get_chat_settings()
    try:
        prompt = (
            "Generate a concise 3-6 word title for a conversation that starts with "
            "the following message. Reply with only the title, no quotes or punctuation:\n\n"
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
