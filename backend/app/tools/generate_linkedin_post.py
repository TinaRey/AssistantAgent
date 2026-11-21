import re

from app.schemas.tools import GenerateLinkedInPostInput, LinkedInPost, LinkedInPosts
from app.tools.base import ToolContext, ToolSpec

_PROMPT = (
    "You write LinkedIn posts for the Pantalelle brand. Use only the facts provided; never invent "
    "products, figures, patents or testimonials. Write EVERY field (text, visual_suggestion, "
    "hashtags) in the requested language. Rules for the variants: each one must take a DIFFERENT "
    "angle and hook, and have its OWN hashtag set (3 to 5 specific hashtags, avoid generic ones "
    "like #Innovation unless it is really the point; never reuse the same set across variants). "
    "The 'text' field must NOT contain any hashtag: put them only in 'hashtags'. "
    "If a current draft is provided, revise it: apply the "
    "requested changes and keep the rest as is, returning the revised post as the first variant."
)

_TRAILING_TAGS = re.compile(r"(?:\n+[ \t]*(?:#[\wÀ-ÿ]+[ \t]*)+)+\s*$")


def normalize_hashtags(tags: list[str]) -> list[str]:
    """'mode femme' / '#Mode' / 'mode' -> '#ModeFemme' / '#Mode' / '#Mode', deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        words = re.findall(r"[\wÀ-ÿ]+", raw)
        if not words:
            continue
        tag = "#" + "".join(w[:1].upper() + w[1:] for w in words)
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def clean_post(post: LinkedInPost) -> LinkedInPost:
    """Code-level guard: hashtags live only in `hashtags`, well-formed, never duplicated in text."""
    text = _TRAILING_TAGS.sub("", post.text).rstrip()
    return post.model_copy(update={"text": text, "hashtags": normalize_hashtags(post.hashtags)})


async def generate_linkedin_post(inp: GenerateLinkedInPostInput, ctx: ToolContext) -> LinkedInPosts:
    brief = (
        f"Topic: {inp.topic}\nTone: {inp.tone}\nLanguage: {inp.language}\n"
        f"Number of variants: {inp.num_variants}\n"
        f"Pantalelle knowledge:\n{inp.knowledge_context or 'none'}\n"
        f"Current draft to revise:\n{inp.current_draft or 'none (write new posts)'}"
    )
    out = await ctx.llm.structured(
        [{"role": "system", "content": _PROMPT}, {"role": "user", "content": brief}], LinkedInPosts
    )
    return LinkedInPosts(posts=[clean_post(p) for p in out.posts[: inp.num_variants]])


SPEC = ToolSpec(
    name="generate_linkedin_post",
    description="ALWAYS use this to write LinkedIn posts (never write posts in the chat). Call it "
    "ONCE for all posts, with num_variants set to the number the user asked for (e.g. 3): "
    "variants then get distinct angles and hashtags. Shown as editable cards. "
    "Does NOT publish: publishing is manual.",
    input_model=GenerateLinkedInPostInput,
    func=generate_linkedin_post,  # type: ignore[arg-type]
    ui_card=True,
)
