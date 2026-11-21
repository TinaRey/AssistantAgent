import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.api import presentations as presentations_api
from app.api.deps import build_runtime, get_runtime
from app.core.ratelimit import SlidingWindowLimiter
from app.core.security import require_auth
from app.document_generation.pdf_builder import render_pdf
from app.document_generation.pptx_builder import render_pptx
from app.integrations.images import build_image_prompt
from app.integrations.llm import LLMError
from app.main import app
from app.schemas.tools import (
    DraftPresentation,
    DraftSlide,
    GeneratePresentationInput,
    PresentationContent,
    Slide,
)
from app.tools.generate_presentation import generate_presentation, image_subject
from tests.conftest import FakeImages, FakeLLM, tiny_png


def draft(n: int = 4, flagged: tuple[int, ...] = (1,)) -> DraftPresentation:
    return DraftPresentation(
        title="Deck",
        slides=[
            DraftSlide(
                title=f"Slide {i}",
                bullets=["Un **mot** clé", "Deux"],
                image_prompt="a hiker in a green valley" if i in flagged else None,
            )
            for i in range(n)
        ],
    )


# ---- tool -------------------------------------------------------------------
async def test_no_image_is_generated_unless_requested(make_runtime) -> None:  # type: ignore[no-untyped-def]
    images = FakeImages()
    *_, ctx = make_runtime(FakeLLM(structured=[draft()]), images=images)
    out = await generate_presentation(
        GeneratePresentationInput(company_name="Urgo", objective="o"), ctx
    )
    assert images.prompts == [] and out.warnings == []  # nothing billed
    assert all(s.image_id is None for s in out.content.slides)
    assert out.pdf_url.endswith("/pdf") and out.pptx_url.endswith("/pptx")
    assert (await ctx.presentations.get(out.presentation_id)) is not None  # persisted, editable


async def test_requested_illustrations_prefer_flagged_slides_and_use_the_style(
    make_runtime,
) -> None:  # type: ignore[no-untyped-def]
    images = FakeImages()
    *_, ctx = make_runtime(FakeLLM(structured=[draft(flagged=(2,))]), images=images)
    out = await generate_presentation(
        GeneratePresentationInput(
            company_name="Urgo", objective="o", illustrations=1, visual_style="vert, bleu, nature"
        ),
        ctx,
    )
    with_image = [i for i, s in enumerate(out.content.slides) if s.image_id]
    assert with_image == [2]  # the slide the model flagged
    assert len(images.prompts) == 1
    assert "vert, bleu, nature" in images.prompts[0] and "No text" in images.prompts[0]
    assert (
        await ctx.presentations.get_image(out.presentation_id, out.content.slides[2].image_id)
        == tiny_png()
    )


async def test_image_failure_never_loses_the_presentation(make_runtime) -> None:  # type: ignore[no-untyped-def]
    images = FakeImages(fail_with=LLMError("rate_limit", "Service d'images limité"))
    *_, ctx = make_runtime(FakeLLM(structured=[draft()]), images=images)
    out = await generate_presentation(
        GeneratePresentationInput(company_name="Urgo", objective="o", illustrations=2), ctx
    )
    assert len(out.content.slides) == 4 and all(s.image_id is None for s in out.content.slides)
    assert out.warnings and "limité" in out.warnings[0]


def test_image_prompt_is_text_free_and_bounded() -> None:
    p = build_image_prompt("x" * 5000, "vert")
    assert len(p) <= 700
    short = build_image_prompt("un randonneur", None)
    assert "No text" in short and "Visual universe" not in short
    assert image_subject(Slide(title="La solution", bullets=["**Pantalon** féminin", "Autre"])) == (
        "La solution: Pantalon féminin; Autre"
    )


# ---- renderers: PDF and PPTX share one plan ---------------------------------
def content(n_slides: int = 3, **kw) -> PresentationContent:  # type: ignore[no-untyped-def]
    return PresentationContent(
        title="Titre",
        slides=[Slide(title=f"S{i}", bullets=["a **b** c"] * 3, **kw) for i in range(n_slides)],
    )


def test_pdf_and_pptx_have_the_same_number_of_pages() -> None:
    from pptx import Presentation

    long = PresentationContent(
        title="T",
        slides=[
            Slide(title="Long", bullets=["mot " * 70] * 6),
            Slide(title="Court", bullets=["a"]),
        ],
    )
    pdf = PdfReader(io.BytesIO(render_pdf(long, "Urgo")))
    pptx = Presentation(io.BytesIO(render_pptx(long, "Urgo")))
    assert len(pdf.pages) == len(pptx.slides) >= 5


def test_pdf_contains_text_page_size_and_metadata() -> None:
    reader = PdfReader(io.BytesIO(render_pdf(content(), "Urgo")))
    assert len(reader.pages) == 5  # cover + 3 + closing
    assert (
        float(reader.pages[0].mediabox.width) == 720
        and float(reader.pages[0].mediabox.height) == 540
    )
    text = " ".join(p.extract_text() for p in reader.pages)
    assert (
        "Préparée pour Urgo" in text
        and "Merci beaucoup pour votre intérêt" in text
        and "S1" in text
    )
    assert reader.metadata.title == "Titre" and reader.metadata.author == "Pantalelle"


def test_images_appear_in_both_formats() -> None:
    from pptx import Presentation

    c = PresentationContent(
        title="T", slides=[Slide(title="Avec image", bullets=["a"], image_id="img1")]
    )
    imgs = {"img1": tiny_png()}
    pdf = PdfReader(io.BytesIO(render_pdf(c, None, None, imgs)))
    without = PdfReader(io.BytesIO(render_pdf(c, None, None, {})))
    assert len(pdf.pages[1].images) == len(without.pages[1].images) + 1  # logo + illustration
    slide = Presentation(io.BytesIO(render_pptx(c, None, None, imgs))).slides[1]
    assert sum(1 for sh in slide.shapes if sh.shape_type == 13) == 2


def test_slide_with_image_uses_a_narrower_text_column() -> None:
    from app.document_generation.brand import load_brand
    from app.document_generation.layout import plan_deck

    bullets = ["mot " * 25] * 6
    plain_plan = plan_deck(
        PresentationContent(title="T", slides=[Slide(title="A", bullets=bullets)]),
        None,
        load_brand(),
    )
    img_plan = plan_deck(
        PresentationContent(title="T", slides=[Slide(title="A", bullets=bullets, image_id="x")]),
        None,
        load_brand(),
    )
    assert len(img_plan) >= len(plain_plan)  # narrower column never holds more on the first page
    first = next(p for p in img_plan if p.kind == "content")
    assert first.image_id == "x"
    assert all(p.image_id is None for p in img_plan if p.kind == "content" and p is not first)


def test_pdf_font_fallback_when_fonts_are_missing(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from app.document_generation import pdf_builder

    pdf_builder._fonts.cache_clear()
    monkeypatch.setattr(pdf_builder, "FONTS_DIR", tmp_path)  # no TTF there
    try:
        assert pdf_builder._fonts() == ("Helvetica", "Helvetica-Bold")
        assert render_pdf(content(1)).startswith(b"%PDF")
    finally:
        pdf_builder._fonts.cache_clear()


# ---- HTTP API ---------------------------------------------------------------
@pytest.fixture
def api(monkeypatch):  # type: ignore[no-untyped-def]
    images = FakeImages()
    rt = build_runtime(FakeLLM(), images=images)
    app.dependency_overrides[get_runtime] = lambda: rt
    app.dependency_overrides[require_auth] = lambda: None
    monkeypatch.setattr(presentations_api, "image_limiter", SlidingWindowLimiter(100, 3600))
    yield TestClient(app), rt, images
    app.dependency_overrides.clear()


async def make_deck(rt, **style) -> str:  # type: ignore[no-untyped-def]
    return await rt.presentations.create(content(3), "Urgo S.A.", style.get("style"))


def run(coro):  # type: ignore[no-untyped-def]
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)


def test_get_update_and_downloads(api) -> None:  # type: ignore[no-untyped-def]
    client, rt, _ = api
    pid = run(make_deck(rt))
    got = client.get(f"/api/presentations/{pid}").json()
    assert (
        got["company"] == "Urgo S.A."
        and len(got["content"]["slides"]) == 3
        and got["image_count"] == 0
    )

    edited = {"title": "Nouveau titre", "slides": [{"title": "Modifiée", "bullets": ["x **y**"]}]}
    r = client.put(f"/api/presentations/{pid}", json=edited)
    assert r.status_code == 200 and r.json()["content"]["slides"][0]["title"] == "Modifiée"

    pdf = client.get(f"/api/presentations/{pid}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert 'filename="pantalelle-urgo-s-a.pdf"' in pdf.headers["content-disposition"]
    text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Modifiée" in text  # the download reflects the user's edit
    pptx = client.get(f"/api/presentations/{pid}/pptx")
    assert zipfile.is_zipfile(io.BytesIO(pptx.content)) and pptx.headers[
        "content-disposition"
    ].endswith('.pptx"')


async def test_images_no_slide_uses_are_garbage_collected(make_runtime) -> None:  # type: ignore[no-untyped-def]
    *_, ctx = make_runtime(FakeLLM())
    store = ctx.presentations
    pid = await store.create(content(2), None, None)
    kept = await store.add_image(pid, tiny_png(), "a")
    unused = await store.add_image(pid, tiny_png(), "b")
    stored = await store.get(pid)
    stored.content.slides[0].image_id = kept
    await store.update_content(pid, stored.content)
    assert set(await store.images_for(pid)) == {kept} and unused not in await store.images_for(pid)
    stored.content.slides = stored.content.slides[1:]  # the slide holding the image is deleted
    await store.update_content(pid, stored.content)
    assert await store.image_count(pid) == 0  # frees a slot of the cost cap


def test_update_validation_and_unknown_ids(api) -> None:  # type: ignore[no-untyped-def]
    client, rt, _ = api
    pid = run(make_deck(rt))
    too_many = {"title": "t", "slides": [{"title": "s", "bullets": ["b"] * 7}]}
    assert client.put(f"/api/presentations/{pid}", json=too_many).status_code == 422
    assert (
        client.put(f"/api/presentations/{pid}", json={"title": "", "slides": []}).status_code == 422
    )
    assert (
        client.put(
            f"/api/presentations/{pid}", json={"title": "t", "slides": [{"title": "x" * 201}]}
        ).status_code
        == 422
    )
    for path in ("", "/pdf", "/pptx"):
        assert client.get(f"/api/presentations/nope{path}").status_code == 404
    assert client.get(f"/api/presentations/{pid}/images/{'0' * 32}").status_code == 404
    assert client.post(f"/api/presentations/{pid}/slides/9/image").status_code == 404


def test_slide_cannot_reference_someone_elses_image(api) -> None:  # type: ignore[no-untyped-def]
    client, rt, _ = api
    other = run(make_deck(rt))
    foreign_image = run(rt.presentations.add_image(other, tiny_png(), "p"))
    mine = run(make_deck(rt))
    body = {"title": "t", "slides": [{"title": "s", "bullets": [], "image_id": foreign_image}]}
    got = client.put(f"/api/presentations/{mine}", json=body).json()
    assert got["content"]["slides"][0]["image_id"] is None


def test_generate_slide_image_on_demand_replace_and_cap(api) -> None:  # type: ignore[no-untyped-def]
    client, rt, images = api
    from app.core.config import Settings

    app.dependency_overrides[presentations_api.get_settings] = lambda: Settings(
        max_images_per_presentation=2, _env_file=None
    )
    pid = run(make_deck(rt, style="vert, nature"))
    r = client.post(
        f"/api/presentations/{pid}/slides/0/image", json={"description": "un sentier en forêt"}
    )
    assert r.status_code == 200 and r.json()["image_count"] == 1
    first_id = r.json()["content"]["slides"][0]["image_id"]
    assert "un sentier en forêt" in images.prompts[0] and "vert, nature" in images.prompts[0]
    assert client.get(f"/api/presentations/{pid}/images/{first_id}").content == tiny_png()

    again = client.post(f"/api/presentations/{pid}/slides/0/image").json()  # replace: count stays 1
    assert again["image_count"] == 1 and again["content"]["slides"][0]["image_id"] != first_id
    assert (
        client.get(f"/api/presentations/{pid}/images/{first_id}").status_code == 404
    )  # old one deleted

    assert client.post(f"/api/presentations/{pid}/slides/1/image").status_code == 200
    blocked = client.post(f"/api/presentations/{pid}/slides/2/image")
    assert blocked.status_code == 409 and "Limite" in blocked.json()["detail"]
    pdf = client.get(f"/api/presentations/{pid}/pdf").content
    assert len(PdfReader(io.BytesIO(pdf)).pages[1].images) >= 2  # logo + generated illustration


def test_image_errors_and_rate_limit(api, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client, rt, images = api
    pid = run(make_deck(rt))
    images.fail_with = LLMError("rate_limit", "Service d'images limité")
    r = client.post(f"/api/presentations/{pid}/slides/0/image")
    assert r.status_code == 429 and "limité" in r.json()["detail"]
    assert run(rt.presentations.image_count(pid)) == 0  # failed generation stores nothing

    images.fail_with = None
    monkeypatch.setattr(presentations_api, "image_limiter", SlidingWindowLimiter(1, 3600))
    assert client.post(f"/api/presentations/{pid}/slides/0/image").status_code == 200
    assert client.post(f"/api/presentations/{pid}/slides/1/image").status_code == 429


def test_sliding_window_limiter() -> None:
    lim = SlidingWindowLimiter(2, 3600)
    assert lim.allow() and lim.allow() and not lim.allow()
    expiring = SlidingWindowLimiter(1, 0.0)
    assert expiring.allow() and expiring.allow()  # window already elapsed


# ---- Postgres store (skipped when the test database is not running) ---------
async def test_pg_store_roundtrip_images_and_isolation(pg_store) -> None:  # type: ignore[no-untyped-def]
    pid = await pg_store.create(content(2), "Urgo", "vert")
    other = await pg_store.create(content(1), "Autre", None)
    got = await pg_store.get(pid)
    assert got.company == "Urgo" and got.visual_style == "vert" and len(got.content.slides) == 2

    img = await pg_store.add_image(pid, tiny_png(), "prompt")
    assert await pg_store.image_count(pid) == 1 and await pg_store.get_image(pid, img) == tiny_png()
    assert await pg_store.get_image(other, img) is None  # scoped to its own presentation
    assert set(await pg_store.images_for(pid)) == {img}

    got.content.slides[0].image_id = img
    foreign = await pg_store.add_image(other, tiny_png(), "p")
    got.content.slides[1].image_id = foreign  # not ours: must be dropped
    saved = await pg_store.update_content(pid, got.content)
    assert saved.content.slides[0].image_id == img and saved.content.slides[1].image_id is None

    unused = await pg_store.add_image(pid, tiny_png(), "unused")
    await pg_store.update_content(pid, saved.content)  # `unused` is referenced by no slide
    assert set(await pg_store.images_for(pid)) == {img} and unused not in await pg_store.images_for(
        pid
    )
    saved.content.slides[0].image_id = None
    await pg_store.update_content(pid, saved.content)  # nothing references any image now
    assert await pg_store.image_count(pid) == 0
    await pg_store.delete_image(pid, img)
    assert await pg_store.image_count(pid) == 0
    assert await pg_store.get("not-a-uuid") is None and await pg_store.get("0" * 32) is None
    assert await pg_store.update_content("not-a-uuid", got.content) is None
