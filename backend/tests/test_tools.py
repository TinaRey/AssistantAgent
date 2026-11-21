from app.integrations.search import SearchResult
from app.schemas.tools import (
    CompanyResearch,
    Contact,
    EmailBody,
    Finding,
    GenerateEmailInput,
    GenerateLinkedInPostInput,
    GeneratePresentationInput,
    LinkedInPost,
    LinkedInPosts,
    PresentationContent,
    RetrieveKnowledgeInput,
    SearchCompanyInput,
    Slide,
)
from app.tools.generate_email import generate_email
from app.tools.generate_linkedin_post import generate_linkedin_post
from app.tools.generate_presentation import generate_presentation
from app.tools.retrieve_knowledge import retrieve_knowledge
from app.tools.search_company import search_company
from tests.conftest import FakeLLM, FakeSearch


async def test_search_company_without_results_invents_nothing(make_runtime) -> None:
    *_, ctx = make_runtime(FakeLLM())
    out = await search_company(SearchCompanyInput(company_name="Urgo"), ctx)
    assert out.findings == [] and out.contacts == [] and out.warnings
    assert "Rien n'a été vérifié" in out.warnings[-1]


async def test_search_company_drops_ungrounded_data(make_runtime) -> None:
    src = SearchResult(title="Urgo", url="https://urgo.com", snippet="Contact: press@urgo.com")
    draft = CompanyResearch(
        company_name="Urgo",
        official_website="https://fake-site.com",
        findings=[
            Finding(statement="ok", source_url="https://urgo.com"),
            Finding(statement="made up", source_url="https://invented.com"),
        ],
        contacts=[
            Contact(name="A", email="press@urgo.com", source_url="https://urgo.com"),
            Contact(name="B", email="ceo@urgo.com", source_url="https://urgo.com"),
            Contact(name="C", source_url="https://invented.com"),
        ],
    )
    *_, ctx = make_runtime(FakeLLM(structured=[draft]), search=FakeSearch([src]))
    out = await search_company(SearchCompanyInput(company_name="Urgo"), ctx)
    assert [f.statement for f in out.findings] == ["ok"]
    assert out.official_website is None
    assert [(c.name, c.email) for c in out.contacts] == [("A", "press@urgo.com"), ("B", None)]
    assert out.sources == ["https://urgo.com"]


async def test_retrieve_knowledge_empty_warns_not_to_invent(make_runtime) -> None:
    *_, ctx = make_runtime(FakeLLM())
    out = await retrieve_knowledge(RetrieveKnowledgeInput(query="brand"), ctx)
    assert out.passages == [] and "invent" in (out.note or "")


async def test_email_recipient_only_from_input(make_runtime) -> None:
    *_, ctx = make_runtime(FakeLLM(structured=[EmailBody(subject="Hi & co", body="Hello")]))
    out = await generate_email(GenerateEmailInput(company_name="X", objective="o"), ctx)
    assert out.to is None and out.mailto_url.startswith("mailto:?subject=Hi%20%26%20co")
    *_, ctx = make_runtime(FakeLLM(structured=[EmailBody(subject="s", body="b")]))
    out = await generate_email(
        GenerateEmailInput(company_name="X", objective="o", recipient_email="a@b.com"), ctx
    )
    assert out.to == "a@b.com" and out.mailto_url.startswith("mailto:a@b.com")


async def test_linkedin_variants_are_capped(make_runtime) -> None:
    posts = LinkedInPosts(posts=[LinkedInPost(text=str(i)) for i in range(4)])
    *_, ctx = make_runtime(FakeLLM(structured=[posts]))
    out = await generate_linkedin_post(GenerateLinkedInPostInput(topic="t", num_variants=2), ctx)
    assert len(out.posts) == 2


async def test_presentation_creates_downloadable_pptx(make_runtime) -> None:
    content = PresentationContent(
        title="T", slides=[Slide(title=f"s{i}", bullets=["a"]) for i in range(5)]
    )
    *_, ctx = make_runtime(FakeLLM(structured=[content]))
    out = await generate_presentation(
        GeneratePresentationInput(company_name="X", objective="o", max_slides=3), ctx
    )
    assert len(out.content.slides) == 3
    assert (ctx.storage_dir / f"{out.file_id}.pptx").is_file()
