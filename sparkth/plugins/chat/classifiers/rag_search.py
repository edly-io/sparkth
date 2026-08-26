"""The RAG search classifier: does answering this message need the attached documents?

A negative verdict skips retrieval for the turn and reaches the client as a bare status event,
so the reasoning behind it lives only in the log here. A failed decision is fatal to the turn —
the route persists an error rather than guessing.
"""

import asyncio
from typing import cast
from uuid import UUID

from langchain_core.messages import BaseMessage, HumanMessage

from sparkth.lib.documents import Document
from sparkth.lib.log import get_logger
from sparkth.lib.rag import get_rag_ingested_document_structure
from sparkth.plugins.chat.classifiers.base import BaseClassifier
from sparkth.plugins.chat.constants import RAG_SEARCH_CLASSIFIER_SYSTEM_PROMPT
from sparkth.plugins.chat.exceptions import ClassifierError, RAGSearchError
from sparkth.plugins.chat.schemas import DocumentHeadings, RAGSearchInput, RAGSearchVerdict

logger = get_logger(__name__)


async def gather_document_headings(documents: list[Document]) -> list[DocumentHeadings]:
    """Read each document's section headings, naming the ones that cannot be read.

    A document whose structure is unavailable still reaches the model by name: the decision can
    be made from names alone, and losing one document's headings must not cost the turn its
    judgement. Documents with no id have nothing to look up.
    """
    saved = [document for document in documents if document.id is not None]
    # TODO: batch-lookup document structures in a single query instead of one coroutine per document
    results = await asyncio.gather(
        *[get_rag_ingested_document_structure(document_id=cast(int, document.id)) for document in saved],
        return_exceptions=True,
    )

    headings: list[DocumentHeadings] = []
    for document, sections in zip(saved, results):
        if isinstance(sections, BaseException):
            logger.warning("No section headings for document %s: %s", document.id, sections)
            headings.append(DocumentHeadings(name=document.name))
            continue
        paths = [
            " / ".join(part for part in (s.chapter, s.section, s.subsection) if part is not None) for s in sections
        ]
        headings.append(DocumentHeadings(name=document.name, sections=[path for path in paths if path]))
    return headings


class RAGSearchClassifier(BaseClassifier[RAGSearchInput, RAGSearchVerdict]):
    """Decides whether a chat turn needs content retrieved from the conversation's documents."""

    def __init__(self, provider_name: str, api_key: str) -> None:
        super().__init__(
            RAG_SEARCH_CLASSIFIER_SYSTEM_PROMPT,
            RAGSearchInput,
            RAGSearchVerdict,
            provider_name,
            api_key,
        )

    def _build_messages(self, payload: RAGSearchInput) -> list[BaseMessage]:
        """Put the message to the model alongside what each document actually contains.

        Section headings are what make the decision possible: "explain mitochondria" is
        answerable from a document that has such a section and not from one that does not.
        """
        lines = [payload.query, "", "The user has attached the following documents:"]
        for document in payload.documents:
            lines.append(f"\n- {document.name}:")
            lines.extend(f"  - {path}" for path in document.sections)
        return [HumanMessage(content="\n".join(lines))]

    async def requires_search(
        self,
        query: str,
        documents: list[Document],
        conversation_uuid: UUID | None = None,
    ) -> bool:
        """Return whether this turn needs retrieval, as the single boolean callers act on.

        Callers ask only when there is something to search: with no attached documents there is
        nothing to retrieve and no decision to make, so that case never reaches here.

        ``conversation_uuid`` never reaches the model. It is logged on a declined search so the
        skip can be traced to the thread a user reports.

        Raises:
            RAGSearchError: the decision could not be made. Fatal to the turn — retrieval is
                not guessed at, so the route surfaces the failure instead.
        """
        headings = await gather_document_headings(documents)
        try:
            verdict = await self.classify({"query": query, "documents": [h.model_dump() for h in headings]})
        except ClassifierError as exc:
            raise RAGSearchError(str(exc)) from exc

        if not verdict.requires_search:
            # The only record of a skip: the client is told retrieval was skipped, not why.
            logger.info(
                "Search classifier skipped retrieval: conversation_uuid=%s model=%s reason=%r documents=%d",
                conversation_uuid,
                self.model,
                verdict.refusal_reason,
                len(documents),
            )
        return verdict.requires_search
