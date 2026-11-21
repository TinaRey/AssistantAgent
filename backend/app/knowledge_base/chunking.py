import re
from dataclasses import dataclass

from app.knowledge_base.extract import Section

CHUNK_SIZE = 1000  # characters (~250 tokens): small enough to stay precise
OVERLAP = 150


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    page: int | None


def split_text(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks += _hard_split(para, size, overlap)
        elif not buf:
            buf = para
        elif len(buf) + len(para) + 2 <= size:
            buf += "\n\n" + para
        else:
            chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)
    return chunks


def _hard_split(text: str, size: int, overlap: int) -> list[str]:
    out: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind(" ", start + size // 2, end)
            end = cut if cut != -1 else end
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in out if c]


def chunk_sections(sections: list[Section]) -> list[ChunkDraft]:
    return [ChunkDraft(c, s.page) for s in sections for c in split_text(s.text)]
