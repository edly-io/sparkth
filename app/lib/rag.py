"""Public API for the RAG library.

All plugins and external modules import RAG functionality from here.
"""

from app.rag.exceptions import DocumentNotFoundError as DocumentNotFoundError
from app.rag.exceptions import RAGNotReadyError as RAGNotReadyError
from app.rag.exceptions import RAGRetrievalError as RAGRetrievalError
from app.rag.exceptions import ScannedPDFError as ScannedPDFError
from app.rag.exceptions import UnsupportedFileTypeError as UnsupportedFileTypeError
from app.rag.ingestion import ingest_document as ingest_document
from app.rag.retrieval import agentic_retrieve_context as agentic_retrieve_context
from app.rag.store import copy_document_chunk_links as copy_document_chunk_links
from app.rag.types import RetrievedChunk as RetrievedChunk
