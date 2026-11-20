# Pantalelle Assistant

Private AI business assistant for Pantalelle: company research, prospecting emails,
PowerPoint decks and LinkedIn content. It is a conversational assistant with
specialised tools, **not** an autonomous agent: the user approves every external action.

This repository is independent from the Shopify theme repository.

## Status

Phase 0 (scaffold) complete. See [docs/architecture.md](docs/architecture.md) for the plan.

## Prerequisites

- Node 20+ and npm
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 automatically)
- Docker (optional)

## Run locally

```bash
cp .env.example .env          # fill in values later; not needed to boot Phase 0

# Terminal 1: backend  -> http://localhost:8000  (docs at /docs)
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend -> http://localhost:3000
cd frontend && npm install && npm run dev
```

The home page shows "Assistant online" when the frontend reaches the backend.

Or with Docker: `docker compose up --build`.

## Tests and checks

```bash
cd backend && uv run pytest && uv run ruff check .
cd frontend && npm run typecheck && npm run build
```

## Environment variables

See [.env.example](.env.example). Only `OPENAI_API_KEY` is needed for Phase 1;
never commit `.env`.
