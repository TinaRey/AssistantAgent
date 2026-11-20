from pathlib import Path

from pptx import Presentation

from app.schemas.tools import PresentationContent


def build_pptx(content: PresentationContent, path: Path) -> None:
    """Fill a fixed layout from structured content. The LLM never controls visual layout.

    TODO: swap the default template for the Pantalelle .pptx template (fonts, colors, logo).
    """
    prs = Presentation()
    title_layout, body_layout = prs.slide_layouts[0], prs.slide_layouts[1]

    cover = prs.slides.add_slide(title_layout)
    cover.shapes.title.text = content.title  # type: ignore[union-attr]

    for slide in content.slides:
        s = prs.slides.add_slide(body_layout)
        s.shapes.title.text = slide.title  # type: ignore[union-attr]
        frame = s.placeholders[1].text_frame
        for i, bullet in enumerate(slide.bullets):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.text = bullet
        notes = slide.speaker_notes or ""
        if slide.suggested_visual:
            notes = f"{notes}\n\nSuggested visual: {slide.suggested_visual}".strip()
        if notes:
            s.notes_slide.notes_text_frame.text = notes  # type: ignore[union-attr]

    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(path)
