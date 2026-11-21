import asyncio
import uuid

from app.document_generation.pptx_builder import build_pptx
from app.schemas.tools import GeneratePresentationInput, PresentationContent, PresentationResult
from app.tools.base import ToolContext, ToolSpec

_PROMPT = (
    "You structure a sales presentation introducing Pantalelle to a prospect. Use only the facts "
    "provided; do not invent Pantalelle facts. Give each slide a title, at most 6 short bullets, "
    "speaker notes and a suggested visual."
)


async def generate_presentation(
    inp: GeneratePresentationInput, ctx: ToolContext
) -> PresentationResult:
    # Step 1: content (LLM, structured). Step 2: document (code, fixed template).
    brief = (
        f"Target company: {inp.company_name}\nObjective: {inp.objective}\nLanguage: {inp.language}\n"
        f"Maximum slides: {inp.max_slides}\nResearch:\n{inp.research_summary or 'none'}\n"
        f"Pantalelle knowledge:\n{inp.knowledge_context or 'none'}"
    )
    content = await ctx.llm.structured(
        [{"role": "system", "content": _PROMPT}, {"role": "user", "content": brief}],
        PresentationContent,
    )
    content = content.model_copy(update={"slides": content.slides[: inp.max_slides]})
    file_id = uuid.uuid4().hex
    await asyncio.to_thread(build_pptx, content, ctx.storage_dir / f"{file_id}.pptx")
    return PresentationResult(
        content=content, file_id=file_id, download_url=f"/api/files/{file_id}"
    )


SPEC = ToolSpec(
    name="generate_presentation",
    description="Create a PowerPoint (.pptx) presentation adapted to a prospect, from Pantalelle's "
    "fixed template. Returns the slide content and a download link.",
    input_model=GeneratePresentationInput,
    func=generate_presentation,  # type: ignore[arg-type]
    timeout_s=90,
    ui_card=True,
)
