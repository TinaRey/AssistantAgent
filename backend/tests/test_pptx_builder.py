from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Emu

from app.document_generation.brand import load_brand
from app.document_generation.pptx_builder import (
    BODY,
    best_size,
    build_pptx,
    clip,
    estimate_height_pt,
    paginate,
    parse_emphasis,
)
from app.schemas.tools import PresentationContent, Slide

RED = "C00000"


def make_deck(tmp_path: Path, slides: list[Slide], company: str | None = "Urgo") -> Presentation:
    path = tmp_path / "deck.pptx"
    build_pptx(PresentationContent(title="Titre de couverture", slides=slides), path, company)
    return Presentation(path)


def texts(slide) -> list[str]:  # type: ignore[no-untyped-def]
    return [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text]


def test_brand_config_is_valid_and_logo_exists() -> None:
    brand = load_brand()
    assert brand.colors.red.upper() == RED and brand.logo_path.is_file()
    assert brand.font == "Calibri"


def test_parse_emphasis_handles_unbalanced_markers() -> None:
    assert parse_emphasis("a **b** c") == [("a ", False), ("b", True), (" c", False)]
    assert parse_emphasis("a **b c") == [("a b c", False)]  # unbalanced: markers dropped, no crash
    assert parse_emphasis("") == []


def test_font_shrinks_then_content_paginates() -> None:
    short = ["Une idée courte"] * 3
    assert best_size(short) == 26 and paginate(short) == [short]
    long = ["x " * 120] * 6  # far more than one slide can hold
    assert best_size(long) is None
    pages = paginate(long)
    assert len(pages) > 1 and sum(len(p) for p in pages) == 6
    assert all(
        estimate_height_pt(p, 20) <= BODY[3] * 72 for p in pages
    )  # every page fits at min size
    assert paginate([]) == [[]]


def test_deck_structure_cover_content_closing(tmp_path: Path) -> None:
    deck = make_deck(tmp_path, [Slide(title="La solution", bullets=["Un", "Deux"])])
    assert len(deck.slides) == 3
    assert deck.slide_width == Emu(9144000) and deck.slide_height == Emu(6858000)  # 4:3
    cover, content, closing = deck.slides
    assert cover.shapes.title.text_frame.text == "Titre de couverture"
    assert "Préparée pour Urgo" in texts(cover) and "PRÉSENTATION" in texts(cover)
    assert content.shapes.title.text_frame.text == "La solution"  # real title placeholder
    assert closing.shapes.title.text_frame.text == load_brand().closing_title
    assert any("contact@pantalelle.fr" in t for t in texts(closing))


def test_cover_without_company_has_no_prepared_for_line(tmp_path: Path) -> None:
    deck = make_deck(tmp_path, [Slide(title="t", bullets=["a"])], company=None)
    assert not any("Préparée pour" in t for t in texts(deck.slides[0]))


def test_brand_colors_fonts_and_emphasis(tmp_path: Path) -> None:
    deck = make_deck(tmp_path, [Slide(title="La solution", bullets=["Un **mot clé** ici"])])
    slide = deck.slides[1]
    body = next(sh for sh in slide.shapes if sh.has_text_frame and "mot clé" in sh.text_frame.text)
    runs = body.text_frame.paragraphs[0].runs
    assert [(r.text, str(r.font.color.rgb)) for r in runs] == [
        ("Un ", "000000"),
        ("mot clé", RED),
        (" ici", "000000"),
    ]
    assert all(r.font.name == "Calibri" for r in runs)
    title_run = slide.shapes.title.text_frame.paragraphs[0].runs[0]
    assert str(title_run.font.color.rgb) == RED
    assert str(slide.shapes.title.fill.fore_color.rgb) == "FDEADA"  # peach title bar


def test_bullets_are_check_marks_or_numbers(tmp_path: Path) -> None:
    deck = make_deck(
        tmp_path,
        [Slide(title="a", bullets=["x"]), Slide(title="b", bullets=["y"], numbered=True)],
    )
    xml = {i: deck.slides[i].shapes._spTree.xml for i in (1, 2)}
    assert 'char="ü"' in xml[1] and "Wingdings" in xml[1] and "buAutoNum" not in xml[1]
    assert 'type="arabicPeriod"' in xml[2] and 'char="ü"' not in xml[2]


def test_footer_logo_and_sequential_page_numbers(tmp_path: Path) -> None:
    deck = make_deck(tmp_path, [Slide(title=f"s{i}", bullets=["a"]) for i in range(3)])
    for n, slide in enumerate(deck.slides, 1):
        assert any(sh.shape_type == 13 for sh in slide.shapes)  # logo on every slide
        if n > 1:
            assert str(n) in texts(slide)


def test_long_slide_is_split_with_suite_title(tmp_path: Path) -> None:
    deck = make_deck(tmp_path, [Slide(title="Argumentaire", bullets=["mot " * 70] * 6)])
    titles = [s.shapes.title.text_frame.text for s in deck.slides]
    assert titles[1] == "Argumentaire" and titles[2] == "Argumentaire (suite)"
    assert len(deck.slides) >= 4


def test_notes_keep_speaker_notes_and_visual(tmp_path: Path) -> None:
    deck = make_deck(
        tmp_path,
        [
            Slide(
                title="t",
                bullets=["a"],
                speaker_notes="Dire ceci",
                suggested_visual="Photo festival",
            )
        ],
    )
    notes = deck.slides[1].notes_slide.notes_text_frame.text
    assert "Dire ceci" in notes and "Visuel suggéré : Photo festival" in notes


def test_nothing_leaves_the_slide_and_titles_are_clipped(tmp_path: Path) -> None:
    deck = make_deck(tmp_path, [Slide(title="T" * 300, bullets=["a"] * 6)])
    for slide in deck.slides:
        for sh in slide.shapes:
            assert sh.left >= 0 and sh.top >= 0
            assert (
                sh.left + sh.width <= deck.slide_width and sh.top + sh.height <= deck.slide_height
            )
    assert len(deck.slides[1].shapes.title.text_frame.text) <= 110
    assert clip("  a   b  ") == "a b"


def test_body_text_never_collides_with_footer_logo() -> None:
    assert BODY[1] + BODY[3] <= 6.85  # logo top is at 6.85 in


@pytest.mark.parametrize("n_bullets", [1, 3, 6])
def test_every_bullet_count_builds(tmp_path: Path, n_bullets: int) -> None:
    deck = make_deck(tmp_path, [Slide(title="t", bullets=["texte"] * n_bullets)])
    assert len(deck.slides) == 3
