"""RAG Intent Router — decides per-turn whether to run document retrieval."""

from pathlib import Path
from typing import Any, cast

from langchain_core.exceptions import LangChainException
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.chat.schemas import RAGRoutingDecision
from app.models.drive import DriveFile

logger = get_logger(__name__)

# Load system prompt at module import time
_SYSTEM_PROMPT = (Path(__file__).parent / "assets" / "rag_intent_router_system_prompt.txt").read_text()


class RAGIntentRouterError(Exception):
    """Raised when the router's LLM call fails."""

    pass


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
        session: AsyncSession,
        user_id: int,
    ) -> RAGRoutingDecision:
        """Decide whether to run RAG retrieval for this turn.

        Args:
            query: The user's query text.
            attached_files: List of DriveFile objects attached to the conversation.
            session: Database session for accessing file metadata.
            user_id: The user ID for context.

        Returns:
            RAGRoutingDecision with should_retrieve and reason.

        Raises:
            RAGIntentRouterError: If the router's LLM call fails.
        """
        # Build attachment summary with section metadata
        attachment_summary = ""
        if attached_files:
            # Lazy import to avoid initializing DB at module level
            from app.rag_mcp.tools import get_document_structure

            attachment_summary = "The user has attached the following files:\n"
            for file in attached_files:
                attachment_summary += f"\n- {file.name}:\n"
                try:
                    sections = await get_document_structure(user_id=user_id, file_id=cast(int, file.id))
                    if sections:
                        for section in sections:
                            # Format section path
                            path_parts = [
                                section.chapter,
                                section.section,
                                section.subsection,
                            ]
                            path = " / ".join(p for p in path_parts if p is not None)
                            if path:
                                attachment_summary += f"  - {path}\n"
                    else:
                        # No sections found, just list the file
                        pass
                except SQLAlchemyError as e:
                    logger.warning(
                        "Failed to get document structure for file %d: %s",
                        file.id,
                        e,
                    )
                    # Continue without section detail

        # Build messages for the router chain
        human_text = f"{query}"
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
