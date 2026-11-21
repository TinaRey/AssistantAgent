import asyncio
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.api.deps import Runtime, get_runtime
from app.core.config import Settings, get_settings
from app.core.ratelimit import SlidingWindowLimiter
from app.document_generation.brand import load_brand
from app.document_generation.pdf_builder import render_pdf
from app.document_generation.pptx_builder import render_pptx
from app.document_generation.theme import Theme, brand_theme, make_theme, themed_brand
from app.integrations.images import build_image_prompt
from app.integrations.llm import LLMError
from app.schemas.tools import PresentationContent, Slide
from app.services.presentations import StoredPresentation
from app.tools.generate_presentation import image_subject

router = APIRouter(prefix="/presentations")

# Brake on spending: at most 12 image generations per hour for the whole app (per process).
image_limiter = SlidingWindowLimiter(limit=12, window_s=3600)

_LLM_STATUS = {
    "rate_limit": 429,
    "timeout": 504,
    "auth": 503,
    "unavailable": 503,
    "bad_output": 502,
}


class SlideEdit(BaseModel):
    title: str = Field(max_length=200)
    bullets: list[str] = Field(default=[], max_length=6)
    speaker_notes: str | None = Field(default=None, max_length=2000)
    suggested_visual: str | None = Field(default=None, max_length=500)
    numbered: bool = False
    image_prompt: str | None = Field(default=None, max_length=300)
    image_id: str | None = Field(default=None, max_length=64)


class ThemeEdit(BaseModel):
    primary: str = Field(pattern=r"^#?[0-9A-Fa-f]{6}$")
    tint: str = Field(pattern=r"^#?[0-9A-Fa-f]{6}$")


class PresentationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slides: list[SlideEdit] = Field(max_length=30)
    theme: ThemeEdit | None = None  # None = the brand's own colors


class ImageRequest(BaseModel):
    description: str | None = Field(default=None, max_length=300)


class PresentationOut(BaseModel):
    id: str
    content: PresentationContent
    company: str | None
    visual_style: str | None
    image_count: int
    max_images: int
    image_cost_usd: float
    theme: Theme | None
    default_theme: Theme
    pdf_url: str
    pptx_url: str


def _slug(text: str | None) -> str:
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:40] or "presentation"


async def _load(rt: Runtime, pid: str) -> StoredPresentation:
    stored = await rt.presentations.get(pid)
    if stored is None:
        raise HTTPException(404, "Présentation introuvable (elle a peut-être expiré).")
    return stored


async def _out(rt: Runtime, stored: StoredPresentation, settings: Settings) -> PresentationOut:
    return PresentationOut(
        id=stored.id,
        content=stored.content,
        company=stored.company,
        visual_style=stored.visual_style,
        image_count=await rt.presentations.image_count(stored.id),
        max_images=settings.max_images_per_presentation,
        image_cost_usd=settings.image_cost_estimate_usd,
        theme=stored.theme,
        default_theme=brand_theme(load_brand()),
        pdf_url=f"/api/presentations/{stored.id}/pdf",
        pptx_url=f"/api/presentations/{stored.id}/pptx",
    )


@router.get("/{pid}", response_model=PresentationOut)
async def get_presentation(
    pid: str, rt: Runtime = Depends(get_runtime), settings: Settings = Depends(get_settings)
) -> PresentationOut:
    return await _out(rt, await _load(rt, pid), settings)


@router.put("/{pid}", response_model=PresentationOut)
async def update_presentation(
    pid: str,
    body: PresentationUpdate,
    rt: Runtime = Depends(get_runtime),
    settings: Settings = Depends(get_settings),
) -> PresentationOut:
    await _load(rt, pid)
    slides = [Slide(**s.model_dump()) for s in body.slides]
    stored = await rt.presentations.update_content(
        pid, PresentationContent(title=body.title, slides=slides)
    )
    assert stored is not None
    # Colors are validated server-side: always readable (contrast), whatever the picker sends.
    theme = make_theme(body.theme.primary, body.theme.tint) if body.theme else None
    stored = await rt.presentations.set_theme(pid, theme) or stored
    return await _out(rt, stored, settings)


@router.get("/{pid}/pdf")
async def download_pdf(pid: str, rt: Runtime = Depends(get_runtime)) -> Response:
    stored = await _load(rt, pid)
    images = await rt.presentations.images_for(pid)
    data = await asyncio.to_thread(
        render_pdf, stored.content, stored.company, themed_brand(load_brand(), stored.theme), images
    )
    return _file(data, "application/pdf", f"pantalelle-{_slug(stored.company)}.pdf")


@router.get("/{pid}/pptx")
async def download_pptx(pid: str, rt: Runtime = Depends(get_runtime)) -> Response:
    stored = await _load(rt, pid)
    images = await rt.presentations.images_for(pid)
    data = await asyncio.to_thread(
        render_pptx,
        stored.content,
        stored.company,
        themed_brand(load_brand(), stored.theme),
        images,
    )
    mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return _file(data, mime, f"pantalelle-{_slug(stored.company)}.pptx")


def _file(data: bytes, mime: str, filename: str) -> Response:
    return Response(
        data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{pid}/images/{image_id}")
async def get_image(pid: str, image_id: str, rt: Runtime = Depends(get_runtime)) -> Response:
    data = await rt.presentations.get_image(pid, image_id)
    if data is None:
        raise HTTPException(404, "Image introuvable")
    return Response(
        data, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"}
    )


@router.post("/{pid}/slides/{index}/image", response_model=PresentationOut)
async def generate_slide_image(
    pid: str,
    index: int,
    body: ImageRequest | None = None,
    rt: Runtime = Depends(get_runtime),
    settings: Settings = Depends(get_settings),
) -> PresentationOut:
    """Generates (or replaces) one illustration. Only ever triggered by an explicit user click."""
    stored = await _load(rt, pid)
    if not 0 <= index < len(stored.content.slides):
        raise HTTPException(404, "Diapositive introuvable")
    slide = stored.content.slides[index]
    count = await rt.presentations.image_count(pid)
    if slide.image_id is None and count >= settings.max_images_per_presentation:
        raise HTTPException(
            409,
            f"Limite de {settings.max_images_per_presentation} illustrations atteinte pour cette présentation.",
        )
    if not image_limiter.allow():
        raise HTTPException(429, "Trop d'images générées récemment. Réessayez plus tard.")

    subject = (body.description.strip() if body and body.description else "") or image_subject(
        slide
    )
    prompt = build_image_prompt(subject, stored.visual_style)
    try:
        data = await rt.images.generate(prompt)
    except LLMError as exc:
        raise HTTPException(_LLM_STATUS.get(exc.kind, 502), str(exc)) from exc

    new_id = await rt.presentations.add_image(pid, data, prompt)
    if slide.image_id:
        await rt.presentations.delete_image(
            pid, slide.image_id
        )  # replaced: stop paying to store it
    slide.image_id = new_id
    updated = await rt.presentations.update_content(pid, stored.content)
    assert updated is not None
    return await _out(rt, updated, settings)
