from urllib.parse import quote

from app.schemas.tools import EmailBody, EmailDraft, GenerateEmailInput
from app.tools.base import ToolContext, ToolSpec

_PROMPT = (
    "You write introductory business emails for Pantalelle, an e-commerce brand. "
    "Use only the facts provided; do not invent Pantalelle facts, partnerships or figures. "
    "Do not include a recipient address. Keep it concise and personal."
)


async def generate_email(inp: GenerateEmailInput, ctx: ToolContext) -> EmailDraft:
    brief = (
        f"Target company: {inp.company_name}\nObjective: {inp.objective}\n"
        f"Recipient name: {inp.recipient_name or 'unknown'}\nTone: {inp.tone}\nLanguage: {inp.language}\n"
        f"Research about the company:\n{inp.research_summary or 'none'}\n"
        f"Pantalelle knowledge:\n{inp.knowledge_context or 'none'}"
    )
    out = await ctx.llm.structured(
        [{"role": "system", "content": _PROMPT}, {"role": "user", "content": brief}], EmailBody
    )
    # Recipient comes from the validated input only, never from the model.
    to = inp.recipient_email
    mailto = f"mailto:{to or ''}?subject={quote(out.subject)}&body={quote(out.body)}"
    return EmailDraft(to=to, subject=out.subject, body=out.body, mailto_url=mailto)


SPEC = ToolSpec(
    name="generate_email",
    description="Draft an editable introductory email (subject + body). Does NOT send anything. "
    "Only pass recipient_email if it was verified in a source or given by the user.",
    input_model=GenerateEmailInput,
    func=generate_email,  # type: ignore[arg-type]
)
