from app.schemas.tools import KnowledgeResult, RetrieveKnowledgeInput
from app.tools.base import ToolContext, ToolSpec


async def retrieve_knowledge(inp: RetrieveKnowledgeInput, ctx: ToolContext) -> KnowledgeResult:
    passages = await ctx.knowledge.search(inp.query, inp.top_k)
    if not passages:
        return KnowledgeResult(
            note="No Pantalelle documents matched. Do not invent company information; "
            "ask the user to upload documents or provide the facts."
        )
    return KnowledgeResult(passages=passages)


SPEC = ToolSpec(
    name="retrieve_knowledge",
    description="Search Pantalelle's own documents (brand, products, tone, references). "
    "Use before writing any content that states facts about Pantalelle.",
    input_model=RetrieveKnowledgeInput,
    func=retrieve_knowledge,  # type: ignore[arg-type]
    timeout_s=15,
)
