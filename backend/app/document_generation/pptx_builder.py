"""Builds the editable Pantalelle .pptx from structured content.

The model only provides text. Layout, colors, fonts and logo are fixed here, following the brand's own
presentation. The slide split comes from `layout.plan_deck`, shared with the PDF renderer.
"""

import io
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.slide import Slide as PptxSlide
from pptx.util import Emu, Inches, Pt

from app.document_generation.brand import Brand, load_brand
from app.document_generation.layout import (
    BAR,
    BODY,
    BODY_WITH_IMAGE_W,
    IMAGE_BOX,
    INDENT_IN,
    SLIDE_H,
    SLIDE_W,
    PlannedSlide,
    best_size,
    clip,
    cover_title_size,
    estimate_height_pt,
    paginate,
    parse_emphasis,
    plan_deck,
    title_size,
)
from app.schemas.tools import PresentationContent

__all__ = [
    "BODY",
    "best_size",
    "build_pptx",
    "clip",
    "estimate_height_pt",
    "paginate",
    "parse_emphasis",
    "render_pptx",
]


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.upper())


def _run(paragraph, text: str, *, size: int, color: str, font: str, bold: bool = False) -> None:  # type: ignore[no-untyped-def]
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.name = font
    run.font.bold = bold
    run.font.color.rgb = rgb(color)


def _bullet(paragraph, brand: Brand, numbered: bool) -> None:  # type: ignore[no-untyped-def]
    pPr = paragraph._p.get_or_add_pPr()
    pPr.set("marL", str(int(Inches(INDENT_IN))))
    pPr.set("indent", str(-int(Inches(INDENT_IN))))
    clr = OxmlElement("a:buClr")
    srgb = OxmlElement("a:srgbClr")
    srgb.set("val", brand.colors.red.upper() if numbered else brand.colors.text.upper())
    clr.append(srgb)
    pPr.append(clr)
    if numbered:
        num = OxmlElement("a:buAutoNum")
        num.set("type", "arabicPeriod")
        pPr.append(num)
    else:  # Wingdings 'ü' is the check mark used in the brand's own deck
        font = OxmlElement("a:buFont")
        font.set("typeface", "Wingdings")
        font.set("pitchFamily", "2")
        font.set("charset", "2")
        pPr.append(font)
        char = OxmlElement("a:buChar")
        char.set("char", "ü")
        pPr.append(char)


def _box(slide: PptxSlide, x: float, y: float, w: float, h: float, *, anchor=MSO_ANCHOR.TOP):  # type: ignore[no-untyped-def]
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    return tb, tf


def _title(slide: PptxSlide, text: str, brand: Brand) -> None:
    shape = slide.shapes.title
    assert shape is not None
    x, y, w, h = BAR
    shape.left, shape.top, shape.width, shape.height = Inches(x), Inches(y), Inches(w), Inches(h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(brand.colors.peach)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.2)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    _run(tf.paragraphs[0], text, size=title_size(text), color=brand.colors.red, font=brand.font)


def _logo(slide: PptxSlide, x: float, y: float, w: float, brand: Brand) -> None:
    if brand.logo_path.is_file():
        pic = slide.shapes.add_picture(str(brand.logo_path), Inches(x), Inches(y), width=Inches(w))
        pic._element.nvPicPr.cNvPr.set("descr", "Logo Pantalelle")  # alt text


def _footer(slide: PptxSlide, number: int, brand: Brand) -> None:
    _logo(slide, 7.3, 6.85, 1.6, brand)
    _, tf = _box(slide, 8.95, 7.0, 0.6, 0.3)
    tf.paragraphs[0].alignment = PP_ALIGN.RIGHT
    _run(tf.paragraphs[0], str(number), size=11, color=brand.colors.muted, font=brand.font)


def _cover(prs, p: PlannedSlide, brand: Brand) -> None:  # type: ignore[no-untyped-def]
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    k = 1000  # freeform coordinates in thousandths of an inch
    fb = slide.shapes.build_freeform(5630, 0, scale=Inches(1) / k)
    fb.add_line_segments([(10000, 0), (10000, 7500), (3750, 7500)], close=True)
    panel = fb.convert_to_shape()
    panel.fill.solid()
    panel.fill.fore_color.rgb = rgb(brand.colors.cover_panel)
    panel.line.fill.background()
    tree = slide.shapes._spTree
    tree.remove(panel._element)
    tree.insert(2, panel._element)  # behind everything

    _logo(slide, 2.95, 0.35, 4.1, brand)
    _, tf = _box(slide, 5.0, 2.75, 4.6, 0.45)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    _run(tf.paragraphs[0], brand.cover_tag, size=16, color=brand.colors.red, font=brand.mono_font)

    title = slide.shapes.title
    assert title is not None
    title.left, title.top, title.width, title.height = (
        Inches(5.0),
        Inches(3.3),
        Inches(4.6),
        Inches(2.1),
    )
    ttf = title.text_frame
    ttf.word_wrap = True
    ttf.vertical_anchor = MSO_ANCHOR.MIDDLE
    ttf.paragraphs[0].alignment = PP_ALIGN.CENTER
    _run(
        ttf.paragraphs[0],
        p.title,
        size=cover_title_size(p.title),
        color=brand.colors.text,
        font=brand.font,
        bold=True,
    )
    if p.subtitle:
        _, tf = _box(slide, 5.0, 5.5, 4.6, 0.5)
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        _run(tf.paragraphs[0], p.subtitle, size=18, color=brand.colors.red, font=brand.font)
    if brand.contact.name:
        _, tf = _box(slide, 0.6, 6.75, 4.0, 0.4)
        _run(
            tf.paragraphs[0], brand.contact.name, size=16, color=brand.colors.text, font=brand.font
        )


def _content(prs, p: PlannedSlide, brand: Brand, images: dict[str, bytes]) -> None:  # type: ignore[no-untyped-def]
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    _title(slide, p.title, brand)
    image = images.get(p.image_id) if p.image_id else None
    x, y, w, h = BODY
    _, tf = _box(slide, x, y, BODY_WITH_IMAGE_W if image else w, h)
    for i, text in enumerate(p.bullets):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_after = Pt(p.size * 0.7)
        _bullet(para, brand, p.numbered)
        for part, emphasized in parse_emphasis(text):
            _run(
                para,
                part,
                size=p.size,
                font=brand.font,
                color=brand.colors.red if emphasized else brand.colors.text,
            )
    if image:
        ix, iy, iw, ih = IMAGE_BOX
        pic = slide.shapes.add_picture(
            io.BytesIO(image), Inches(ix), Inches(iy), Inches(iw), Inches(ih)
        )
        pic.auto_shape_type = MSO_SHAPE.ROUNDED_RECTANGLE  # rounded frame like the brand's photos
        pic._element.nvPicPr.cNvPr.set("descr", f"Illustration : {p.title}")
    _footer(slide, p.number, brand)
    if p.notes:
        slide.notes_slide.notes_text_frame.text = p.notes  # type: ignore[union-attr]


def _closing(prs, p: PlannedSlide, brand: Brand) -> None:  # type: ignore[no-untyped-def]
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    _title(slide, p.title, brand)
    _, tf = _box(slide, 0.9, 2.2, 8.0, 4.0)
    first = True
    for line in brand.closing_lines:
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.space_after = Pt(10)
        _run(para, line, size=22, color=brand.colors.text, font=brand.font)
    c = brand.contact
    for i, line in enumerate(x for x in (c.name, c.role, c.phone, c.email) if x):
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        if i == 0:
            para.space_before = Pt(28)
        _run(para, line, size=20, color=brand.colors.text, font=brand.font, bold=True)
    _footer(slide, p.number, brand)


def render_pptx(
    content: PresentationContent,
    company: str | None = None,
    brand: Brand | None = None,
    images: dict[str, bytes] | None = None,
) -> bytes:
    brand = brand or load_brand()
    images = images or {}
    prs = Presentation()  # default template is already 4:3 (10 x 7.5 in)
    prs.slide_width, prs.slide_height = Emu(Inches(SLIDE_W)), Emu(Inches(SLIDE_H))
    for p in plan_deck(content, company, brand):
        if p.kind == "cover":
            _cover(prs, p, brand)
        elif p.kind == "content":
            _content(prs, p, brand, images)
        else:
            _closing(prs, p, brand)
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def build_pptx(
    content: PresentationContent,
    path: Path,
    company: str | None = None,
    brand: Brand | None = None,
    images: dict[str, bytes] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_pptx(content, company, brand, images))
