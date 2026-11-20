import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.deps import Runtime, get_runtime
from app.core.config import Settings, get_settings
from app.integrations.llm import LLMError
from app.knowledge_base.extract import ExtractionError
from app.knowledge_base.service import DocumentInfo, DuplicateDocumentError, KnowledgeService

router = APIRouter(prefix="/documents")

_LLM_STATUS = {"rate_limit": 429, "timeout": 504, "auth": 503, "unavailable": 503}


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    kind: str
    size_bytes: int
    chunk_count: int
    created_at: str

    @classmethod
    def of(cls, d: DocumentInfo) -> "DocumentOut":
        return cls(**{**d.__dict__, "created_at": d.created_at.isoformat()})


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=100_000)


def _kb(rt: Runtime) -> KnowledgeService:
    if rt.knowledge is None:
        raise HTTPException(503, "La base de connaissances n'est pas configurée (DATABASE_URL).")
    return rt.knowledge


async def _guard(coro):  # type: ignore[no-untyped-def]
    try:
        return await coro
    except ExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
    except DuplicateDocumentError as exc:
        raise HTTPException(409, "Ce document a déjà été ajouté.") from exc
    except LLMError as exc:
        raise HTTPException(_LLM_STATUS.get(exc.kind, 502), str(exc)) from exc


@router.get("", response_model=list[DocumentOut])
async def list_documents(rt: Runtime = Depends(get_runtime)) -> list[DocumentOut]:
    return [DocumentOut.of(d) for d in await _kb(rt).list_documents()]


@router.post("", response_model=DocumentOut, status_code=201)
async def upload(
    file: UploadFile,
    rt: Runtime = Depends(get_runtime),
    settings: Settings = Depends(get_settings),
) -> DocumentOut:
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)  # never buffer more than limit + 1 byte
    if len(data) > limit:
        raise HTTPException(413, f"Fichier trop volumineux (max {settings.max_upload_mb} Mo).")
    filename = (file.filename or "document").replace("\\", "/").rsplit("/", 1)[-1][:255]
    return DocumentOut.of(await _guard(_kb(rt).ingest_file(filename, data)))


@router.post("/note", response_model=DocumentOut, status_code=201)
async def add_note(body: NoteIn, rt: Runtime = Depends(get_runtime)) -> DocumentOut:
    return DocumentOut.of(await _guard(_kb(rt).ingest_note(body.title, body.text)))


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: uuid.UUID, rt: Runtime = Depends(get_runtime)) -> None:
    if not await _kb(rt).delete_document(doc_id):
        raise HTTPException(404, "Document introuvable")
