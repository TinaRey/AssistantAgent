import io

import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient

from app.api.deps import build_runtime, get_runtime
from app.core.security import require_auth
from app.knowledge_base.chunking import split_text
from app.knowledge_base.extract import ExtractionError, extract, kind_for
from app.knowledge_base.service import DuplicateDocumentError
from app.main import app
from tests.conftest import FakeLLM


# ---- pure unit tests (no DB) ----------------------------------------------
def test_chunking_respects_size_and_keeps_all_text() -> None:
    para = "Mot " * 120  # 480 chars
    chunks = split_text("\n\n".join([para] * 5), size=1000, overlap=100)
    assert all(len(c) <= 1000 for c in chunks) and len(chunks) >= 3
    long = "abc " * 1000
    assert all(len(c) <= 1000 for c in split_text(long, size=1000, overlap=100))
    assert split_text("   \n\n  ") == []


def test_extract_txt_docx_and_rejections() -> None:
    assert extract("txt", "Bonjour é".encode())[0].text == "Bonjour é"
    assert extract("txt", "caf\xe9".encode("latin-1"))[0].text == "café"
    buf = io.BytesIO()
    d = DocxDocument()
    d.add_paragraph("Histoire de la marque")
    d.save(buf)
    assert "Histoire" in extract("docx", buf.getvalue())[0].text
    for kind, data in [
        ("pdf", b"not a pdf"),
        ("docx", b"not zip"),
        ("txt", b"a\x00b"),
        ("txt", b""),
    ]:
        with pytest.raises(ExtractionError):
            extract(kind, data)
    with pytest.raises(ExtractionError):
        kind_for("virus.exe")
    assert kind_for("Deck.PDF") == "pdf"


def test_extract_pdf_pages() -> None:
    from pypdf import PdfWriter

    w = PdfWriter()
    w.add_blank_page(200, 200)
    buf = io.BytesIO()
    w.write(buf)
    with pytest.raises(ExtractionError, match="Aucun texte"):  # blank/scanned pdf
        extract("pdf", buf.getvalue())


# ---- integration tests against the local pgvector database -----------------
async def test_ingest_search_returns_relevant_passage_with_source(kb) -> None:  # type: ignore[no-untyped-def]
    await kb.ingest_file(
        "histoire.txt", "Pantalelle est née en 2020 à Lyon, atelier de lampes.".encode()
    )
    await kb.ingest_file("ton.md", b"Notre ton est chaleureux, simple et sans jargon.")
    res = await kb.search("quel est le ton de la marque chaleureux", 2)
    assert res[0].source == "ton.md" and res[0].score > res[1].score


async def test_duplicates_listing_and_delete_cascade(kb) -> None:  # type: ignore[no-untyped-def]
    info = await kb.ingest_note("Réunion", "Positionnement premium et local.")
    assert info.filename == "Réunion (note)" and info.chunk_count == 1
    with pytest.raises(DuplicateDocumentError):
        await kb.ingest_note("Autre titre", "Positionnement premium et local.")
    assert [d.filename for d in await kb.list_documents()] == ["Réunion (note)"]
    assert await kb.delete_document(info.id) is True
    assert await kb.search("premium", 3) == []  # chunks gone with the document
    assert await kb.delete_document(info.id) is False


async def test_retrieve_knowledge_tool_uses_the_store(kb, make_runtime) -> None:  # type: ignore[no-untyped-def]
    from app.schemas.tools import RetrieveKnowledgeInput
    from app.tools.retrieve_knowledge import retrieve_knowledge

    await kb.ingest_note("Valeurs", "Artisanat durable et fabrication locale.")
    *_, ctx = make_runtime(FakeLLM())
    ctx = type(ctx)(
        llm=ctx.llm,
        search=ctx.search,
        knowledge=kb,
        presentations=ctx.presentations,
        images=ctx.images,
        templates=ctx.templates,
    )
    out = await retrieve_knowledge(RetrieveKnowledgeInput(query="artisanat durable"), ctx)
    assert out.passages[0].source == "Valeurs (note)" and out.note is None


# ---- HTTP layer -------------------------------------------------------------
@pytest.fixture
def client(kb, tmp_path):  # type: ignore[no-untyped-def]
    rt = build_runtime(FakeLLM(), knowledge=kb)
    app.dependency_overrides[get_runtime] = lambda: rt
    app.dependency_overrides[require_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_upload_list_delete_flow(client) -> None:  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/documents", files={"file": ("notes.txt", b"Notre histoire commence ici.")}
    )
    assert r.status_code == 201 and r.json()["chunk_count"] == 1
    doc_id = r.json()["id"]
    assert (
        client.post(
            "/api/documents", files={"file": ("n.txt", b"Notre histoire commence ici.")}
        ).status_code
        == 409
    )
    assert len(client.get("/api/documents").json()) == 1
    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert client.delete(f"/api/documents/{doc_id}").status_code == 404


def test_upload_validation(client) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/api/documents", files={"file": ("x.exe", b"MZ")}).status_code == 422
    assert client.post("/api/documents", files={"file": ("fake.pdf", b"hello")}).status_code == 422
    assert client.post("/api/documents", files={"file": ("e.txt", b"")}).status_code == 422
    big = b"a" * (10 * 1024 * 1024 + 1)
    assert client.post("/api/documents", files={"file": ("big.txt", big)}).status_code == 413
    r = client.post(
        "/api/documents/note", json={"title": "Réunion", "text": "Positionnement haut de gamme."}
    )
    assert r.status_code == 201


def test_documents_503_without_database(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import Settings

    monkeypatch.setattr(
        "app.api.deps.get_settings", lambda: Settings(database_url="", _env_file=None)
    )
    rt = build_runtime(FakeLLM())
    assert rt.knowledge is None
    app.dependency_overrides[get_runtime] = lambda: rt
    app.dependency_overrides[require_auth] = lambda: None
    try:
        assert TestClient(app).get("/api/documents").status_code == 503
    finally:
        app.dependency_overrides.clear()
