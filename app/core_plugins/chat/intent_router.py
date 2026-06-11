"""RAG Intent Router — decides per-turn whether to run document retrieval."""

import asyncio
from pathlib import Path
from typing import Any, cast

from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.core_plugins.chat.exceptions import RAGIntentRouterError
from app.core_plugins.chat.schemas import RAGRoutingDecision
from app.lib.documents import Document
from app.lib.log import get_logger
from app.lib.rag import get_document_structure

logger = get_logger(__name__)

# Load system prompt at module import time
_SYSTEM_PROMPT = (Path(__file__).parent / "assets" / "rag_intent_router_system_prompt.txt").read_text()


class RAGIntentRouter:
    """Routes per-turn chat messages to decide whether to run RAG retrieval."""

    def __init__(self, llm: Any) -> None:
        """Initialize the router with an LLM instance.

        Args:
            llm: A LangChain LLM that supports with_structured_output.
        """
        self._chain: Any = llm.with_structured_output(RAGRoutingDecision)

    async def decide(
        self,
        *,
        query: str,
        attached_documents: list[Document],
        user_id: int,
    ) -> RAGRoutingDecision:
        """Decide whether to run RAG retrieval for this turn.

        Args:
            query: The user's query text.
            attached_documents: Documents attached to the conversation.
            user_id: The user ID passed to the public RAG document-structure API.

        Returns:
            RAGRoutingDecision with should_retrieve and reason.

        Raises:
            RAGIntentRouterError: If the router's LLM call fails.
        """
        # Build attachment summary with section metadata
        attachment_summary = ""
        if attached_documents:
            documents = [doc for doc in attached_documents if doc.id is not None]
            results = await asyncio.gather(
                *[get_document_structure(user_id=user_id, document_id=cast(int, doc.id)) for doc in documents],
                return_exceptions=True,
            )

            if documents:
                attachment_summary = "The user has attached the following documents:\n"
                for document, sections_or_exc in zip(documents, results):
                    attachment_summary += f"\n- {document.name}:\n"
                    if isinstance(sections_or_exc, BaseException):
                        logger.warning(
                            "Failed to get document structure for document %d: %s",
                            cast(int, document.id),
                            sections_or_exc,
                        )
                        continue
                    for section in sections_or_exc:
                        path_parts = [section.chapter, section.section, section.subsection]
                        path = " / ".join(p for p in path_parts if p is not None)
                        if path:
                            attachment_summary += f"  - {path}\n"

        # Build messages for the router chain
        human_text = query
        if attachment_summary:
            human_text = f"{query}\n\n{attachment_summary}"

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_text),
        ]

        # Call the chain and handle errors
        try:
            result = await self._chain.ainvoke(messages)
            return cast(RAGRoutingDecision, result)
        except (LangChainException, ValidationError) as exc:
            logger.error("Router LLM failed: %s", exc)
            raise RAGIntentRouterError(f"Router LLM failed: {exc}") from exc
