"""Layout plan shared by the PDF and PowerPoint renderers, so both split slides identically."""

import math
from dataclasses import dataclass
from typing import Literal

from app.document_generation.brand import Brand
from app.schemas.tools import PresentationContent

SLIDE_W, SLIDE_H = 10.0, 7.5  # inches (4:3, like the brand's deck)
BAR = (0.5, 0.28, 9.0, 1.07)  # title bar x, y, w, h
BODY = (0.6, 1.65, 8.8, 4.95)  # full-width body area
BODY_WITH_IMAGE_W = 5.55  # body width when an illustration sits on the right
IMAGE_BOX = (6.4, 1.8, 3.1, 3.1)  # square illustration x, y, w, h
INDENT_IN = 0.45
MAX_TITLE_CHARS = 110
FONT_SIZES = (26, 24, 22, 20)  # body sizes tried from largest to smallest
CHAR_W = 0.52  # average Calibri/Carlito glyph width as a fraction of the font size (conservative)
LOGO_TOP = 6.85  # the footer logo starts here; body must end above


def parse_emphasis(text: str) -> list[tuple[str, bool]]:
    """'a **b** c' -> [('a ', False), ('b', True), (' c', False)]. Unbalanced markers are dropped."""
    if text.count("**") % 2:
        text = text.replace("**", "")
    return [(p, i % 2 == 1) for i, p in enumerate(text.split("**")) if p]


def plain(text: str) -> str:
    return "".join(p for p, _ in parse_emphasis(text))


def estimate_height_pt(bullets: list[str], size: int, width_in: float = BODY[2]) -> float:
    chars_per_line = (width_in - INDENT_IN) * 72 / (size * CHAR_W)
    lines = sum(max(1, math.ceil(len(plain(b)) / chars_per_line)) for b in bullets)
    return lines * size * 1.2 + max(0, len(bullets) - 1) * size * 0.7


def best_size(bullets: list[str], width_in: float = BODY[2]) -> int | None:
    for size in FONT_SIZES:
        if estimate_height_pt(bullets, size, width_in) <= BODY[3] * 72:
            return size
    return None


def paginate(bullets: list[str], width_in: float = BODY[2]) -> list[list[str]]:
    """Split bullets over several slides rather than shrinking text below the smallest size."""
    pages: list[list[str]] = []
    current: list[str] = []
    for b in bullets:
        if current and best_size([*current, b], width_in) is None:
            pages.append(current)
            current = []
        current.append(b)
    if current:
        pages.append(current)
    return pages or [[]]


def title_size(title: str) -> int:
    n = len(title)
    return 32 if n <= 38 else 28 if n <= 54 else 24


def clip(title: str) -> str:
    title = " ".join(title.split())
    return title if len(title) <= MAX_TITLE_CHARS else title[: MAX_TITLE_CHARS - 1].rstrip() + "…"


def cover_title_size(text: str) -> int:
    return 28 if len(text) <= 50 else 24 if len(text) <= 90 else 20


@dataclass(frozen=True)
class PlannedSlide:
    kind: Literal["cover", "content", "closing"]
    number: int  # 1-based position in the deck
    title: str
    bullets: tuple[str, ...] = ()
    numbered: bool = False
    size: int = FONT_SIZES[-1]
    image_id: str | None = None
    notes: str = ""
    subtitle: str | None = None  # cover: "Préparée pour ..."


def plan_deck(
    content: PresentationContent, company: str | None, brand: Brand
) -> list[PlannedSlide]:
    plan = [
        PlannedSlide(
            "cover",
            1,
            clip(content.title),
            subtitle=f"Préparée pour {company}" if company else None,
        )
    ]
    for s in content.slides:
        bullets = [b.strip() for b in s.bullets if b.strip()]
        width = BODY_WITH_IMAGE_W if s.image_id else BODY[2]
        notes = s.speaker_notes or ""
        if s.suggested_visual:
            notes = f"{notes}\n\nVisuel suggéré : {s.suggested_visual}".strip()
        pages = paginate(bullets, width)
        if s.image_id and len(pages) > 1:
            # The image is narrower than the page: re-paginate the tail at full width.
            first, rest = pages[0], [b for p in pages[1:] for b in p]
            pages = [first, *paginate(rest, BODY[2])]
        for i, page in enumerate(pages):
            w = width if i == 0 else BODY[2]
            plan.append(
                PlannedSlide(
                    "content",
                    len(plan) + 1,
                    clip(s.title if i == 0 else f"{s.title} (suite)"),
                    tuple(page),
                    s.numbered,
                    best_size(page, w) or FONT_SIZES[-1],
                    s.image_id if i == 0 else None,
                    notes if i == 0 else "",
                )
            )
    plan.append(PlannedSlide("closing", len(plan) + 1, brand.closing_title))
    return plan
