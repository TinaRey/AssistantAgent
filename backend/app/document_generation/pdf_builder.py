"""Renders the Pantalelle presentation as a PDF (same plan and geometry as the .pptx)."""

import io
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from app.document_generation.brand import ASSETS_DIR, Brand, load_brand
from app.document_generation.layout import (
    BAR,
    BODY,
    BODY_WITH_IMAGE_W,
    IMAGE_BOX,
    INDENT_IN,
    SLIDE_H,
    SLIDE_W,
    PlannedSlide,
    cover_title_size,
    parse_emphasis,
    plan_deck,
    title_size,
)
from app.schemas.tools import PresentationContent

PT = 72.0  # points per inch
FONTS_DIR = ASSETS_DIR.parent / "fonts"


@lru_cache
def _fonts() -> tuple[str, str]:
    """Carlito (metric-compatible with Calibri, OFL) if bundled, else the built-in Helvetica."""
    try:
        pdfmetrics.registerFont(TTFont("Carlito", str(FONTS_DIR / "Carlito-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Carlito-Bold", str(FONTS_DIR / "Carlito-Bold.ttf")))
        return "Carlito", "Carlito-Bold"
    except (OSError, TTFError):  # missing/corrupt font file: keep working with a standard font
        return "Helvetica", "Helvetica-Bold"


def _y(top_in: float) -> float:
    return (SLIDE_H - top_in) * PT


def _para(
    text: str, size: float, color: str, font: str, align: int = 0, left_indent: float = 0.0
) -> Paragraph:
    style = ParagraphStyle(
        "p",
        fontName=font,
        fontSize=size,
        leading=size * 1.2,
        textColor=HexColor("#" + color),
        alignment=align,
        leftIndent=left_indent,
    )
    return Paragraph(text, style)


def _rich(text: str, normal: str, accent: str) -> str:
    out = []
    for part, emphasized in parse_emphasis(text):
        part = escape(part)
        out.append(f'<font color="#{accent}">{part}</font>' if emphasized else part)
    return "".join(out) or escape(normal)


def _draw_text_block(
    c: Canvas,
    para: Paragraph,
    x_in: float,
    top_in: float,
    w_in: float,
    h_in: float,
    *,
    middle: bool,
) -> float:
    _, h = para.wrap(w_in * PT, h_in * PT)
    offset = (h_in * PT - h) / 2 if middle else 0
    para.drawOn(c, x_in * PT, _y(top_in) - offset - h)
    return h


def _check_mark(c: Canvas, x: float, baseline: float, size: float, color: str) -> None:
    """Vector check mark: Carlito has no check glyph and built-in symbol fonts render unevenly."""
    c.saveState()
    c.setStrokeColor(HexColor("#" + color))
    c.setLineWidth(size * 0.07)
    c.setLineCap(1)
    c.setLineJoin(1)
    path = c.beginPath()
    path.moveTo(x + size * 0.04, baseline + size * 0.30)
    path.lineTo(x + size * 0.20, baseline + size * 0.08)
    path.lineTo(x + size * 0.50, baseline + size * 0.62)
    c.drawPath(path, stroke=1, fill=0)
    c.restoreState()


def _logo(c: Canvas, x: float, y: float, w: float, brand: Brand) -> None:
    if brand.logo_path.is_file():
        img = ImageReader(str(brand.logo_path))
        iw, ih = img.getSize()
        c.drawImage(img, x * PT, _y(y) - w * PT * ih / iw, w * PT, w * PT * ih / iw, mask="auto")


def _footer(c: Canvas, number: int, brand: Brand, font: str) -> None:
    _logo(c, 7.3, 6.85, 1.6, brand)
    c.setFont(font, 11)
    c.setFillColor(HexColor("#" + brand.colors.muted))
    c.drawRightString(9.55 * PT, _y(7.22), str(number))


def _title_bar(c: Canvas, text: str, brand: Brand, font: str) -> None:
    x, y, w, h = BAR
    c.setFillColor(HexColor("#" + brand.colors.peach))
    c.rect(x * PT, _y(y + h), w * PT, h * PT, stroke=0, fill=1)
    para = _para(escape(text), title_size(text), brand.colors.red, font, TA_CENTER)
    _draw_text_block(c, para, x + 0.2, y, w - 0.4, h, middle=True)


def _cover(c: Canvas, p: PlannedSlide, brand: Brand, regular: str, bold: str) -> None:
    c.setFillColor(HexColor("#" + brand.colors.cover_panel))
    path = c.beginPath()
    path.moveTo(5.63 * PT, _y(0))
    path.lineTo(10 * PT, _y(0))
    path.lineTo(10 * PT, _y(7.5))
    path.lineTo(3.75 * PT, _y(7.5))
    path.close()
    c.drawPath(path, stroke=0, fill=1)
    _logo(c, 2.95, 0.35, 4.1, brand)

    c.setFont("Courier-Bold", 16)
    c.setFillColor(HexColor("#" + brand.colors.red))
    c.drawCentredString(7.3 * PT, _y(3.05), brand.cover_tag)
    para = _para(escape(p.title), cover_title_size(p.title), brand.colors.text, bold, TA_CENTER)
    _draw_text_block(c, para, 5.0, 3.3, 4.6, 2.1, middle=True)
    if p.subtitle:
        sub = _para(escape(p.subtitle), 18, brand.colors.red, regular, TA_CENTER)
        _draw_text_block(c, sub, 5.0, 5.5, 4.6, 0.5, middle=False)
    if brand.contact.name:
        c.setFont(regular, 16)
        c.setFillColor(HexColor("#" + brand.colors.text))
        c.drawString(0.65 * PT, _y(7.05), brand.contact.name)


def _content(
    c: Canvas, p: PlannedSlide, brand: Brand, regular: str, bold: str, images: dict[str, bytes]
) -> None:
    _title_bar(c, p.title, brand, regular)
    image = images.get(p.image_id) if p.image_id else None
    x, y, w, h = BODY
    width_in = BODY_WITH_IMAGE_W if image else w
    top = y
    for i, text in enumerate(p.bullets):
        para = _para(
            _rich(text, text, brand.colors.red),
            p.size,
            brand.colors.text,
            regular,
            left_indent=INDENT_IN * PT,
        )
        _, ph = para.wrap(width_in * PT, h * PT)
        baseline = _y(top) - p.size  # first line baseline of this bullet
        if p.numbered:
            c.setFont(regular, p.size)
            c.setFillColor(HexColor("#" + brand.colors.red))
            c.drawString(x * PT, baseline, f"{i + 1}.")
        else:
            _check_mark(c, x * PT, baseline, p.size, brand.colors.text)
        para.drawOn(c, x * PT, _y(top) - ph)
        top += (ph + p.size * 0.7) / PT
    if image:
        ix, iy, iw, ih = IMAGE_BOX
        c.saveState()
        clip = c.beginPath()
        clip.roundRect(ix * PT, _y(iy + ih), iw * PT, ih * PT, 0.25 * PT)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(ImageReader(io.BytesIO(image)), ix * PT, _y(iy + ih), iw * PT, ih * PT)
        c.restoreState()
    _footer(c, p.number, brand, regular)


def _closing(c: Canvas, p: PlannedSlide, brand: Brand, regular: str, bold: str) -> None:
    _title_bar(c, p.title, brand, regular)
    top = 2.2
    for line in brand.closing_lines:
        para = _para(escape(line), 22, brand.colors.text, regular)
        top += (_draw_text_block(c, para, 0.9, top, 8.0, 1.0, middle=False) + 10) / PT
    top += 28 / PT
    k = brand.contact
    for line in (x for x in (k.name, k.role, k.phone, k.email) if x):
        para = _para(escape(line), 20, brand.colors.text, bold)
        top += (_draw_text_block(c, para, 0.9, top, 8.0, 1.0, middle=False) + 4) / PT
    _footer(c, p.number, brand, regular)


def render_pdf(
    content: PresentationContent,
    company: str | None = None,
    brand: Brand | None = None,
    images: dict[str, bytes] | None = None,
) -> bytes:
    brand = brand or load_brand()
    images = images or {}
    regular, bold = _fonts()
    out = io.BytesIO()
    c = Canvas(out, pagesize=(SLIDE_W * PT, SLIDE_H * PT))
    c.setTitle(content.title)
    c.setAuthor("Pantalelle")
    for p in plan_deck(content, company, brand):
        if p.kind == "cover":
            _cover(c, p, brand, regular, bold)
        elif p.kind == "content":
            _content(c, p, brand, regular, bold, images)
        else:
            _closing(c, p, brand, regular, bold)
        c.showPage()
    c.save()
    return out.getvalue()


def build_pdf(
    content: PresentationContent,
    path: Path,
    company: str | None = None,
    brand: Brand | None = None,
    images: dict[str, bytes] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_pdf(content, company, brand, images))
