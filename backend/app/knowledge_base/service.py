"""Knowledge base: ingestion, listing, deletion and semantic search over Postgres + pgvector."""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.integrations.embeddings import Embedder
from app.integrations.templates import TemplatePdf
from app.knowledge_base.chunking import chunk_sections
from app.knowledge_base.extract import ExtractionError, Section, extract, kind_for
from app.models import Chunk, Document
from app.schemas.tools import Passage


class DuplicateDocumentError(Exception):
    pass


@dataclass(frozen=True)
class DocumentInfo:
    id: uuid.UUID
    filename: str
    kind: str
    size_bytes: int
    chunk_count: int
    created_at: datetime


def source_label(filename: str, page: int | None) -> str:
    return f"{filename}, p. {page}" if page else filename


class KnowledgeService:
    def __init__(self, sessions: sessionmaker[Session], embedder: Embedder) -> None:
        self._sessions, self._embedder = sessions, embedder

    # ---- ingestion -------------------------------------------------------
    async def ingest_file(self, filename: str, data: bytes) -> DocumentInfo:
        kind = kind_for(filename)
        sections = await asyncio.to_thread(extract, kind, data)
        return await self._ingest(filename, kind, data, sections)

    async def ingest_note(self, title: str, text: str) -> DocumentInfo:
        data = text.encode("utf-8")
        if not text.strip():
            raise ExtractionError("La note est vide.")
        return await self._ingest(f"{title.strip()} (note)", "note", data, [Section(text)])

    async def _ingest(
        self, filename: str, kind: str, data: bytes, sections: list[Section]
    ) -> DocumentInfo:
        digest = hashlib.sha256(data).hexdigest()
        if await asyncio.to_thread(self._exists, digest):
            raise DuplicateDocumentError(filename)
        drafts = chunk_sections(sections)
        vectors = await self._embedder.embed([d.text for d in drafts])
        return await asyncio.to_thread(self._save, filename, kind, data, digest, drafts, vectors)

    def _exists(self, digest: str) -> bool:
        with self._sessions() as s:
            return s.scalar(select(Document.id).where(Document.sha256 == digest)) is not None

    def _save(self, filename, kind, data, digest, drafts, vectors) -> DocumentInfo:  # type: ignore[no-untyped-def]
        doc = Document(filename=filename, kind=kind, size_bytes=len(data), sha256=digest, data=data)
        doc.chunks = [
            Chunk(position=i, page=d.page, text=d.text, embedding=v)
            for i, (d, v) in enumerate(zip(drafts, vectors, strict=True))
        ]
        with self._sessions() as s:
            s.add(doc)
            try:
                s.commit()
            except IntegrityError as exc:  # concurrent duplicate upload
                s.rollback()
                raise DuplicateDocumentError(filename) from exc
            return DocumentInfo(
                doc.id, doc.filename, doc.kind, doc.size_bytes, len(drafts), doc.created_at
            )

    # ---- listing / deletion ---------------------------------------------
    async def list_documents(self) -> list[DocumentInfo]:
        return await asyncio.to_thread(self._list)

    def _list(self) -> list[DocumentInfo]:
        stmt = (
            select(Document, func.count(Chunk.id))
            .outerjoin(Chunk)
            .group_by(Document.id)
            .order_by(Document.created_at.desc())
        )
        with self._sessions() as s:
            return [
                DocumentInfo(d.id, d.filename, d.kind, d.size_bytes, n, d.created_at)
                for d, n in s.execute(stmt)
            ]

    async def delete_document(self, doc_id: uuid.UUID) -> bool:
        return await asyncio.to_thread(self._delete, doc_id)

    def _delete(self, doc_id: uuid.UUID) -> bool:
        with self._sessions() as s:
            result = s.execute(delete(Document).where(Document.id == doc_id))
            s.commit()
            return result.rowcount > 0

    # ---- templates (implements the TemplateSource protocol) --------------
    async def list_pdf_names(self) -> list[str]:
        def work() -> list[str]:
            with self._sessions() as s:
                return list(
                    s.scalars(
                        select(Document.filename)
                        .where(Document.kind == "pdf")
                        .order_by(Document.created_at.desc())
                    )
                )

        return await asyncio.to_thread(work)

    async def get_pdf(self, filename: str) -> TemplatePdf | None:
        def work() -> TemplatePdf | None:
            with self._sessions() as s:
                doc = s.scalar(
                    select(Document).where(Document.kind == "pdf", Document.filename == filename)
                )
                return TemplatePdf(doc.filename, doc.data) if doc else None

        return await asyncio.to_thread(work)

    # ---- retrieval (implements the KnowledgeStore protocol) -------------
    async def search(self, query: str, top_k: int) -> list[Passage]:
        [vec] = await self._embedder.embed([query])
        return await asyncio.to_thread(self._search, vec, top_k)

    def _search(self, vec: list[float], top_k: int) -> list[Passage]:
        distance = Chunk.embedding.cosine_distance(vec)
        stmt = (
            select(Chunk.text, Chunk.page, Document.filename, distance)
            .join(Document)
            .order_by(distance)
            .limit(top_k)
        )
        with self._sessions() as s:
            return [
                Passage(text=t, source=source_label(fn, pg), score=round(1 - float(dist), 4))
                for t, pg, fn, dist in s.execute(stmt)
            ]
