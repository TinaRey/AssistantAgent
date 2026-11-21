# Pantalelle Assistant

Private AI business assistant for Pantalelle: company research, prospecting emails,
PowerPoint decks and LinkedIn content. It is a conversational assistant with
specialised tools, **not** an autonomous agent: the user approves every external action.

This repository is independent from the Shopify theme repository.

## Status

Done: scaffold, backend tools/orchestration, password login, French chat UI with editable previews, knowledge base (upload PDF/DOCX/TXT/MD + notes, pgvector search). Web research via Tavily (set `SEARCH_API_KEY`). See [docs/architecture.md](docs/architecture.md) for the plan.

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

## Deploy (Render + Supabase)

`render.yaml` describes the two services; follow [docs/deployment.md](docs/deployment.md) (Supabase project, secrets,
Blueprint, verification checklist, troubleshooting).

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

## Company research

`search_company` runs three Tavily queries (website, news/partnerships, contacts), then asks the model to
structure the results. Code then drops any finding or contact whose source URL is not in the results,
and any email not literally present in a result. Retries: up to 2 on HTTP 429/5xx (Retry-After capped at 5 s);
quota/key errors are reported in French in the chat. Without `SEARCH_API_KEY` the assistant says nothing was verified.
Limits to know: Tavily returns page extracts, so professional emails are only found when they appear in them.
Web content is untrusted: prompts tell the model to ignore instructions inside results, and the assistant only drafts
(sending/publishing always needs the user).

## Presentations (PDF + editable PowerPoint)

Ask in the chat, e.g. "Fais une présentation pour Urgo, visuels verts et bleus, nature, outdoor". The assistant
creates a presentation card where every slide is editable (title, bullets, order, notes); changes are saved in
Postgres and the **PDF** and **PowerPoint (.pptx, editable template)** are built on demand from the saved
content, so nothing depends on the server's disk.

Brand: follows the brand's own deck (4:3, peach title bar with red title, check-mark bullets with key words
in red via `**word**`, logo + page number, diagonal cover, closing page with contact). The model only writes
text; layout lives in `backend/app/document_generation/` (`layout.py` plans the slides, shared by
`pdf_builder.py` and `pptx_builder.py`, so both split long slides identically). Brand values are in
`backend/assets/brand/brand.json` + `logo.png`. The PDF uses Carlito (metric-compatible with Calibri, SIL OFL,
`backend/assets/fonts/`); the .pptx asks for Calibri/Wingdings like the original deck.

Template + ambiance: upload any PDF presentation on the **Documents** page, then ask e.g. "Adapte la présentation
générale pour Urgo, ambiance verte et bleue nature outdoor". The assistant passes the file name as `template`
(matched by distinctive words, accents ignored): the template's text (structure, wording) is added to the model's
brief and its colors are read from the PDF (`document_generation/theme.py`, pypdf only, no extra dependency or
model call). A requested ambiance (`visual_style`) overrides the template colors: the model proposes a
`theme_primary`/`theme_tint` pair, code checks it (WCAG contrast >= 4.5, light tint) and falls back to a keyword
palette (vert, bleu, rose, terre...). Colors can then be changed in the card (two pickers, contrast re-checked on
save) and apply to both the PDF and the .pptx. The logo is a raster image and keeps its brand colors.
Not done on purpose: editing the original PDF in place (text reflow around photos is brittle).

Visuals: `visual_style` (e.g. "vert, bleu, nature, outdoor") also steers the suggested visuals and the image prompts.
**Images are never generated unless asked**: either in the chat ("avec une image explicative", max 3) or with the
per-slide button (confirmation dialog shows the indicative price). Caps: `MAX_IMAGES_PER_PRESENTATION` and
12 generations per hour per server process. A failed generation never loses the presentation.
Cost: indicative only (`IMAGE_COST_ESTIMATE_USD`); OpenAI publishes per-image prices for `gpt-image-1.5` /
`gpt-image-1-mini` (cents per 1024x1024 image at low/medium quality) but, at the time of writing, only per-token
prices for the `gpt-image-2*` family: check your OpenAI usage page after the first generations.
