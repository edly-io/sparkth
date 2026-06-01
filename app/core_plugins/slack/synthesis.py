"""LLM synthesis layer for the Slack TA Bot RAG pipeline."""

from typing import Any

from app.core_plugins.slack.config import get_slack_system_config
from app.lib.log import get_logger
from app.llm.providers import BaseChatProvider

logger = get_logger(__name__)


async def synthesize_answer(
    question: str,
    context: str,
    provider: BaseChatProvider,
) -> str:
    """Send the user question and retrieved context to the LLM for synthesis.

    Returns the LLM's synthesized answer string.
    """
    safe_question = question[: get_slack_system_config().MAX_QUESTION_LEN]
    user_content = (
        f"## Student Question\n"
        f"<student_question>{safe_question}</student_question>\n\n"
        f"## Course Material Excerpts\n{context}"
    )

    response: dict[str, Any] = await provider.send_message(messages=[{"role": "user", "content": user_content}])
    raw_content = response.get("content")
    if not raw_content:
        logger.error("Synthesis provider returned no content: response=%r", response)
        raise ValueError("LLM provider returned an empty or missing content field")
    content: str = str(raw_content)
    logger.info(
        "Synthesis complete: question_len=%d context_len=%d answer_len=%d",
        len(question),
        len(context),
        len(content),
    )
    return content
