"""Turn an uploaded file into plain text sections. Validates type by extension AND content."""

import io
import zipfile
from dataclasses import dataclass

ALLOWED = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md"}


class ExtractionError(Exception):
    """User-presentable: the file cannot be used."""


@dataclass(frozen=True)
class Section:
    text: str
    page: int | None = None


def kind_for(filename: str) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    kind = ALLOWED.get(ext)
    if kind is None:
        raise ExtractionError("Format non pris en charge. Utilisez PDF, DOCX, TXT ou MD.")
    return kind


def extract(kind: str, data: bytes) -> list[Section]:
    if not data:
        raise ExtractionError("Le fichier est vide.")
    try:
        sections = {"pdf": _pdf, "docx": _docx, "txt": _text, "md": _text}[kind](data)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError("Impossible de lire ce fichier (corrompu ou protégé).") from exc
    sections = [s for s in sections if s.text.strip()]
    if not sections:
        raise ExtractionError(
            "Aucun texte trouvé. Si c'est un PDF scanné (images), il faut une version avec du texte."
        )
    return sections


def _pdf(data: bytes) -> list[Section]:
    if not data.startswith(b"%PDF"):
        raise ExtractionError("Ce fichier n'est pas un PDF valide.")
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ExtractionError("Ce PDF est protégé par un mot de passe.")
    return [Section(page.extract_text() or "", i + 1) for i, page in enumerate(reader.pages)]


def _docx(data: bytes) -> list[Section]:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise ExtractionError("Ce fichier n'est pas un DOCX valide.")
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        parts += [" | ".join(c.text for c in row.cells) for row in table.rows]
    return [Section("\n\n".join(parts))]


def _text(data: bytes) -> list[Section]:
    if b"\x00" in data:
        raise ExtractionError("Ce fichier n'est pas un fichier texte.")
    try:
        return [Section(data.decode("utf-8-sig"))]
    except UnicodeDecodeError:
        return [Section(data.decode("latin-1"))]
