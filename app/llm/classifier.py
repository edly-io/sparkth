"""LLM-based scope classifier for the learning design assistant."""

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.exceptions import LangChainException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from app.core.logger import get_logger

logger = get_logger(__name__)

_CLASSIFIER_SYSTEM_PROMPT = """You are a binary intent classifier for a learning design assistant chatbot.

The chatbot's purpose is ONLY to help users design and create online educational content. Decide whether the user's message is within that scope.

IMPORTANT: Evaluate scope using the full conversation, not the latest message in isolation. If the user's message is a direct reply to a question the assistant asked (e.g., answering "Who is the audience?" with a role or name), it is IN SCOPE — even if the message looks unrelated on its own.

IN SCOPE — respond in_scope: true:
- Designing or creating courses, lessons, or modules
- Writing learning objectives, outcomes, or competencies
- Building curriculum, syllabi, or course outlines
- Creating educational assessments (quizzes, exams, knowledge checks)
- Applying instructional design principles (cognitive load, scaffolding, spaced repetition, ILO alignment)
- Reviewing, editing, or improving educational content
- Analyzing a target audience for a course
- Short answers, clarifications, or confirmations that are replies to the assistant's own course-creation questions

OUT OF SCOPE — respond in_scope: false:
- General knowledge questions (history facts, geography, science trivia, current events)
- Writing, debugging, or explaining code
- Personal advice (medical, legal, financial, psychological)
- Creative writing unrelated to course content (poems, fiction, stories)
- Real-time information (news, weather, stock prices)
- Translating or rewriting documents unrelated to course design
- Any task not related to building or improving educational content"""

# Cheapest capable model per provider — classification uses few tokens and needs low latency
_CLASSIFIER_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5",
    "google": "gemini-2.0-flash",
}


class _ScopeResult(BaseModel):
    in_scope: bool


class ScopeClassifier:
    """LLM-based scope classifier for the learning design assistant.

    Uses a cheap, fast model with structured output to classify whether a user
    query is within the assistant's learning design scope.

    Fails open (returns True) on any error — the main LLM's system prompt acts
    as a safety net for borderline cases.
    """

    def __init__(self, provider_name: str, api_key: str) -> None:
        classifier_model = _CLASSIFIER_MODELS.get(provider_name)
        if classifier_model is None:
            raise ValueError(f"Unsupported provider for classifier: {provider_name!r}")

        llm: Any
        match provider_name:
            case "openai":
                llm = ChatOpenAI(api_key=api_key, model=classifier_model, temperature=0)  # type: ignore[call-arg]
            case "anthropic":
                llm = ChatAnthropic(api_key=api_key, model=classifier_model, temperature=0)  # type: ignore[call-arg]
            case "google":
                llm = ChatGoogleGenerativeAI(google_api_key=api_key, model=classifier_model, temperature=0)

        self._chain: Any = llm.with_structured_output(_ScopeResult)

    async def classify(self, query: str, history: list[dict[str, str]] | None = None) -> bool:
        """Return True if the query is within learning design scope.

        Accepts optional conversation history (list of {"role": ..., "content": ...} dicts)
        so the classifier can determine if the current message is a reply to an assistant question.

        Fails open on any error — the main LLM's system prompt handles
        out-of-scope requests as a fallback.
        """
        if not query.strip():
            return True

        # Build messages: system prompt + up to last 6 history turns + current query
        messages: list[Any] = [SystemMessage(content=_CLASSIFIER_SYSTEM_PROMPT)]
        for turn in (history or [])[-6:]:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if not isinstance(content, str):
                continue
            if role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "user":
                messages.append(HumanMessage(content=content))
        messages.append(HumanMessage(content=query))

        try:
            result: _ScopeResult = await self._chain.ainvoke(messages)
            return result.in_scope
        except (LangChainException, ValidationError) as exc:
            logger.warning("Scope classifier failed, defaulting to in_scope=True: %s", exc)
            return True
