"""Input/output contracts of every tool. The LLM only ever sees these schemas."""

from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ---- search_company -------------------------------------------------------
class SearchCompanyInput(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    focus: str | None = Field(default=None, max_length=300, description="e.g. 'partnerships'")
    language: str = Field(default="fr", max_length=20, description="Language of the written output")


class Finding(BaseModel):
    statement: str
    source_url: str


class CollaborationIdea(BaseModel):
    """Always a hypothesis: never presented as a verified fact."""

    idea: str
    rationale: str


class Contact(BaseModel):
    name: str | None = None
    role: str | None = None
    email: str | None = Field(default=None, description="Only if literally present in a source")
    source_url: str


class CompanyResearch(BaseModel):
    company_name: str
    official_website: str | None = None
    summary: str = ""
    findings: list[Finding] = []
    collaboration_ideas: list[CollaborationIdea] = []
    contacts: list[Contact] = []
    sources: list[str] = []
    warnings: list[str] = []


# ---- retrieve_knowledge ---------------------------------------------------
class RetrieveKnowledgeInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class Passage(BaseModel):
    text: str
    source: str
    score: float | None = None


class KnowledgeResult(BaseModel):
    passages: list[Passage] = []
    note: str | None = None


# ---- generate_email -------------------------------------------------------
class GenerateEmailInput(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1000)
    recipient_email: str | None = Field(default=None, pattern=EMAIL_PATTERN)
    recipient_name: str | None = Field(default=None, max_length=200)
    research_summary: str | None = Field(default=None, max_length=6000)
    knowledge_context: str | None = Field(default=None, max_length=6000)
    tone: str = Field(default="professionnel et chaleureux", max_length=100)
    language: str = Field(default="fr", max_length=20)
    current_draft: str | None = Field(
        default=None,
        max_length=8000,
        description="Existing draft to REVISE (possibly edited by the user). Keep what the "
        "instructions do not ask to change.",
    )


class EmailBody(BaseModel):
    """What the LLM is allowed to write. The recipient is never LLM-generated."""

    subject: str
    body: str


class EmailDraft(BaseModel):
    to: str | None = None
    subject: str
    body: str
    mailto_url: str


# ---- generate_linkedin_post ----------------------------------------------
class GenerateLinkedInPostInput(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)
    tone: str = Field(default="authentique et inspirant", max_length=100)
    language: str = Field(default="fr", max_length=20)
    num_variants: int = Field(default=2, ge=1, le=5)
    current_draft: str | None = Field(
        default=None,
        max_length=8000,
        description="Existing draft to REVISE (possibly edited by the user). Keep what the "
        "instructions do not ask to change.",
    )
    knowledge_context: str | None = Field(default=None, max_length=6000)


class LinkedInPost(BaseModel):
    text: str
    hashtags: list[str] = []
    visual_suggestion: str | None = None


class LinkedInPosts(BaseModel):
    posts: list[LinkedInPost]


# ---- generate_presentation -----------------------------------------------
class GeneratePresentationInput(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1000)
    research_summary: str | None = Field(default=None, max_length=6000)
    knowledge_context: str | None = Field(default=None, max_length=6000)
    language: str = Field(default="fr", max_length=20)
    max_slides: int = Field(default=8, ge=3, le=15)
    visual_style: str | None = Field(
        default=None,
        max_length=200,
        description="Visual universe requested by the user, e.g. 'vert, bleu, nature, outdoor'.",
    )
    template: str | None = Field(
        default=None,
        max_length=200,
        description="File name (or distinctive words) of an uploaded PDF presentation to use as the "
        "model: its structure, wording and colors guide the new deck.",
    )
    illustrations: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Number of AI-generated explanatory images to create NOW. Leave 0 unless the "
        "user explicitly asked for generated images (each one costs money).",
    )


class DraftSlide(BaseModel):
    """What the LLM writes for one slide."""

    title: str
    bullets: list[str] = Field(default=[], max_length=6)
    speaker_notes: str | None = None
    suggested_visual: str | None = None
    numbered: bool = False  # numbered list instead of check marks
    image_prompt: str | None = None  # short subject of an explanatory illustration, if useful


class DraftPresentation(BaseModel):
    title: str
    slides: list[DraftSlide]
    # Only when a visual style/ambiance was requested: 6-digit hex colors without '#'.
    theme_primary: str | None = None  # dark enough for text on white
    theme_tint: str | None = None  # very light background tint


class Slide(DraftSlide):
    """A stored slide: same as the draft plus the attached image, if any."""

    image_id: str | None = None


class PresentationContent(BaseModel):
    title: str
    slides: list[Slide]


class PresentationResult(BaseModel):
    presentation_id: str
    template: str | None = None
    theme: dict[str, str] | None = None
    content: PresentationContent
    pdf_url: str
    pptx_url: str
    warnings: list[str] = []
