# Architecture

```
Next.js (chat UI, previews, upload)  --REST-->  FastAPI
                                                 ├─ api/            thin HTTP routes
                                                 ├─ services/       orchestrator (LLM + tool loop)
                                                 ├─ tools/          email, linkedin, pptx, research
                                                 ├─ knowledge_base/ ingestion + retrieval
                                                 ├─ document_generation/  python-pptx templates
                                                 └─ core/           config, auth, logging
                                                 PostgreSQL (app data; pgvector when needed)
```

## Decisions

- **Orchestrator** = one LLM call loop using OpenAI tool calling. No agent framework.
- **Tools return structured data** (Pydantic); the LLM never lays out slides, python-pptx fills a fixed template.
- **Retrieval**: start with Postgres full-text search; add pgvector only if quality needs it.
- **Research**: `SearchProvider` interface with a mock implementation until a provider key exists. Every finding keeps its source URL; contacts are only reported if found in a source.
- **Email**: editable preview, copy, `mailto:`. No sending. Gmail OAuth later behind a `MailProvider` interface.
- **Auth**: single shared password (`APP_PASSWORD`) enforced before any deployment.

## Phases

0 scaffold (done) · 1 chat · 2 knowledge base · 3 email/LinkedIn/PPTX tools · 4 research · 5 integrations
