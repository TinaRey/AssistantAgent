from app.schemas.tools import GenerateLinkedInPostInput, LinkedInPosts
from app.tools.base import ToolContext, ToolSpec

_PROMPT = (
    "You write LinkedIn posts for the Pantalelle brand. Use only the facts provided; never invent "
    "products, figures or testimonials. For each variant give text, relevant hashtags, a suggested "
    "visual and the tone used."
)


async def generate_linkedin_post(inp: GenerateLinkedInPostInput, ctx: ToolContext) -> LinkedInPosts:
    brief = (
        f"Topic: {inp.topic}\nTone: {inp.tone}\nLanguage: {inp.language}\n"
        f"Variants: {inp.num_variants}\nPantalelle knowledge:\n{inp.knowledge_context or 'none'}"
    )
    out = await ctx.llm.structured(
        [{"role": "system", "content": _PROMPT}, {"role": "user", "content": brief}], LinkedInPosts
    )
    return LinkedInPosts(posts=out.posts[: inp.num_variants])


SPEC = ToolSpec(
    name="generate_linkedin_post",
    description="Draft LinkedIn post variants with hashtags and visual suggestions. "
    "Does NOT publish: publishing is manual.",
    input_model=GenerateLinkedInPostInput,
    func=generate_linkedin_post,  # type: ignore[arg-type]
)
