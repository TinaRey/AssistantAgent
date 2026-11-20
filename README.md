# Pantalelle Assistant

Private AI business assistant for Pantalelle: company research, prospecting emails,
PowerPoint decks and LinkedIn content. It is a conversational assistant with
specialised tools, **not** an autonomous agent: the user approves every external action.

This repository is independent from the Shopify theme repository.

## Status

Done: scaffold, backend tools/orchestration, password login, French chat UI with editable previews. Next: knowledge base (document upload) and a real search provider. See [docs/architecture.md](docs/architecture.md) for the plan.

## Prerequisites

- Node 20+ and npm
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 automatically)
- Docker (optional)

## Run locally

```bash
cp .env.example .env          # then set APP_PASSWORD, SECRET_KEY and OPENAI_API_KEY

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
