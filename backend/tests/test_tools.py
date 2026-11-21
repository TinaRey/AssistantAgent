from app.integrations.search import SearchResult
from app.schemas.tools import (
    CompanyResearch,
    Contact,
    EmailBody,
    Finding,
    GenerateEmailInput,
    GenerateLinkedInPostInput,
    LinkedInPost,
    LinkedInPosts,
    RetrieveKnowledgeInput,
    SearchCompanyInput,
)
from app.tools.generate_email import generate_email
from app.tools.generate_linkedin_post import generate_linkedin_post
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


async def test_email_revision_passes_the_current_draft(make_runtime) -> None:  # type: ignore[no-untyped-def]
    llm = FakeLLM(structured=[EmailBody(subject="s", body="b")])
    *_, ctx = make_runtime(llm)
    await generate_email(
        GenerateEmailInput(
            company_name="X", objective="plus court", current_draft="Bonjour, version éditée."
        ),
        ctx,
    )
    system, user = llm.structured_messages[0]
    assert "version éditée" in user["content"] and "revise it" in system["content"]


async def test_linkedin_revision_passes_the_current_draft(make_runtime) -> None:  # type: ignore[no-untyped-def]
    llm = FakeLLM(structured=[LinkedInPosts(posts=[LinkedInPost(text="t")])])
    *_, ctx = make_runtime(llm)
    await generate_linkedin_post(
        GenerateLinkedInPostInput(topic="plus direct", current_draft="Mon post édité"), ctx
    )
    assert "Mon post édité" in llm.structured_messages[0][1]["content"]


def test_hashtags_are_normalized_and_deduplicated() -> None:
    from app.tools.generate_linkedin_post import normalize_hashtags

    assert normalize_hashtags(["mode femme", "#Outdoor", "outdoor", "", "  ", "#Éthique"]) == [
        "#ModeFemme",
        "#Outdoor",
        "#Éthique",
    ]


def test_clean_post_removes_hashtags_from_text_and_fixes_the_list() -> None:
    from app.tools.generate_linkedin_post import clean_post

    raw = LinkedInPost(
        text="Super post !\n\n#ModeFemme #Outdoor #Innovation", hashtags=["ModeFemme", "Outdoor"]
    )
    post = clean_post(raw)
    assert post.text == "Super post !" and post.hashtags == ["#ModeFemme", "#Outdoor"]
    # a hashtag used mid-sentence is real content and stays
    kept = clean_post(LinkedInPost(text="J'adore le #design local.", hashtags=[]))
    assert kept.text == "J'adore le #design local."


async def test_linkedin_variants_get_clean_hashtags(make_runtime) -> None:  # type: ignore[no-untyped-def]
    posts = LinkedInPosts(posts=[LinkedInPost(text="a\n#x #y", hashtags=["x y"])])
    *_, ctx = make_runtime(FakeLLM(structured=[posts]))
    out = await generate_linkedin_post(GenerateLinkedInPostInput(topic="t"), ctx)
    assert out.posts[0].text == "a" and out.posts[0].hashtags == ["#XY"]


def test_french_is_the_default_tone() -> None:
    assert GenerateLinkedInPostInput(topic="t").tone == "authentique et inspirant"
    assert GenerateEmailInput(company_name="X", objective="o").tone == "professionnel et chaleureux"
