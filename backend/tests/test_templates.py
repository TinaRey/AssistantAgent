import io

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.colors import Color
from reportlab.pdfgen.canvas import Canvas

from app.api import presentations as presentations_api
from app.api.deps import build_runtime, get_runtime
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import require_auth
from app.document_generation.brand import load_brand
from app.document_generation.pdf_builder import render_pdf
from app.document_generation.theme import (
    Theme,
    brand_theme,
    contrast,
    extract_template_palette,
    extract_template_text,
    make_theme,
    palette_from_keywords,
    themed_brand,
)
from app.integrations.templates import match_template
from app.main import app
from app.schemas.tools import DraftPresentation, DraftSlide, GeneratePresentationInput
from app.tools.base import ToolError
from app.tools.generate_presentation import generate_presentation
from tests.conftest import FakeLLM, FakeTemplates


def template_pdf(primary=(0.75, 0, 0), tint=(0.99, 0.92, 0.85)) -> bytes:  # type: ignore[no-untyped-def]
    """A tiny deck: tinted title bar, colored title, black body, like the brand's."""
    out = io.BytesIO()
    c = Canvas(out, pagesize=(720, 540))
    for n in (1, 2, 3):
        c.setFillColor(Color(*tint))
        c.rect(40, 440, 640, 80, stroke=0, fill=1)
        c.setFillColor(Color(*primary))
        c.drawString(60, 470, f"Titre {n}")
        c.setFillColor(Color(0, 0, 0))
        c.drawString(60, 380, f"Le pantalon pour elles, page {n}")
        c.showPage()
    c.save()
    return out.getvalue()


def draft(**kw) -> DraftPresentation:  # type: ignore[no-untyped-def]
    return DraftPresentation(
        title="Deck", slides=[DraftSlide(title="S", bullets=["a"]), DraftSlide(title="T")], **kw
    )


# ---- theme ----------------------------------------------------------------------------------
def test_theme_is_made_readable() -> None:
    t = make_theme("#66BB6A", "A5D6A7")  # light green primary on a mid-tone tint
    assert contrast(t.primary, "FFFFFF") >= 4.5 and contrast(t.primary, t.tint) >= 4.0
    assert t.tint != "A5D6A7" and contrast("000000", t.tint) > 15  # tint was lightened
    assert make_theme("2E7D32", "E4F2E5").primary == "2E7D32"  # already fine: unchanged
    assert make_theme("nothex", "E4F2E5") is None and make_theme("#12345", "E4F2E5") is None


def test_keyword_palettes() -> None:
    green_blue = palette_from_keywords("vert, bleu, nature, outdoor")
    assert green_blue.primary == "2E7D32" and green_blue.tint == "E1EDF7"  # green leads, blue tints
    assert palette_from_keywords("Des tons sobres")  # accents + plural tolerated
    assert palette_from_keywords("ROSE pastel").primary.startswith("B0")
    assert palette_from_keywords("xyz abc") is None and palette_from_keywords("") is None


def test_themed_brand_replaces_only_the_accent_colors() -> None:
    brand = load_brand()
    themed = themed_brand(brand, Theme(primary="2E7D32", tint="E4F2E5"))
    assert (themed.colors.red, themed.colors.peach, themed.colors.cover_panel) == (
        "2E7D32",
        "E4F2E5",
        "E4F2E5",
    )
    assert themed.colors.text == brand.colors.text and themed.colors.muted == brand.colors.muted
    assert themed_brand(brand, None) is brand and brand_theme(brand).primary == "C00000"


def test_template_palette_and_text_are_read_from_a_pdf() -> None:
    pdf = template_pdf(primary=(0.1, 0.45, 0.2), tint=(0.9, 0.96, 0.9))
    theme = extract_template_palette(pdf)
    assert theme.primary == "1A7333" and theme.tint == "E6F5E6"
    text = extract_template_text(pdf)
    assert "--- Page 1 ---" in text and "Le pantalon pour elles, page 3" in text
    assert len(extract_template_text(pdf, max_chars=50)) == 50
    assert (
        extract_template_palette(b"not a pdf") is None and extract_template_text(b"not a pdf") == ""
    )


def test_pdf_with_only_black_text_has_no_palette() -> None:
    out = io.BytesIO()
    c = Canvas(out)
    c.drawString(50, 50, "noir")
    c.save()
    assert extract_template_palette(out.getvalue()) is None


def test_match_template_by_distinctive_words() -> None:
    names = ["Pantalelle_presentation generale_French.pdf", "Catalogue 2025.pdf"]
    assert match_template("présentation générale", names) == [names[0]]
    assert match_template("catalogue.pdf", names) == [names[1]]
    assert match_template("pantalelle_presentation generale_french.pdf", names) == [names[0]]
    assert match_template("pantalelle", names) == [names[0]]
    assert match_template("introuvable", names) == [] and match_template("  ", names) == []


# ---- tool -------------------------------------------------------------------------------------
async def test_template_guides_the_model_and_gives_its_colors(make_runtime) -> None:  # type: ignore[no-untyped-def]
    pdf = template_pdf(primary=(0.1, 0.45, 0.2), tint=(0.9, 0.96, 0.9))
    llm = FakeLLM(structured=[draft()])
    *_, ctx = make_runtime(llm, templates=FakeTemplates({"Présentation générale.pdf": pdf}))
    out = await generate_presentation(
        GeneratePresentationInput(
            company_name="Urgo", objective="o", template="presentation generale"
        ),
        ctx,
    )
    assert out.template == "Présentation générale.pdf"
    assert out.theme == {"primary": "1A7333", "tint": "E6F5E6"}  # the template's own colors
    brief = llm.structured_messages[0][1]["content"]
    assert (
        "TEMPLATE DECK (Présentation générale.pdf)" in brief
        and "Le pantalon pour elles, page 1" in brief
    )
    assert (await ctx.presentations.get(out.presentation_id)).theme.primary == "1A7333"


async def test_requested_ambiance_beats_the_template_colors(make_runtime) -> None:  # type: ignore[no-untyped-def]
    pdf = template_pdf()
    llm = FakeLLM(structured=[draft(theme_primary="66BB6A", theme_tint="E8F5E9")])
    *_, ctx = make_runtime(llm, templates=FakeTemplates({"deck.pdf": pdf}))
    out = await generate_presentation(
        GeneratePresentationInput(
            company_name="Urgo", objective="o", template="deck", visual_style="vert nature"
        ),
        ctx,
    )
    assert contrast(out.theme["primary"], "FFFFFF") >= 4.5  # the model's pale green was darkened
    assert out.theme["primary"] != "C00000" and out.warnings == []


async def test_ambiance_without_usable_model_colors_falls_back_to_keywords(make_runtime) -> None:  # type: ignore[no-untyped-def]
    for bad in (draft(), draft(theme_primary="zzz", theme_tint="E8F5E9")):
        *_, ctx = make_runtime(FakeLLM(structured=[bad]))
        out = await generate_presentation(
            GeneratePresentationInput(company_name="U", objective="o", visual_style="vert, bleu"),
            ctx,
        )
        assert out.theme == {"primary": "2E7D32", "tint": "E1EDF7"}


async def test_unknown_ambiance_keeps_brand_colors_and_warns(make_runtime) -> None:  # type: ignore[no-untyped-def]
    *_, ctx = make_runtime(FakeLLM(structured=[draft()]))
    out = await generate_presentation(
        GeneratePresentationInput(company_name="U", objective="o", visual_style="ambiance cosy"),
        ctx,
    )
    assert out.theme is None and "couleurs de la marque conservées" in out.warnings[0]


async def test_no_template_no_ambiance_means_brand_defaults(make_runtime) -> None:  # type: ignore[no-untyped-def]
    llm = FakeLLM(structured=[draft(theme_primary="2E7D32", theme_tint="E4F2E5")])
    *_, ctx = make_runtime(llm)
    out = await generate_presentation(
        GeneratePresentationInput(company_name="U", objective="o"), ctx
    )
    assert out.theme is None and out.template is None  # colors from the model are ignored unasked
    assert "TEMPLATE DECK" not in llm.structured_messages[0][1]["content"]


async def test_template_errors_are_explicit(make_runtime) -> None:  # type: ignore[no-untyped-def]
    pdfs = {"Présentation A.pdf": template_pdf(), "Présentation B.pdf": template_pdf()}
    *_, ctx = make_runtime(FakeLLM(structured=[draft()]), templates=FakeTemplates(pdfs))
    with pytest.raises(
        ToolError, match="Disponibles : « Présentation A.pdf », « Présentation B.pdf »"
    ):
        await generate_presentation(
            GeneratePresentationInput(company_name="U", objective="o", template="catalogue"), ctx
        )
    with pytest.raises(ToolError, match="Plusieurs PDF correspondent"):
        await generate_presentation(
            GeneratePresentationInput(company_name="U", objective="o", template="presentation"), ctx
        )
    *_, empty = make_runtime(FakeLLM())
    with pytest.raises(ToolError, match="aucun PDF n'a été ajouté"):
        await generate_presentation(
            GeneratePresentationInput(company_name="U", objective="o", template="x"), empty
        )


# ---- HTTP: edit colors, download in those colors -------------------------------------------------
@pytest.fixture
def api(monkeypatch):  # type: ignore[no-untyped-def]
    rt = build_runtime(FakeLLM())
    app.dependency_overrides[get_runtime] = lambda: rt
    app.dependency_overrides[require_auth] = lambda: None
    monkeypatch.setattr(presentations_api, "image_limiter", SlidingWindowLimiter(100, 3600))
    yield TestClient(app), rt
    app.dependency_overrides.clear()


def test_colors_can_be_edited_and_drive_the_downloads(api) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    from tests.test_presentations import content

    client, rt = api
    pid = asyncio.new_event_loop().run_until_complete(
        rt.presentations.create(content(2), "Urgo", None)
    )
    got = client.get(f"/api/presentations/{pid}").json()
    assert got["theme"] is None and got["default_theme"] == {"primary": "C00000", "tint": "FDEADA"}

    base = {"title": "T", "slides": [{"title": "S", "bullets": ["a **b**"]}]}
    r = client.put(
        f"/api/presentations/{pid}",
        json={**base, "theme": {"primary": "#2e7d32", "tint": "#e4f2e5"}},
    )
    assert r.status_code == 200 and r.json()["theme"] == {"primary": "2E7D32", "tint": "E4F2E5"}
    pdf = client.get(f"/api/presentations/{pid}/pdf").content
    assert extract_template_palette(pdf) == Theme(primary="2E7D32", tint="E4F2E5")  # round trip
    assert extract_template_palette(pdf).primary != "C00000"  # the brand red is gone from the file

    pale = client.put(
        f"/api/presentations/{pid}",
        json={**base, "theme": {"primary": "#FFEE99", "tint": "#FFFFFF"}},
    )
    assert (
        contrast(pale.json()["theme"]["primary"], "FFFFFF") >= 4.5
    )  # a user cannot pick unreadable colors

    assert (
        client.put(
            f"/api/presentations/{pid}",
            json={**base, "theme": {"primary": "red", "tint": "#ffffff"}},
        ).status_code
        == 422
    )
    back = client.put(
        f"/api/presentations/{pid}", json=base
    ).json()  # no theme = brand colors again
    assert back["theme"] is None
    assert (
        extract_template_palette(client.get(f"/api/presentations/{pid}/pdf").content).primary
        == "C00000"
    )


def test_pptx_uses_the_theme_colors(api) -> None:  # type: ignore[no-untyped-def]
    import asyncio

    from pptx import Presentation

    from tests.test_presentations import content

    client, rt = api
    pid = asyncio.new_event_loop().run_until_complete(
        rt.presentations.create(content(1), None, None)
    )
    base = {"title": "T", "slides": [{"title": "S", "bullets": ["x"]}]}
    client.put(
        f"/api/presentations/{pid}", json={**base, "theme": {"primary": "1F5F99", "tint": "E1EDF7"}}
    )
    deck = Presentation(io.BytesIO(client.get(f"/api/presentations/{pid}/pptx").content))
    slide = deck.slides[1]
    assert str(slide.shapes.title.fill.fore_color.rgb) == "E1EDF7"
    assert str(slide.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb) == "1F5F99"


def test_rendered_pdf_uses_given_brand_colors() -> None:
    from tests.test_presentations import content

    themed = themed_brand(load_brand(), Theme(primary="1F5F99", tint="E1EDF7"))
    assert extract_template_palette(render_pdf(content(2), None, themed)) == Theme(
        primary="1F5F99", tint="E1EDF7"
    )


# ---- Postgres: template PDFs from the knowledge base, theme persistence ----------------------
async def test_knowledge_service_lists_and_returns_uploaded_pdfs(kb) -> None:  # type: ignore[no-untyped-def]
    await kb.ingest_file("Présentation générale.pdf", template_pdf())
    await kb.ingest_note("Réunion", "Positionnement premium.")  # not a PDF: never a template
    await kb.ingest_file("notes.txt", b"du texte")
    assert await kb.list_pdf_names() == ["Présentation générale.pdf"]
    pdf = await kb.get_pdf("Présentation générale.pdf")
    assert pdf.filename == "Présentation générale.pdf" and pdf.data.startswith(b"%PDF")
    assert await kb.get_pdf("notes.txt") is None and await kb.get_pdf("absent.pdf") is None
    names = await kb.list_pdf_names()
    assert match_template("presentation generale", names) == ["Présentation générale.pdf"]


async def test_tool_reads_a_template_from_the_real_knowledge_base(kb, make_runtime) -> None:  # type: ignore[no-untyped-def]
    await kb.ingest_file("Pantalelle_presentation generale_French.pdf", template_pdf())
    *_, ctx = make_runtime(FakeLLM(structured=[draft()]))
    ctx = type(ctx)(
        llm=ctx.llm,
        search=ctx.search,
        knowledge=kb,
        presentations=ctx.presentations,
        images=ctx.images,
        templates=kb,
    )
    out = await generate_presentation(
        GeneratePresentationInput(
            company_name="Urgo", objective="o", template="presentation generale"
        ),
        ctx,
    )
    assert out.template == "Pantalelle_presentation generale_French.pdf"
    assert out.theme["primary"] == "BF0000"


async def test_pg_store_keeps_the_theme(pg_store) -> None:  # type: ignore[no-untyped-def]
    from tests.test_presentations import content

    pid = await pg_store.create(content(1), "Urgo", "vert", Theme(primary="2E7D32", tint="E4F2E5"))
    assert (await pg_store.get(pid)).theme == Theme(primary="2E7D32", tint="E4F2E5")
    changed = await pg_store.set_theme(pid, Theme(primary="1F5F99", tint="E1EDF7"))
    assert changed.theme.primary == "1F5F99" and (await pg_store.get(pid)).theme.primary == "1F5F99"
    assert (await pg_store.set_theme(pid, None)).theme is None
    assert await pg_store.set_theme("not-a-uuid", None) is None
    await pg_store.set_theme(pid, Theme(primary="2E7D32", tint="E4F2E5"))
    edited = await pg_store.update_content(
        pid, content(2)
    )  # editing text must not reset the colors
    assert edited.theme.primary == "2E7D32"
