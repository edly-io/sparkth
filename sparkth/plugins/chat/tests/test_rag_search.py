"""Tests for the RAG search classifier.

Model selection, input validation and failure translation belong to the base and are covered in
test_base_classifier.py. What is asserted here is this classifier's own work: gathering each
attached document's section headings, putting them to the model alongside the query, the single
boolean the route acts on, and the log a declined search leaves — the only trace, since a skip
reaches the client as a bare event.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.exceptions import LangChainException
from langchain_core.messages import BaseMessage

from sparkth.lib.documents import Document, DocumentStatus
from sparkth.plugins.chat.classifiers.rag_search import RAGSearchClassifier
from sparkth.plugins.chat.constants import RAG_SEARCH_CLASSIFIER_SYSTEM_PROMPT
from sparkth.plugins.chat.exceptions import RAGSearchError
from sparkth.plugins.chat.schemas import RAGSearchVerdict

_LOGGER = "sparkth.plugins.chat.classifiers.rag_search"
_STRUCTURE = "sparkth.plugins.chat.classifiers.rag_search.get_rag_ingested_document_structure"


def _classifier_with(chain: MagicMock) -> RAGSearchClassifier:
    """A classifier whose facade-built LLM is replaced by one yielding ``chain``."""
    llm = MagicMock()
    llm.with_structured_output.return_value = chain
    provider = MagicMock()
    provider.create_llm.return_value = llm
    with patch("sparkth.plugins.chat.classifiers.base.get_provider", return_value=provider):
        return RAGSearchClassifier("anthropic", "test-key")


def _chain_deciding(requires_search: bool, refusal_reason: str = "") -> MagicMock:
    chain = MagicMock()
    chain.ainvoke = AsyncMock(
        return_value=RAGSearchVerdict(requires_search=requires_search, refusal_reason=refusal_reason)
    )
    return chain


def _document(document_id: int = 1, name: str = "textbook.pdf") -> Document:
    return Document(id=document_id, user_id=1, name=name, status=DocumentStatus.READY)


def _section(chapter: str | None = None, section: str | None = None, subsection: str | None = None) -> MagicMock:
    heading = MagicMock()
    heading.chapter = chapter
    heading.section = section
    heading.subsection = subsection
    return heading


def _sent_messages(chain: MagicMock) -> list[BaseMessage]:
    messages: list[BaseMessage] = chain.ainvoke.await_args.args[0]
    return messages


class TestTheTurnPutToTheModel:
    """The query alone cannot be judged — what the documents contain decides it."""

    @pytest.mark.asyncio
    async def test_the_shipped_prompt_leads_the_call(self) -> None:
        chain = _chain_deciding(True)

        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]):
            await _classifier_with(chain).requires_search("tell me about chapter 2", [_document()])

        assert _sent_messages(chain)[0].content == RAG_SEARCH_CLASSIFIER_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_the_query_and_every_document_name_reach_the_model(self) -> None:
        chain = _chain_deciding(True)

        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]):
            await _classifier_with(chain).requires_search(
                "summarise the intro", [_document(1, "textbook.pdf"), _document(2, "notes.pdf")]
            )

        turn = str(_sent_messages(chain)[-1].content)
        assert "summarise the intro" in turn
        assert "textbook.pdf" in turn
        assert "notes.pdf" in turn

    @pytest.mark.asyncio
    async def test_section_headings_are_listed_as_paths(self) -> None:
        """A heading's chapter, section and subsection are one path, so the model can see how
        deep the match would be rather than three unrelated words."""
        chain = _chain_deciding(True)
        headings = [_section("Chapter 1", "Cells", "Mitochondria"), _section("Chapter 2", None, None)]

        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=headings):
            await _classifier_with(chain).requires_search("what powers a cell", [_document()])

        turn = str(_sent_messages(chain)[-1].content)
        assert "Chapter 1 / Cells / Mitochondria" in turn
        assert "Chapter 2" in turn


class TestGatheringDocumentStructure:
    """Headings are read per document, and a document that cannot be read is not fatal."""

    @pytest.mark.asyncio
    async def test_every_document_is_looked_up(self) -> None:
        chain = _chain_deciding(True)

        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]) as mock_structure:
            await _classifier_with(chain).requires_search("q", [_document(1), _document(7)])

        assert [call.kwargs["document_id"] for call in mock_structure.await_args_list] == [1, 7]

    @pytest.mark.asyncio
    async def test_a_document_with_no_id_is_skipped(self) -> None:
        """An unsaved document has no id to look up and nothing to retrieve from."""
        chain = _chain_deciding(True)
        unsaved = Document(user_id=1, name="draft.pdf", status=DocumentStatus.READY)

        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]) as mock_structure:
            await _classifier_with(chain).requires_search("q", [unsaved, _document(3)])

        assert [call.kwargs["document_id"] for call in mock_structure.await_args_list] == [3]

    @pytest.mark.asyncio
    async def test_a_failed_lookup_leaves_the_document_named_but_headingless(self) -> None:
        """One unreadable document must not cost the others their headings, or the turn its
        judgement — the model can still decide from the names."""
        chain = _chain_deciding(True)

        with patch(_STRUCTURE, new_callable=AsyncMock, side_effect=[OSError("gone"), [_section("Chapter 9")]]):
            await _classifier_with(chain).requires_search("q", [_document(1, "broken.pdf"), _document(2, "ok.pdf")])

        turn = str(_sent_messages(chain)[-1].content)
        assert "broken.pdf" in turn
        assert "Chapter 9" in turn

    @pytest.mark.asyncio
    async def test_a_failed_lookup_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        chain = _chain_deciding(True)

        with (
            caplog.at_level(logging.WARNING, logger=_LOGGER),
            patch(_STRUCTURE, new_callable=AsyncMock, side_effect=OSError("gone")),
        ):
            await _classifier_with(chain).requires_search("q", [_document(1)])

        assert "1" in caplog.text


class TestTheBooleanCallersActOn:
    """`requires_search` unwraps the verdict so the route acts on one boolean."""

    @pytest.mark.asyncio
    async def test_a_search_is_required_when_the_model_says_so(self) -> None:
        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]):
            assert await _classifier_with(_chain_deciding(True)).requires_search("chapter 2?", [_document()]) is True

    @pytest.mark.asyncio
    async def test_a_declined_search_comes_back_false(self) -> None:
        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]):
            assert await _classifier_with(_chain_deciding(False)).requires_search("thanks!", [_document()]) is False


class TestDecliningIsLogged:
    """A skipped search reaches the client as a bare event, so the log holds the reasoning."""

    @pytest.mark.asyncio
    async def test_the_reason_the_model_gave_is_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        chain = _chain_deciding(False, "casual conversation")

        with (
            caplog.at_level(logging.INFO, logger=_LOGGER),
            patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]),
        ):
            await _classifier_with(chain).requires_search("thanks!", [_document()])

        assert "casual conversation" in caplog.text

    @pytest.mark.asyncio
    async def test_the_conversation_uuid_ties_the_skip_to_a_thread(self, caplog: pytest.LogCaptureFixture) -> None:
        conversation_uuid = uuid4()

        with (
            caplog.at_level(logging.INFO, logger=_LOGGER),
            patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]),
        ):
            await _classifier_with(_chain_deciding(False)).requires_search("hi", [_document()], conversation_uuid)

        assert str(conversation_uuid) in caplog.text

    @pytest.mark.asyncio
    async def test_a_required_search_logs_nothing(self, caplog: pytest.LogCaptureFixture) -> None:
        with (
            caplog.at_level(logging.INFO, logger=_LOGGER),
            patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]),
        ):
            await _classifier_with(_chain_deciding(True)).requires_search("chapter 2?", [_document()])

        assert caplog.text == ""


class TestFailureTranslation:
    """Unlike scope, a failed retrieval decision is fatal to the turn: the route persists an
    error and tells the user, rather than guessing at retrieval."""

    @pytest.mark.asyncio
    async def test_a_failed_model_call_becomes_a_rag_search_error(self) -> None:
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=LangChainException("provider is down"))

        with patch(_STRUCTURE, new_callable=AsyncMock, return_value=[]), pytest.raises(RAGSearchError):
            await _classifier_with(chain).requires_search("chapter 2?", [_document()])
