"""LLM synthesis layer for the Slack TA Bot RAG pipeline."""

from typing import Any

from app.core.logger import get_logger
from app.llm.providers import BaseChatProvider

logger = get_logger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """You are a helpful teaching assistant answering student questions.

You will receive the student's question and relevant excerpts from course materials.
Use ONLY the provided excerpts to answer. Do not invent information.

Rules:
- Answer in a clear, concise, and friendly tone suitable for students.
- If the excerpts do not fully answer the question, say what you can and note what is unclear.
- Do not repeat the excerpts verbatim — synthesize them into a natural answer.
- Keep the answer focused and under 300 words."""


async def synthesize_answer(
    question: str,
    context: str,
    provider: BaseChatProvider,
) -> str:
    """Send the user question and retrieved context to the LLM for synthesis.

    Returns the LLM's synthesized answer string.
    """
    user_content = f"## Student Question\n{question}\n\n## Course Material Excerpts\n{context}"

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
