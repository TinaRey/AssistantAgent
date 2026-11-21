"""Template decks: PDF presentations uploaded to the knowledge base."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TemplatePdf:
    filename: str
    data: bytes


class TemplateSource(Protocol):
    async def list_pdf_names(self) -> list[str]: ...
    async def get_pdf(self, filename: str) -> TemplatePdf | None: ...


class EmptyTemplateSource:
    async def list_pdf_names(self) -> list[str]:
        return []

    async def get_pdf(self, filename: str) -> TemplatePdf | None:
        return None


def _tokens(text: str) -> set[str]:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return {t for t in re.split(r"[^a-z0-9]+", ascii_text) if t}


def match_template(query: str, names: list[str]) -> list[str]:
    """Names whose words contain all the words of the query ('presentation generale' finds
    'Pantalelle_presentation generale_French.pdf'). Exact (case-insensitive) match wins."""
    exact = [n for n in names if n.lower() == query.strip().lower()]
    if exact:
        return exact
    wanted = _tokens(query) - {"pdf"}
    if not wanted:
        return []
    return [n for n in names if wanted <= _tokens(n)]
