"""RAG Intent Router — decides per-turn whether to run document retrieval."""

import asyncio
from pathlib import Path
from typing import Any, cast

from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.core_plugins.chat.schemas import RAGRoutingDecision
from app.core_plugins.googledrive.models import DriveFile
from app.lib.log import get_logger
from app.rag.mcp.tools import get_document_structure

logger = get_logger(__name__)

# Load system prompt at module import time
_SYSTEM_PROMPT = (Path(__file__).parent / "assets" / "rag_intent_router_system_prompt.txt").read_text()


class RAGIntentRouterError(Exception):
    """Raised when the router's LLM call fails."""


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
        attached_files: list[DriveFile],
        user_id: int,
    ) -> RAGRoutingDecision:
        """Decide whether to run RAG retrieval for this turn.

        Args:
            query: The user's query text.
            attached_files: List of DriveFile objects attached to the conversation.
            user_id: The user ID passed to get_document_structure.

        Returns:
            RAGRoutingDecision with should_retrieve and reason.

        Raises:
            RAGIntentRouterError: If the router's LLM call fails.
        """
        # Build attachment summary with section metadata
        attachment_summary = ""
        if attached_files:
            files_with_documents = [f for f in attached_files if f.document_id is not None]
            for file in attached_files:
                if file.document_id is None:
                    logger.warning("Skipping attached file %d with no linked document_id", cast(int, file.id))

            results = await asyncio.gather(
                *[
                    get_document_structure(user_id=user_id, document_id=cast(int, f.document_id))
                    for f in files_with_documents
                ],
                return_exceptions=True,
            )

            if files_with_documents:
                attachment_summary = "The user has attached the following files:\n"
                for file, sections_or_exc in zip(files_with_documents, results):
                    attachment_summary += f"\n- {file.name}:\n"
                    if isinstance(sections_or_exc, BaseException):
                        logger.warning(
                            "Failed to get document structure for document %d: %s",
                            cast(int, file.document_id),
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
