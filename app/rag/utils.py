"""RAG utility functions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.db import session_scope
from app.lib.documents import Document
from app.rag.models import DocumentChunk, DocumentChunkLink
from app.rag.types import DocumentSection


def get_asset(file_name: str, file_extension: str) -> str | dict[str, Any]:
    """Read a file from app/rag/assets and return its contents.

    Returns a str for .txt files and a dict for .json files.
    """
    ext = file_extension.lstrip(".")
    path = Path(__file__).parent / "assets" / f"{file_name}.{ext}"

    with path.open() as f:
        if ext == "txt":
            content = f.read()
        elif ext == "json":
            content = json.load(f)
        else:
            raise ValueError(f"Unsupported asset extension: {file_extension}")

    return content


async def _fetch_document(session: AsyncSession, user_id: int, document_id: int) -> Document | None:
    """Return the Document if it exists and belongs to user_id."""
    result = await session.exec(
        select(Document).where(
            col(Document.user_id) == user_id,
            col(Document.id) == document_id,
        )
    )
    return result.first()


async def get_rag_ingested_document_structure(user_id: int, document_id: int) -> list[DocumentSection]:
    """Return ordered section metadata generated from the ingested RAG chunks.

    Returns an empty list when the document does not exist for the user.
    """
    async with session_scope() as session:
        document = await _fetch_document(session, user_id, document_id)
        if document is None:
            return []

        result = await session.exec(
            select(
                col(DocumentChunk.chapter),
                col(DocumentChunk.section),
                col(DocumentChunk.subsection),
                func.count().label("chunk_count"),
            )
            .join(DocumentChunkLink, col(DocumentChunk.id) == col(DocumentChunkLink.chunk_id))
            .where(
                col(DocumentChunk.user_id) == user_id,
                col(DocumentChunkLink.document_id) == document_id,
            )
            .group_by(
                col(DocumentChunk.chapter),
                col(DocumentChunk.section),
                col(DocumentChunk.subsection),
            )
            .order_by(func.min(col(DocumentChunk.id)))
        )

        return [
            DocumentSection(
                source_name=document.name,
                chapter=row[0],
                section=row[1],
                subsection=row[2],
                chunk_count=row[3],
                position_index=index,
            )
            for index, row in enumerate(result.all())
        ]
