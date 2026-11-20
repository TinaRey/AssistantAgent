import asyncio
import re

from app.integrations.search import SearchResult
from app.schemas.tools import CompanyResearch, SearchCompanyInput
from app.tools.base import ToolContext, ToolSpec

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

_PROMPT = (
    "You analyse web search results about a company for a prospecting assistant. "
    "Use ONLY the provided results. Every finding and contact must cite a source_url taken from "
    "the results. Never guess an email address: include one only if it appears verbatim in a result. "
    "Collaboration ideas are hypotheses, keep them clearly separate from findings."
)


async def search_company(inp: SearchCompanyInput, ctx: ToolContext) -> CompanyResearch:
    queries = [
        f"{inp.company_name} official website",
        f"{inp.company_name} {inp.focus or 'news partnerships'}",
        f"{inp.company_name} contact press partnerships email",
    ]
    batches = await asyncio.gather(*(ctx.search.search(q, 5) for q in queries))
    results: dict[str, SearchResult] = {}
    for r in (r for batch in batches for r in batch):
        results.setdefault(r.url, r)

    if not results:
        return CompanyResearch(
            company_name=inp.company_name,
            warnings=[
                "No search results (search provider not configured or nothing found). "
                "Nothing was verified."
            ],
        )

    listing = "\n\n".join(
        f"URL: {r.url}\nTitle: {r.title}\nSnippet: {r.snippet}" for r in results.values()
    )
    draft = await ctx.llm.structured(
        [
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": f"Company: {inp.company_name}\n\nResults:\n{listing}"},
        ],
        CompanyResearch,
    )
    return _enforce_grounding(draft, results)


def _enforce_grounding(draft: CompanyResearch, results: dict[str, SearchResult]) -> CompanyResearch:
    """Code-level guard: whatever the model wrote, only source-backed data survives."""
    known = set(results)
    corpus = " ".join(f"{r.title} {r.snippet}" for r in results.values())
    emails_in_sources = {e.lower() for e in _EMAIL_RE.findall(corpus)}
    warnings = list(draft.warnings)

    findings = [f for f in draft.findings if f.source_url in known]
    if len(findings) < len(draft.findings):
        warnings.append("Some findings were dropped because they cited no known source.")

    contacts = []
    for c in draft.contacts:
        if c.source_url not in known:
            warnings.append("A contact was dropped because it cited no known source.")
            continue
        if c.email and c.email.lower() not in emails_in_sources:
            warnings.append(f"Email for {c.name or 'a contact'} was removed: not found in sources.")
            c = c.model_copy(update={"email": None})
        contacts.append(c)

    site = draft.official_website if draft.official_website in known else None
    return draft.model_copy(
        update={
            "findings": findings,
            "contacts": contacts,
            "official_website": site,
            "sources": sorted(known),
            "warnings": warnings,
        }
    )


SPEC = ToolSpec(
    name="search_company",
    description="Research a company on the web: website, activities, news, collaboration "
    "hypotheses and publicly listed professional contacts. All facts carry source URLs.",
    input_model=SearchCompanyInput,
    func=search_company,  # type: ignore[arg-type]
    timeout_s=60,
)
