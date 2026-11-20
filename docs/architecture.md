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

## Layers (dependencies point downward only)

| Layer | Folder | Role |
|---|---|---|
| Orchestration | `services/orchestrator.py` | LLM loop, capped by `MAX_TOOL_ITERATIONS` (default 6) |
| Execution | `services/tool_runner.py` | Pydantic validation, per-tool timeout, error containment, approval gate |
| Business logic | `tools/` | One independent async function per tool: `search_company`, `retrieve_knowledge`, `generate_email`, `generate_presentation`, `generate_linkedin_post` |
| Integrations | `integrations/` | LLM, search, knowledge store: protocols + implementations (mock/empty for now) |
| Contracts | `schemas/` | Pydantic inputs/outputs of every tool, API models |

## Tool safety

- **Traceability**: every call (ok, error, timeout, invalid input, pending approval) is recorded with tool, arguments, duration and status (`GET /api/traces`, and in each chat response). Logs contain no arguments or outputs.
- **Human approval**: a `ToolSpec` with `requires_approval=True` is never run by the model loop. It becomes a pending action, executed only by `POST /api/actions/{id}/approve` (at most once) or discarded by `/reject`. No such tool exists yet (no sending/publishing in the MVP); the mechanism is in place and tested for Gmail later.
- **Anti-hallucination in code, not only in prompts**: `search_company` drops any finding/contact whose source URL is not in the search results and any email not literally present in them; `generate_email` takes the recipient from validated input only, never from the model.
- **Errors**: LLM errors map to HTTP 429/503/504/502; tool errors are returned to the model as messages so it can recover.

## Decisions

- **Orchestrator** = one LLM call loop using OpenAI tool calling. No agent framework.
- **Tools return structured data** (Pydantic); the LLM never lays out slides, python-pptx fills a fixed template.
- **Retrieval**: start with Postgres full-text search; add pgvector only if quality needs it.
- **Research**: `SearchProvider` interface with a mock implementation until a provider key exists. Every finding keeps its source URL; contacts are only reported if found in a source.
- **Email**: editable preview, copy, `mailto:`. No sending. Gmail OAuth later behind a `MailProvider` interface.
- **Auth**: single shared password (`APP_PASSWORD`) enforced before any deployment.

## Phases

0 scaffold (done) · 1 chat · 2 knowledge base · 3 email/LinkedIn/PPTX tools · 4 research · 5 integrations
