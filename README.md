# Pantalelle Assistant

Private AI business assistant for Pantalelle: company research, prospecting emails,
PowerPoint decks and LinkedIn content. It is a conversational assistant with
specialised tools, **not** an autonomous agent: the user approves every external action.

This repository is independent from the Shopify theme repository.

## Status

Done: scaffold, backend tools/orchestration, password login, French chat UI with editable previews, knowledge base (upload PDF/DOCX/TXT/MD + notes, pgvector search). Next: a real search provider (Phase 4). See [docs/architecture.md](docs/architecture.md) for the plan.

## Prerequisites

- Node 20+ and npm
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 automatically)
- Docker (optional)

## Run locally

```bash
cp .env.example .env          # then set APP_PASSWORD, SECRET_KEY and OPENAI_API_KEY

# Terminal 0: local Postgres + pgvector (Docker), then create the tables
docker compose up -d --wait db
(cd backend && uv sync && uv run alembic upgrade head)

# Terminal 1: backend  -> http://localhost:8000  (docs at /docs)
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend -> http://localhost:3000
cd frontend && npm install && npm run dev
```

Open http://localhost:3000 and sign in with `APP_PASSWORD`. The browser only talks to Next.js,
which proxies `/api/*` to the backend (`BACKEND_URL`), so the session cookie is httpOnly and same-origin.
Conversations are stored in the browser (localStorage) only.

Or with Docker: `docker compose up --build`.

## Tests and checks

```bash
cd backend && uv run pytest && uv run ruff check .
cd frontend && npm run typecheck && npm run build
```

## Environment variables

See [.env.example](.env.example). `APP_PASSWORD`, `SECRET_KEY` and `OPENAI_API_KEY` are needed to use the chat;
never commit `.env`.

## Knowledge base

Open **Documents Pantalelle** in the sidebar to upload files or paste notes (e.g. meeting minutes).
Text is extracted, split into ~1000-character passages, embedded with OpenAI
(`EMBEDDING_MODEL`, default `text-embedding-3-small`) and stored in Postgres/pgvector.
The assistant retrieves passages with the `retrieve_knowledge` tool and cites file/page.
Scanned (image-only) PDFs have no text and are rejected with a clear message.

Database: local Docker Postgres in development; Supabase (EU region) in production by changing only
`DATABASE_URL`. Schema changes go through Alembic (`uv run alembic upgrade head`).
Automated tests use the `pantalelle_test` database from the same container and skip themselves if it is down.
