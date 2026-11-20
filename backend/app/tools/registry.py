from app.tools import (
    generate_email,
    generate_linkedin_post,
    generate_presentation,
    retrieve_knowledge,
    search_company,
)
from app.tools.base import ToolSpec


def build_registry() -> dict[str, ToolSpec]:
    specs = [
        search_company.SPEC,
        retrieve_knowledge.SPEC,
        generate_email.SPEC,
        generate_presentation.SPEC,
        generate_linkedin_post.SPEC,
    ]
    return {s.name: s for s in specs}
