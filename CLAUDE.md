# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Upstream Repository Rules

This is a fork of `open-webui/open-webui`. **Never create a PR to the upstream repository**, and never push any code there. You may fetch or pull updates from upstream to keep this fork in sync, but all changes stay in this fork only.

## What This Project Is

Open WebUI is a self-hosted AI chat platform with a SvelteKit frontend (SPA, no SSR) and a FastAPI backend. It supports Ollama, OpenAI-compatible APIs, and direct connections to Anthropic, Google Gemini, and other providers. Key capabilities include RAG, web search, image generation, voice/video, Python function calling (via Pyodide and Pipelines), MCP tool servers, and real-time collaboration over WebSockets.

## Development Commands

### Frontend (SvelteKit + Vite)

```bash
npm run dev          # start frontend dev server on :5173 (proxies API to :8080)
npm run build        # production build → build/
npm run check        # svelte-check type checking
npm run lint:frontend  # eslint --fix
npm run format       # prettier (JS/TS/Svelte/CSS/MD/JSON)
npm run test:frontend  # vitest
npm run i18n:parse   # extract i18n keys and update src/lib/i18n/
```

### Backend (FastAPI + uvicorn)

```bash
cd backend
# Development (hot reload, CORS open to :5173 and :8080):
./dev.sh
# Or manually:
CORS_ALLOW_ORIGIN="http://localhost:5173;http://localhost:8080" uvicorn open_webui.main:app --port 8080 --reload

# Format / lint:
npm run format:backend   # ruff format (from repo root)
npm run lint:backend     # pylint backend/
```

Python requires **3.11 or 3.12** (not 3.13+). Use `uv` or `pip install -e ".[all]"` to install dependencies from `pyproject.toml`.

### Backend Tests

Tests live in `backend/open_webui/test/` and require a running Postgres instance (Docker-based). Run with pytest from the repo root:

```bash
pytest backend/open_webui/test/                         # all tests
pytest backend/open_webui/test/apps/webui/routers/test_auths.py  # single file
pytest backend/open_webui/test/ -k "test_get_session_user"        # single test
```

Test classes extend `AbstractPostgresTest` and use `mock_webui_user()` context manager to simulate authenticated users.

### Database Migrations

```bash
# Create a new Alembic migration (from repo root):
DATABASE_URL=<url> alembic -c backend/open_webui/alembic.ini revision --autogenerate -m "description"
```

Migrations live in `backend/open_webui/migrations/versions/`. They run automatically on startup when `ENABLE_DB_MIGRATIONS=true` (default). The legacy Peewee migration system (`internal/wrappers.py`) also runs for older tables.

### E2E Tests

```bash
npm run cy:open      # Cypress interactive
# Playwright tests use docker-compose.playwright.yaml
```

## Architecture

### Frontend (`src/`)

- **SPA only** — `src/routes/+layout.js` sets `export const ssr = false`. All rendering is client-side.
- **Routing**: SvelteKit file-based. Route groups: `(app)/` for the main authenticated app, `auth/` for login, `s/` for shared chats, `watch/` for watch mode.
- **Global state**: Svelte writable stores in `src/lib/stores/index.ts`. The key stores are `user`, `config`, `models`, `chats`, `socket`, and `settings`. Components read/write these directly — no Flux/Redux pattern.
- **API layer**: `src/lib/apis/` mirrors the backend router structure (one directory per domain). Each module exports plain async functions that call `fetch` against `WEBUI_API_BASE_URL` (`/api/v1` in production, `http://localhost:8080/api/v1` in dev).
- **Real-time**: Socket.IO client in `+layout.svelte`, connected to `socket` store. Event emitters from the backend push chat status, model usage, and notifications.
- **i18n**: i18next with lazy-loaded JSON bundles in `src/lib/i18n/locales/`. Use `$i18n.t('key')` in templates. Run `npm run i18n:parse` after adding new string keys.
- **In-browser Python**: Pyodide worker (`src/lib/workers/pyodide.worker`) runs Python code client-side for the code interpreter. A persistent worker instance is kept in the `pyodideWorker` store.

### Backend (`backend/open_webui/`)

The FastAPI app is assembled in `main.py`, which mounts all routers, middleware, the Socket.IO ASGI app, and the static frontend build.

**Layers (read in this order when tracing a feature):**

1. `routers/` — FastAPI `APIRouter` instances, one file per domain. All public HTTP endpoints live here. Routes use `Depends(get_verified_user)` or `Depends(get_admin_user)` for auth.
2. `models/` — SQLAlchemy ORM table definitions (`class Foo(Base)`) plus Pydantic response models (`class FooModel(BaseModel)`) and a `class Foos` with static/class methods for all DB queries. There is **no repository layer** — DB operations are methods on the model class (e.g., `Chats.get_chat_by_id()`).
3. `utils/` — Shared helpers. Important ones: `auth.py` (JWT decode/encode, `get_verified_user` FastAPI dependency), `chat.py` (request dispatch to LLM providers with filter/pipeline processing), `access_control/` (group-based permission checks), `plugin.py` (loads user-defined Python functions/tools as modules).
4. `internal/db.py` — SQLAlchemy engine setup supporting SQLite and PostgreSQL. Provides `get_async_session` (FastAPI dependency) and `get_async_db_context` (context manager for use outside of request scope). **Use async sessions throughout** — the codebase is fully async.
5. `config.py` — Runtime-configurable settings backed by the database. Values read from `env.py` (environment variables) at startup and can be overridden at runtime via the Admin API.
6. `env.py` — All environment variable declarations with defaults. This is the canonical reference for what env vars exist.

**LLM request flow** (`utils/chat.py`):

```
Router endpoint → process_filter_functions (inlet) → route to provider router
  (openai.py / ollama.py / anthropic.py / etc.) → stream response
  → process_filter_functions (outlet) → return to client
```

Filters and Pipes are user-defined Python functions loaded dynamically by `utils/plugin.py`. They use a `Valves` Pydantic model for configuration.

**Real-time** (`socket/main.py`): Socket.IO server (`python-socketio`) is mounted as a sub-ASGI app. It handles model usage tracking (`USAGE_POOL`), session management, collaborative document editing (via `pycrdt`/Yjs), and event forwarding. For multi-node deployments, a Redis `AsyncRedisManager` replaces the default in-memory manager.

**RAG pipeline** (`routers/retrieval.py`, `retrieval/`):

- Documents are chunked via LangChain text splitters and embedded.
- Vector store is abstracted by `retrieval/vector/factory.py` — implementations for ChromaDB, PGVector, Qdrant, Milvus, OpenSearch, Elasticsearch, Pinecone, and others.
- Web search results are injected inline with the same pipeline via `retrieval/web/` (15+ search providers).

**Storage** (`storage/provider.py`): Abstract `StorageProvider` with backends for local filesystem, S3, Google Cloud Storage, and Azure Blob Storage. Selected via `STORAGE_PROVIDER` env var.

**Database**: Defaults to SQLite (`data/webui.db`). Set `DATABASE_URL` for PostgreSQL. Schema is managed by Alembic (newer tables) and a legacy Peewee migration runner (older tables) — both run on startup.

## Key Conventions

### Backend

- Python strings use **single quotes** (enforced by ruff: `flake8-quotes.inline-quotes = "single"`).
- Line length is 120 characters.
- Imports follow ruff isort rules; `datetime` must be imported as `import datetime as dt` (banned direct import).
- All DB access must use **async** SQLAlchemy sessions. Pass `db: AsyncSession = Depends(get_async_session)` in router signatures.
- When adding a new router, register it in `main.py` following the existing import + `app.include_router(...)` pattern.
- New database tables need both an SQLAlchemy `Base` subclass in `models/` and an Alembic migration.

### Frontend

- Svelte 5 with runes syntax where applicable.
- TailwindCSS 4 for styling. No custom CSS unless unavoidable.
- All user-facing strings must go through `$i18n.t('...')`.
- API calls go in `src/lib/apis/<domain>/index.ts`, not inline in components.
- `WEBUI_API_BASE_URL`, `OLLAMA_API_BASE_URL`, etc. are defined in `src/lib/constants.ts` — always import from there, never hardcode URLs.
