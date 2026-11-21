import asyncio

from app.document_generation.theme import (
    Theme,
    extract_template_palette,
    extract_template_text,
    make_theme,
    palette_from_keywords,
)
from app.integrations.images import build_image_prompt
from app.integrations.llm import LLMError
from app.integrations.templates import match_template
from app.schemas.tools import (
    DraftPresentation,
    GeneratePresentationInput,
    PresentationContent,
    PresentationResult,
    Slide,
)
from app.tools.base import ToolContext, ToolError, ToolSpec

_PROMPT = (
    "You structure a sales presentation introducing Pantalelle to a prospect. Use only the facts "
    "provided; never invent Pantalelle facts, figures, patents or references. Write everything in "
    "the requested language. The cover page and the closing page (thanks + contact) are added "
    "automatically: do NOT create them. Each slide: a short title (max ~8 words), 3 to 5 short "
    "bullets (max ~15 words each, one idea per bullet), speaker notes, and a suggested visual. "
    "In bullets, wrap the 1 to 3 key words in **double asterisks** (they are shown in the brand red), "
    "for example 'Pantalon féminin avec **ouverture fonctionnelle** brevetée'. Set numbered=true only "
    "for an ordered list of arguments. Narrative to adapt to the prospect (skip steps that the "
    "provided facts cannot support): the usage problem, the solution, use cases, the proposed "
    "approach, why this prospect in particular. If a visual style is given, make each suggested_visual "
    "fit it. For the 2 or 3 slides where an explanatory illustration would help most, fill image_prompt "
    "with a short English description of the subject to illustrate (no text in the image, no real "
    "people's faces); leave it empty elsewhere. If a TEMPLATE DECK text is provided, it is Pantalelle's "
    "own existing presentation: follow its narrative order, tone and wording, keep its verified "
    "Pantalelle facts, and rewrite everything that is client-specific for the target company (never "
    "copy another client's details). If a visual style is requested, also return theme_primary and "
    "theme_tint: 6-digit hex colors without '#' matching that ambiance (primary: dark enough for "
    "text on white; tint: a very light background of the same family). Otherwise leave both empty."
)

MAX_PARALLEL_IMAGES = 2


def image_subject(slide: Slide) -> str:
    """What to draw for a slide: the model's image_prompt, else the slide's own topic."""
    if slide.image_prompt and slide.image_prompt.strip():
        return slide.image_prompt.strip()
    return f"{slide.title}: " + "; ".join(b.replace("**", "") for b in slide.bullets[:2])


async def generate_presentation(
    inp: GeneratePresentationInput, ctx: ToolContext
) -> PresentationResult:
    brief = (
        f"Target company: {inp.company_name}\nObjective: {inp.objective}\nLanguage: {inp.language}\n"
        f"Maximum slides: {inp.max_slides}\nVisual style requested: {inp.visual_style or 'none'}\n"
        f"Research:\n{inp.research_summary or 'none'}\n"
        f"Pantalelle knowledge:\n{inp.knowledge_context or 'none'}"
    )
    template_name, template_text, template_theme = await _load_template(inp, ctx)
    if template_text:
        brief += f"\nTEMPLATE DECK ({template_name}):\n{template_text}"
    draft = await ctx.llm.structured(
        [{"role": "system", "content": _PROMPT}, {"role": "user", "content": brief}],
        DraftPresentation,
    )
    slides = [Slide(**s.model_dump()) for s in draft.slides[: inp.max_slides]]
    warnings: list[str] = []
    theme = _choose_theme(inp, draft, template_theme, warnings)
    pid = await ctx.presentations.create(
        PresentationContent(title=draft.title, slides=slides),
        inp.company_name,
        inp.visual_style,
        theme,
    )

    if inp.illustrations and slides:
        warnings += await _illustrate(inp, ctx, pid, slides)

    content = PresentationContent(title=draft.title, slides=slides)
    stored = await ctx.presentations.update_content(pid, content)
    if stored is not None:
        content = stored.content
    return PresentationResult(
        presentation_id=pid,
        template=template_name,
        theme=theme.model_dump() if theme else None,
        content=content,
        pdf_url=f"/api/presentations/{pid}/pdf",
        pptx_url=f"/api/presentations/{pid}/pptx",
        warnings=warnings,
    )


async def _load_template(
    inp: GeneratePresentationInput, ctx: ToolContext
) -> tuple[str | None, str, Theme | None]:
    """Resolve the requested template PDF from the knowledge base; (None, '', None) if none asked."""
    if not inp.template:
        return None, "", None
    names = await ctx.templates.list_pdf_names()
    matches = match_template(inp.template, names)
    if not matches:
        available = ", ".join(f"« {n} »" for n in names) or "aucun PDF n'a été ajouté"
        raise ToolError(f"Aucun PDF ne correspond à « {inp.template} ». Disponibles : {available}.")
    if len(matches) > 1:
        raise ToolError(
            "Plusieurs PDF correspondent : " + ", ".join(f"« {n} »" for n in matches) + "."
        )
    pdf = await ctx.templates.get_pdf(matches[0])
    if pdf is None:
        raise ToolError(f"Le PDF « {matches[0]} » est introuvable.")
    text = await asyncio.to_thread(extract_template_text, pdf.data)
    theme = await asyncio.to_thread(extract_template_palette, pdf.data)
    return pdf.filename, text, theme


def _choose_theme(
    inp: GeneratePresentationInput,
    draft: DraftPresentation,
    template_theme: Theme | None,
    warnings: list[str],
) -> Theme | None:
    """Requested ambiance wins (model colors, checked by code; else keyword palette), then the
    template's own colors, else None (brand colors)."""
    if inp.visual_style:
        theme = (
            make_theme(draft.theme_primary, draft.theme_tint)
            if draft.theme_primary and draft.theme_tint
            else None
        ) or palette_from_keywords(inp.visual_style)
        if theme is None:
            warnings.append(
                f"Couleurs non reconnues pour « {inp.visual_style} » : couleurs de la marque conservées. "
                "Vous pouvez les choisir dans la fiche."
            )
        return theme
    return template_theme


async def _illustrate(
    inp: GeneratePresentationInput, ctx: ToolContext, pid: str, slides: list[Slide]
) -> list[str]:
    """Generate up to `inp.illustrations` images, preferring slides the model flagged. Never fatal."""
    flagged = [i for i, s in enumerate(slides) if s.image_prompt and s.image_prompt.strip()]
    others = [i for i in range(len(slides)) if i not in flagged]
    chosen = sorted((flagged + others)[: inp.illustrations])
    gate = asyncio.Semaphore(MAX_PARALLEL_IMAGES)
    warnings: list[str] = []

    async def one(index: int) -> None:
        prompt = build_image_prompt(image_subject(slides[index]), inp.visual_style)
        async with gate:
            try:
                data = await ctx.images.generate(prompt)
            except LLMError as exc:
                warnings.append(f"Illustration de la diapositive {index + 1} non générée : {exc}")
                return
        slides[index].image_id = await ctx.presentations.add_image(pid, data, prompt)

    await asyncio.gather(*(one(i) for i in chosen))
    return sorted(set(warnings))


SPEC = ToolSpec(
    name="generate_presentation",
    description="Create a presentation (editable in the app, downloadable as PDF and PowerPoint) "
    "adapted to a prospect, from Pantalelle's brand template; cover and closing pages are added "
    "automatically. Pass template when the user names an existing PDF presentation to base the new "
    "one on (its structure, wording and colors guide the result). Pass visual_style when the user "
    "names colors or an ambiance (e.g. 'vert, bleu, nature, outdoor'): the colors then change. Set "
    "illustrations (max 3) ONLY if the user explicitly asks for generated/explanatory images: each "
    "one is billed.",
    input_model=GeneratePresentationInput,
    func=generate_presentation,  # type: ignore[arg-type]
    timeout_s=240,
    ui_card=True,
)
